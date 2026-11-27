"""Génère la page d'accueil du site (index.html à la racine du dépôt), affichée par GitHub Pages.

Le navigateur n'exécute aucune formule : tous les chiffres sont calculés ici par le moteur réel
(lots 5 et 6) sur le jeu de démonstration fictif (interface/demo, voir generer_demo.py), puis
intégrés à la page sous forme de résultats.
Le gabarit visuel est dans interface/gabarit.html.

Usage : python interface/generer_site.py               index.html en ligne (sans données, lot 13)
        python interface/generer_site.py demo.html     démonstration complète (données intégrées)
"""
import json
from decimal import Decimal
import os
import sys
import tempfile
from datetime import date, datetime

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from zenitude.comptabilite import fees  # noqa: E402
from zenitude.comptes import pcg, tresorerie  # noqa: E402
from zenitude.config import controles as c, couverture, formules, publication  # noqa: E402
from zenitude.config.versions import Depot  # noqa: E402
from zenitude.kpi import moteur  # noqa: E402
from zenitude import socle  # noqa: E402  (lot 25)
from zenitude.kpi.mesures import Source, bornes, charger_exploitation, liste_mois, libelle_mois  # noqa: E402

date_min = date.min


def date_debut(mois):
    return date(int(mois[:4]), int(mois[5:7]), 1)


DEMO = os.path.join(RACINE, "interface", "demo")
GABARIT = os.path.join(RACINE, "interface", "gabarit.html")
LOGO = os.path.join(RACINE, "interface", "logo_zenitude.png")
ANNEE = 2026
ORDRE_KPI = ["TO-SEN", "PRIX-MOYEN", "REVPAR", "REVPAC", "DMS", "CAPTAGE-PDJ"]
# Dernier mois importé de la comptabilité (démonstration) : les mois suivants sont affichés en projection.
# Tant que le module Budgets n'existe pas, la projection reprend les écritures fictives de ces mois.
DERNIER_MOIS_IMPORTE = f"{ANNEE}-10"

# Présentation du tableau EBITDA (lot 15) : modèle du compte de résultat de gestion du groupe (fichier
# « CR Senior Bailly-Romainvilliers », onglets CR et Mapping ; structure et règles d'affectation seulement,
# aucun montant repris). À valider par le contrôle de gestion.
# Règles d'une ligne : "706" = comptes commençant par 706 ; "=60320003" = ce compte exactement ;
# "6135:POUBELLE" = comptes commençant par 6135 dont le libellé du compte contient POUBELLE (appliqué quand le
# libellé du compte est fourni par l'export). Ordre : compte exact, puis mot-clé, puis préfixe le plus long.
# Les comptes de produits affectés à une ligne de charges (75, 79, 7084, 7088) viennent en déduction.
# niveau : 0 = résultat, 1 = total, 2 = sous-total, 3 = poste.
_P = "produit"
_C = "charge"
_T = "total"
LIGNES_EBITDA = [
    ("CT_SEJ", "Court séjour", ["7061", "706"], _P, 3),
    ("LG_SEJ", "Long séjour", ["7062"], _P, 3),
    ("LG_ETU", "Long séjour étudiant", ["70:ETUDIANT"], _P, 3),
    ("LG_SEN", "Long séjour senior", ["7061:SENIOR", "7062:SENIOR", "7091", "=70630009"], _P, 3),
    ("CA_HEB", "CA hébergement", ("+", "CT_SEJ", "LG_SEJ", "LG_ETU", "LG_SEN"), _T, 2),
    ("CA_PARK", "CA parking", ["7064", "70:PARKING", "70:GARAGE"], _P, 3),
    ("CA_MEN", "CA ménages", ["70613"], _P, 3),
    ("CA_SPA", "CA SPA", ["70:SPA"], _P, 3),
    ("CA_INT", "CA internet", ["70:INTERNET", "70:WIFI"], _P, 3),
    ("CA_ELEC", "CA électricité", ["70:ELECTRICITE", "70:ELECTRIQ"], _P, 3),
    ("CA_SALLE", "CA location de salle et séminaire", ["7066", "70:SEMINAIRE", "70:LOCATION SALLE"], _P, 3),
    ("CA_DIV", "CA divers", ["70", "70612", "7063", "7065", "7067", "7068", "707", "708", "=70740000", "=70613003",
                             "70:NAVETTE"], _P, 3),
    ("CA_ANN", "CA annexes", ("+", "CA_PARK", "CA_MEN", "CA_SPA", "CA_INT", "CA_ELEC", "CA_SALLE", "CA_DIV"), _T, 2),
    ("CA_REST", "CA restauration", ["701", "7011", "7074", "70:RESTAU", "=70630010"], _P, 2),
    ("CA", "Chiffre d'affaires", ("+", "CA_HEB", "CA_ANN", "CA_REST"), _T, 1),

    ("COMM", "Commissions sur ventes", ["6222"], _C, 3),
    ("MEN_ST", "Ménage sous-traité", [], _C, 3),
    ("MEN_SAL", "Salaires bruts ménage", ["6411:MENAGE"], _C, 3),
    ("MEN_CS", "Charges sociales ménage", ["645:MENAGE"], _C, 3),
    ("MEN_CP", "Provisions CP ménage", ["6412:MENAGE", "6456:MENAGE"], _C, 3),
    ("MEN_PRI", "Primes ménage", ["6413:MENAGE"], _C, 3),
    ("MEN_INT", "Intérim ménage", ["621"], _C, 3),
    ("MEN", "Frais de personnel ménage", ("+", "MEN_ST", "MEN_SAL", "MEN_CS", "MEN_CP", "MEN_PRI", "MEN_INT"), _T, 2),
    ("BLANCH", "Blanchissage", ["6157"], _C, 3),
    ("PROD_ENT", "Produits d'entretien", ["=60320003", "=60630002"], _C, 3),
    ("PROD_ACC", "Produits d'accueil", ["=60320004", "=60630004"], _C, 3),
    ("CV_AUT", "Charges variables autres", ("+", "PROD_ENT", "PROD_ACC"), _T, 2),
    ("EAU", "Eau", ["60612"], _C, 3),
    ("ELEC", "Électricité", ["60611"], _C, 3),
    ("GAZ", "Gaz et autres énergies", ["6061"], _C, 3),
    ("ENERGIE", "Énergie et fluides", ("+", "EAU", "ELEC", "GAZ"), _T, 2),
    ("CV_HEB", "Charges variables hébergement", ("+", "COMM", "MEN", "BLANCH", "CV_AUT", "ENERGIE"), _T, 1),
    ("ACH_REST", "Achats restaurant et sous-traitance restauration",
     ["6011", "6012", "6013", "6014", "6074", "=60320006", "=60320007", "=60410001", "=60410004", "=60410005"], _C, 3),
    ("CV_REST", "Charges variables restaurant", ("+", "ACH_REST"), _T, 1),
    ("CV", "Total charges variables", ("+", "CV_HEB", "CV_REST"), _T, 1),
    ("MARGE_VAR", "Marge variable", ("-", "CA", "CV"), _T, 0),

    ("SAL_HB", "Salaires bruts hébergement", ["641", "6411", "6414", "6417", "6419"], _C, 3),
    ("CS_HB", "Charges sociales hébergement", ["64", "645", "647", "648", "649"], _C, 3),
    ("CP_HB", "Provisions CP hébergement", ["6412", "6456"], _C, 3),
    ("PRI_HB", "Primes hébergement", ["6413"], _C, 3),
    ("INT_HB", "Intérim hébergement", ["6214", "621:RECEPTION"], _C, 3),
    ("PERS_HB", "Frais de personnel hébergement", ("+", "SAL_HB", "CS_HB", "CP_HB", "PRI_HB", "INT_HB"), _T, 2),
    ("MISSION", "Frais de mission", ["6256", "6257"], _C, 3),
    ("VOYAGE", "Voyages et déplacements", ["6251"], _C, 3),
    ("AUT_PERS", "Autres frais de personnel hébergement", ("+", "MISSION", "VOYAGE"), _T, 2),
    ("PETITES", "Petites fournitures et autres", ["60", "6015", "6032", "6063", "609"], _C, 3),
    ("FOURN_ADM", "Fournitures administratives", ["6064", "=60320008"], _C, 3),
    ("FOURN", "Fournitures", ("+", "PETITES", "FOURN_ADM"), _T, 2),
    ("LOC_POUB", "Location poubelles", ["6135:POUBELLE", "6135:BENNE"], _C, 3),
    ("LOC_TV", "Location télévision", ["6135:TELEVISION", "6135:TV"], _C, 3),
    ("LOC_INFO", "Location informatique et TPE", ["61351", "=61130001", "=61350002", "=61350023", "6135:INFORMATIQUE",
                                                   "6135:TPE", "6135:COPIEUR", "6135:LOGICIEL", "6135:CAISSE",
                                                   "6135:BOX", "6135:WIFI"], _C, 3),
    ("LOC_VEH", "Location de véhicules", ["6135:VEHICULE", "6135:TRANSPORT", "6135:VOITURE", "612:PEUGEOT",
                                           "612:VEHICULE"], _C, 3),
    ("LOC_AUT", "Autres locations", ["612", "6135"], _C, 3),
    ("LOC_MAT", "Location matériel", ("+", "LOC_POUB", "LOC_TV", "LOC_INFO", "LOC_VEH", "LOC_AUT"), _T, 2),
    ("ENTRET", "Entretien", ["6152", "6155", "617"], _C, 3),
    ("MAINT", "Maintenance", ["6156"], _C, 3),
    ("MAINT_INFO", "Maintenance informatique", ["=61560003", "=61560004", "=61560006", "=61560009"], _C, 3),
    ("GARD", "Personnel extérieur (gardiennage)", ["=61130006"], _C, 3),
    ("MAINT_ENT", "Maintenance et entretien", ("+", "ENTRET", "MAINT", "MAINT_INFO", "GARD"), _T, 2),
    ("POSTE", "Frais postaux et télécommunications", ["626"], _C, 3),
    ("ASSUR", "Assurances", ["616"], _C, 3),
    ("HONO", "Honoraires", ["6226", "6227", "6228"], _C, 3),
    ("BANQUE", "Services bancaires", ["627"], _C, 3),
    ("ASSU_HONO", "Assurances, frais financiers, honoraires", ("+", "ASSUR", "HONO", "BANQUE"), _T, 2),
    ("CH_LOC", "Charges locatives", ["614"], _C, 3),
    ("TEOM", "Remboursement TEOM", ["63513"], _C, 3),
    ("LOC_IMMO", "Location immobilière", ("+", "CH_LOC", "TEOM"), _T, 2),
    ("PUB", "Publicité, communication", ["623", "6112", "=61130002"], _C, 2),
    ("TAXES", "Taxes", ["63"], _C, 2),
    ("DIVERS", "Divers", ["61", "62", "65", "75", "6037", "6041", "607", "618", "624", "628", "=61130003",
                          "=65110001"], _C, 2),
    ("TRANSF", "Transferts de charges", ["79", "7084", "7088"], _C, 2),
    ("CF_HEB", "Charges fixes hébergement", ("+", "PERS_HB", "AUT_PERS", "FOURN", "LOC_MAT", "MAINT_ENT", "POSTE",
                                             "ASSU_HONO", "LOC_IMMO", "PUB", "TAXES", "DIVERS", "TRANSF"), _T, 1),
    ("REST_SAL", "Salaires bruts restauration", ["6411:RESTAU", "6411:CUISINE", "6411:BAR"], _C, 3),
    ("REST_CS", "Charges sociales restauration", ["645:RESTAU", "645:CUISINE", "645:BAR"], _C, 3),
    ("REST_CP", "Provisions CP restauration", ["6412:RESTAU", "6412:CUISINE", "6412:BAR", "6456:RESTAU",
                                                "6456:CUISINE", "6456:BAR"], _C, 3),
    ("REST_PRI", "Primes restauration", ["6413:RESTAU"], _C, 3),
    ("REST_INT", "Intérim restauration", ["621:RESTAU", "621:CUISINE"], _C, 3),
    ("CF_REST", "Charges fixes restauration", ("+", "REST_SAL", "REST_CS", "REST_CP", "REST_PRI", "REST_INT"), _T, 1),
    ("CF", "Total charges fixes", ("+", "CF_HEB", "CF_REST"), _T, 1),
    ("EBITDAR_HS", "EBITDAR hors frais de siège", ("-", "MARGE_VAR", "CF"), _T, 0),

    ("DROIT_MARQ", "Droit de marque", ["6511"], _C, 3),
    ("SERV_INT", "Frais de service interne", ["6111", "6113"], _C, 3),
    ("FEES_EXT", "Fees externes", [], _C, 3),
    ("MKT_EXT", "Marketing externe", ["6114"], _C, 3),
    ("DM_EXT", "Droit de marque externe", ["65112"], _C, 3),
    ("SIEGE", "Frais de siège", ("+", "DROIT_MARQ", "SERV_INT", "FEES_EXT", "MKT_EXT", "DM_EXT"), _T, 1),
    ("EBITDAR", "EBITDAR y compris frais de siège et fees", ("-", "EBITDAR_HS", "SIEGE"), _T, 0),
    ("LOY_COPRO", "Loyers copropriétaires", ["6132"], _C, 3),
    ("LOY_PC", "Loyers parties communes", ["=61320000", "=61320009"], _C, 3),
    ("LOYERS", "Loyers propriétaires", ("+", "LOY_COPRO", "LOY_PC"), _T, 1),
    ("EBITDA", "EBITDA", ("-", "EBITDAR", "LOYERS"), _T, 0),

    ("H_SUBV", "Subventions d'exploitation (hors CR, en déduction)", ["74"], _C, 3),
    ("H_FIN", "Charges et produits financiers", ["66", "76", "796"], _C, 3),
    ("H_EXC", "Charges et produits exceptionnels", ["67", "77", "797"], _C, 3),
    ("H_DOT", "Dotations et reprises", ["68", "78"], _C, 3),
    ("H_IS", "Impôt sur les bénéfices", ["69"], _C, 3),
    ("HORS", "Éléments hors CR", ("+", "H_SUBV", "H_FIN", "H_EXC", "H_DOT", "H_IS"), _T, 1),
    ("RN", "Résultat net", ("-", "EBITDA", "HORS"), _T, 0),
]
# Ratios affichés sous une ligne (en % du chiffre d'affaires), calculés par la page sur les lignes ci-dessus.
RATIOS_EBITDA = [
    {"apres": "CA_REST", "code": "PCT_REST", "libelle": "en % du CA total", "num": "CA_REST", "den": "CA"},
    {"apres": "MARGE_VAR", "code": "PCT_MV", "libelle": "% marge variable", "num": "MARGE_VAR", "den": "CA"},
    {"apres": "CF", "code": "PCT_CF", "libelle": "Charges fixes en % du CA total", "num": "CF", "den": "CA"},
    {"apres": "EBITDAR_HS", "code": "PCT_EBITDAR_HS", "libelle": "EBITDAR en % du CA total", "num": "EBITDAR_HS", "den": "CA"},
    {"apres": "EBITDAR", "code": "PCT_EBITDAR", "libelle": "EBITDAR en % du CA total", "num": "EBITDAR", "den": "CA"},
]

# Soldes intermédiaires de gestion (lot 8), selon le plan comptable général. Chaque compte de classe 6
# ou 7 tombe dans la ligne de son préfixe le plus long (707 en ventes de marchandises, le reste du 70 en
# production vendue, 686 en charges financières plutôt qu'en dotations...). Provisoire, à valider par le
# contrôle de gestion comme le tableau EBITDA.
LIGNES_SIG = [
    ("CA_VENTES", "Ventes de marchandises", ["707", "7097"], "produit", 2),
    ("ACH_MARCH", "Achats consommés de marchandises", ["607", "6037", "6097"], "charge", 2),
    ("MARGE_COM", "Marge commerciale", ("+", "CA_VENTES", "-", "ACH_MARCH"), "total", 1),
    ("CA_HEB", "CA hébergement", ["706"], "produit", 2),
    ("CA_SERV", "CA autres services", ["70"], "produit", 2),
    ("CA_ANNEX", "Produits des activités annexes", ["7088"], "produit", 2),
    ("PROD_STOCK", "Production stockée et immobilisée", ["71", "72"], "produit", 2),
    ("ACH_MP", "Achats consommés de matières premières", ["601", "602", "6031", "6032", "6091", "6092"], "charge", 2),
    ("MARGE_PROD", "Marge sur production", ("+", "CA_HEB", "CA_SERV", "CA_ANNEX", "PROD_STOCK", "-", "ACH_MP"), "total", 1),
    ("VENTES_PROD", "Ventes et production", ("+", "CA_VENTES", "CA_HEB", "CA_SERV", "CA_ANNEX", "PROD_STOCK"), "total", 1),
    ("ACH_CONSO", "Achats consommés", ("+", "ACH_MARCH", "ACH_MP"), "total", 2),
    ("MARGE_GLOB", "Marge globale", ("+", "VENTES_PROD", "-", "ACH_CONSO"), "total", 1),
    ("CONSO_INT", "Consommations intermédiaires", ("+", "FOURN", "SERV_EXT"), "total", 1),
    ("FOURN", "Fournitures et autres achats", ["60"], "charge", 2),
    ("SERV_EXT", "Services extérieurs (dont loyers)", ["61", "62"], "charge", 2),
    ("VA", "Valeur ajoutée", ("+", "MARGE_GLOB", "-", "CONSO_INT"), "total", 1),
    ("SUBV", "Subventions d'exploitation", ["74"], "produit", 2),
    ("TAXES", "Impôts et taxes", ["63"], "charge", 2),
    ("PERSO", "Charges de personnel", ["64"], "charge", 2),
    ("EBE", "Excédent brut d'exploitation (EBE)", ("+", "VA", "SUBV", "-", "TAXES", "PERSO"), "total", 0),
    ("AUTRES_PROD", "Autres produits et reprises", ["75", "78", "79"], "produit", 2),
    ("AUTRES_CH", "Autres charges de gestion", ["65"], "charge", 2),
    ("DOT", "Dotations aux amortissements et provisions", ["68"], "charge", 2),
    ("REX", "Résultat d'exploitation", ("+", "EBE", "AUTRES_PROD", "-", "AUTRES_CH", "DOT"), "total", 0),
    ("PROD_FIN", "Produits financiers", ["76", "786", "796"], "produit", 2),
    ("CH_FIN", "Charges financières", ["66", "686"], "charge", 2),
    ("RCAI", "Résultat courant avant impôts", ("+", "REX", "PROD_FIN", "-", "CH_FIN"), "total", 1),
    ("PROD_EXC", "Produits exceptionnels", ["77", "787", "797"], "produit", 2),
    ("CH_EXC", "Charges exceptionnelles", ["67", "687"], "charge", 2),
    ("REXC", "Résultat exceptionnel", ("+", "PROD_EXC", "-", "CH_EXC"), "total", 1),
    ("IS", "Participation et impôt sur les bénéfices", ["69"], "charge", 2),
    ("RN", "Résultat net", ("+", "RCAI", "REXC", "-", "IS"), "total", 0),
]
# Lot 15 : mesures importées (libellés de secours ; depuis le lot 21, le catalogue fait foi).
# Une colonne par mesure d'exploitation du catalogue ; d'autres en-têtes reconnus (alias) pour reprendre les
# dossiers KPI existants. Les autres colonnes de ces dossiers (CA SAP, TO seniors...) seront ajoutées quand le
# contrôle de gestion aura validé les KPI qui les utilisent.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalogue_kpi  # noqa: E402  (lot 20)

IMPORT_KPI = [
    {"code": "LN_VENDUES", "entete": "Chambres vendues", "alias": ["Logements-nuits vendus", "Nuitées vendues"],
     "consolide": "Nuitées totales"},
    {"code": "LN_DISPONIBLES", "entete": "Chambres disponibles", "alias": ["Logements-nuits disponibles"],
     "consolide": "Capacité totale"},
    {"code": "NB_SEJOURS", "entete": "Séjours", "alias": ["Nombre de séjours", "Séjours (estim.)"],
     "consolide": "Nb de réservations"},
    {"code": "NUITEES_CLIENTS", "entete": "Clients présents (nuitées)", "alias": ["Clients présents", "Nuitées clients"],
     "consolide": "Clients présents"},
    {"code": "COUVERTS_PDJ", "entete": "Petits-déjeuners servis", "alias": ["PDJ servis", "PDJ servis (estim.)", "Couverts petit-déjeuner"],
     "consolide": "Nb PDJ"},
]
# Lot 19 (décision 0013) : quantités et montants de base de l'onglet « Données KPI » du consolidé KPI
# (Consolide_KPI_<année>.xlsx). Importées telles quelles ; les ratios sont recalculés, jamais importés.
# Les mesures CA_... sont des montants HT : elles peuvent être négatives (avoirs) ; les autres jamais.
for _code, _entete in [
        ("LOTS_HOT", "Lots hôtelier"), ("LOTS_SEN", "Lots seniors"), ("LOTS_SEN_OCC", "Lots seniors occupés"),
        ("LN_VENDUES_HOT", "Chambres vendues hôtelières"), ("LN_DISPO_HOT", "Capacité hôtelière (lots × jours)"),
        ("NUITEES_SEN", "Nuitées seniors"), ("LN_DISPO_SEN", "Capacité seniors"),
        ("CA_MEWS_TOTAL", "CA total résidence HT"), ("CA_MEWS_HOTELIER", "CA total hôtelier HT"),
        ("CA_MEWS_HEB_HOT", "CA hébergement hôtelier HT"), ("CA_MEWS_HEB_SEN", "CA hébergement seniors HT"),
        ("CA_MEWS_PDJ", "CA HT PDJ"), ("CA_MEWS_RESTO", "CA HT RESTO"), ("CA_MEWS_SPA", "CA HT SPA"),
        ("CA_SAP", "CA SAP"), ("CA_RESTO_SEN", "CA Restauration seniors")]:
    IMPORT_KPI.append({"code": _code, "entete": _entete, "alias": [], "consolide": _entete, "modele": False})

# Contrôle du consolidé : chaque ratio du fichier est recalculé à partir des quantités importées (même définition
# que l'outil KPI) ; un écart est signalé, jamais corrigé. Le ratio lui-même n'est pas importé.
RATIOS_CONSOLIDE = [
    {"colonne": "TO hôtelier", "num": "LN_VENDUES_HOT", "den": "LN_DISPO_HOT"},
    {"colonne": "PM", "num": "CA_MEWS_HEB_HOT", "den": "LN_VENDUES_HOT"},
    {"colonne": "RevPar", "num": "CA_MEWS_HEB_HOT", "den": "LN_DISPO_HOT"},
    {"colonne": "RevPac", "num": "CA_MEWS_HOTELIER", "den": "NUITEES_CLIENTS"},
    {"colonne": "DMS", "num": "LN_VENDUES_HOT", "den": "NB_SEJOURS"},
    {"colonne": "Captage PDJ", "num": "COUVERTS_PDJ", "den": "NUITEES_CLIENTS"},
    {"colonne": "TO seniors", "num": "NUITEES_SEN", "den": "LN_DISPO_SEN"},
    {"colonne": "TO résidence", "num": "LN_VENDUES", "den": "LN_DISPONIBLES"},
]
LIBELLES_JOURNAUX = {"VT": "Ventes", "HA": "Achats", "BQ": "Banque", "OD": "Opérations diverses", "AN": "À-nouveaux"}


def _depot(config):
    d = Depot(os.path.join(tempfile.mkdtemp(), "store"))
    vid = d.deposer(config, "alice")
    d.approuver(vid, "bob")
    d.appliquer(vid, "bob")
    return d


def _feuilles(classeur):
    ctx = c._Ctx(c.Rapport(chemin=classeur), set(), None)
    c._lire(ctx, classeur)
    return ctx.feuilles


def _periodes():
    out = [{"id": m, "libelle": libelle_mois(m).capitalize(), "mois": [m], "type": "mois"}
           for m in liste_mois(f"{ANNEE}-01", f"{ANNEE}-12")]
    for t in range(4):
        mois = liste_mois(f"{ANNEE}-{3 * t + 1:02d}", f"{ANNEE}-{3 * t + 3:02d}")
        out.append({"id": f"T{t + 1}-{ANNEE}", "libelle": f"{t + 1}{'er' if t == 0 else 'e'} trimestre {ANNEE}",
                    "mois": mois, "type": "trimestre"})
    out.append({"id": f"A-{ANNEE}", "libelle": f"Année civile {ANNEE}",
                "mois": liste_mois(f"{ANNEE}-01", f"{ANNEE}-12"), "type": "annee"})
    return out


def _resume(res):
    return {k["code"]: {"statut": k["statut"], "affichage": k["affichage"], "valeur": k["valeur"],
                        "motif": k["motif"]} for k in res}


def _ligne_du_compte(compte, lignes=None, libelle=""):
    """Ligne d'un compte dans un tableau, ou None si non couvert. Ordre : compte exact ("=..."), puis mot-clé du
    libellé du compte ("préfixe:MOT", seulement si le libellé est connu), puis préfixe le plus long."""
    exact, mot, pref = None, None, None
    lib = (libelle or "").upper()
    for code, _, regle, sens, _ in (lignes or LIGNES_EBITDA):
        if not isinstance(regle, list):
            continue
        for r in regle:
            if r.startswith("="):
                if compte == r[1:]:
                    exact = code
            elif ":" in r:
                p, w = r.split(":", 1)
                if lib and compte.startswith(p) and w in lib and (mot is None or len(p) > mot[1]):
                    mot = (code, len(p))
            elif compte.startswith(r) and (pref is None or len(r) > pref[1]):
                pref = (code, len(r))
    return exact or (mot[0] if mot else None) or (pref[0] if pref else None)


def _termes(regle):
    """Formule d'une ligne de total : liste de (signe, code). ("-", A, B, C) = A - B - C ;
    ("+", A, B, "-", C) = A + B - C."""
    op, *codes = regle
    if op == "-" and "-" not in codes and "+" not in codes:
        return [(1, codes[0])] + [(-1, c) for c in codes[1:]]
    out, signe = [], 1
    for c in codes:
        if c in ("+", "-"):
            signe = 1 if c == "+" else -1
        else:
            out.append((signe, c))
    return out


def _tableau(lignes, ecritures, dossiers, mois, taux):
    """Tableau de gestion par mois (montants en Decimal arrondis au centime, chaînes dans la page).
    taux = (code du ratio, numérateur, dénominateur), en pourcentage."""
    dossiers = set(dossiers)
    brut = {m: {} for m in mois}
    non_classes = set()
    for e in ecritures:
        if e["dossier"] not in dossiers:
            continue
        m = e["date"][:7]
        if m not in brut or not e["compte"][:1] in ("6", "7"):
            continue
        ligne = _ligne_du_compte(e["compte"], lignes, e.get("libelle_compte"))
        if ligne is None:
            non_classes.add(e["compte"])
            continue
        montant = Decimal(e["credit"] or 0) - Decimal(e["debit"] or 0)
        brut[m][ligne] = brut[m].get(ligne, Decimal("0")) + montant
    regles = {code: (regle, s) for code, _, regle, s, _ in lignes}

    def calc(valeurs):
        out = {}

        def val(code):
            if code in out:
                return out[code]
            regle, s = regles[code]
            if isinstance(regle, list):
                v = valeurs.get(code)
                out[code] = None if v is None else (v if s == "produit" else -v)
            else:
                termes = [(sg, val(c)) for sg, c in _termes(regle)]
                out[code] = None if all(v is None for _, v in termes) else \
                    sum(((v or Decimal("0")) * sg for sg, v in termes), Decimal("0"))
            return out[code]
        for code in regles:
            val(code)
        return out

    def chaine(d):
        return {k: (None if v is None else str(v.quantize(Decimal("0.01")))) for k, v in d.items()}

    code_taux, num, den = taux

    def ratio(d):
        if d.get(den) in (None, Decimal("0")) or d.get(num) is None:
            return None
        return str((d[num] / d[den] * 100).quantize(Decimal("0.1")))

    par_mois, cumul_r, cumul_t = {}, {}, {}
    for m in mois:
        d = calc(brut[m])
        par_mois[m] = dict(chaine(d), **{code_taux: ratio(d)})
        for code in brut[m]:
            cumul_t[code] = cumul_t.get(code, Decimal("0")) + brut[m][code]
            if m <= DERNIER_MOIS_IMPORTE:
                cumul_r[code] = cumul_r.get(code, Decimal("0")) + brut[m][code]
    tr, tt = calc(cumul_r), calc(cumul_t)
    return {"mois": par_mois, "realise": dict(chaine(tr), **{code_taux: ratio(tr)}),
            "total": dict(chaine(tt), **{code_taux: ratio(tt)}), "non_classes": sorted(non_classes)}


def _ebitda(ecritures, dossiers, mois):
    return _tableau(LIGNES_EBITDA, ecritures, dossiers, mois, ("TAUX_EBITDA", "EBITDA", "CA"))


def _sig(ecritures, dossiers, mois):
    return _tableau(LIGNES_SIG, ecritures, dossiers, mois, ("TAUX_EBE", "EBE", "VENTES_PROD"))


LIBELLES_MESURES = {
    "LN_VENDUES": "Logements-nuits vendus", "LN_DISPONIBLES": "Logements-nuits disponibles",
    "NB_SEJOURS": "Séjours", "NUITEES_CLIENTS": "Nuitées clients", "COUVERTS_PDJ": "Couverts petit-déjeuner",
}


def _lignes_exportees(lignes):
    """Lignes d'un tableau de gestion avec leur règle (préfixes de comptes ou termes d'un total),
    pour que la page recalcule le tableau quand des ajustements existent (lot 9)."""
    out = []
    for code, libelle, regle, sens, niveau in lignes:
        r = {"prefixes": list(regle)} if isinstance(regle, list) else {"termes": [[sg, cd] for sg, cd in _termes(regle)]}
        out.append({"code": code, "libelle": libelle, "niveau": niveau, "sens": sens, "regle": r})
    return out


def _libelles_pcg():
    chemin = os.path.join(RACINE, "config_modele", "pcg_reference.csv")
    out = {}
    with open(chemin, encoding="utf-8") as fh:
        for ligne in fh:
            if ligne.startswith("#") or not ligne.strip():
                continue
            champs = ligne.rstrip("\n").split(";")
            if len(champs) >= 2 and champs[0].isdigit():
                out[champs[0]] = champs[1]
    return out


def _date_iso(v):
    """Date du référentiel en AAAA-MM-JJ, ou chaîne vide si absente."""
    if v is None or v == "":
        return ""
    return v.date().isoformat() if hasattr(v, "date") else (v.isoformat() if hasattr(v, "isoformat") else str(v)[:10])


def _donnees_calcul(ecritures, exploitation, rubriques, residences):
    """Données de base pour le calculateur d'ajustements de la page (lot 9, décision 0002).

    Montants comptables en « crédit - débit » par dossier, mois et compte de classe 6 ou 7 (chaînes
    à deux décimales). Le calculateur de la page ne fait que sommer ces montants et les passer dans les
    mêmes règles que le moteur Python ; un test compare les deux (tests/test_site_ajustements.py).
    """
    mois_ecr = sorted({e["date"][:7] for e in ecritures})
    # Lot 14 : la frise va jusqu'à la fin de l'année suivante, pour les lissages répartis sur l'exercice
    # suivant (E+1). Les mois sans écriture restent sans donnée : jamais zéro.
    mois_tous = liste_mois(mois_ecr[0], max(mois_ecr[-1], f"{ANNEE + 1}-12"))
    compta, couverts = {}, {}
    for e in ecritures:
        d, m = e["dossier"], e["date"][:7]
        couverts.setdefault(d, set()).add(m)
        if e["compte"][:1] in ("6", "7"):
            cell = compta.setdefault(d, {}).setdefault(m, {})
            cell[e["compte"]] = cell.get(e["compte"], Decimal("0")) + Decimal(e["credit"] or 0) - Decimal(e["debit"] or 0)
    compta = {d: {m: {k: str(v.quantize(Decimal("0.01"))) for k, v in cs.items()} for m, cs in ms.items()}
              for d, ms in compta.items()}
    expl = {}
    for (d, m, mesure), v in exploitation.items():
        expl.setdefault(d, {}).setdefault(m, {})[mesure] = str(v)
    # Classement des comptes dans les agrégats de base : la page applique le préfixe le plus long.
    # Les cas que la page ne sait pas rejouer (rubrique propre à un dossier, datée ou avec exceptions)
    # bloquent la génération plutôt que de produire des chiffres différents du moteur.
    regles = []
    for r in rubriques:
        if str(r.get("Statut") or "").strip() != "actif":
            continue
        pref = str(r.get("Préfixe ou plage de comptes") or "").strip()
        ok = (str(r.get("Dossier Pennylane (ou * pour tous)") or "").strip() == "*" and pref.isdigit()
              and not str(r.get("Exceptions (comptes exclus, séparés par ;)") or "").strip()
              and r.get("Date de fin") in (None, "")
              and (c._date(r.get("Date d'effet")) or date_min) <= date_debut(mois_tous[0]))
        if not ok:
            raise ValueError(f"Rubrique {r.get('Code rubrique')} : cas non géré par le calculateur de la page "
                             "(dossier précis, plage, exceptions ou dates). Voir docs/decisions/0002.")
        regles.append({"prefixe": pref, "agregat": str(r["Agrégat de base"]).strip()})
    pcg = _libelles_pcg()
    return {
        "mois": mois_tous,
        "fin_donnees": mois_ecr[-1],
        "compta": compta,
        "couverts": {d: sorted(ms) for d, ms in couverts.items()},
        "exploitation": expl,
        "rubriques": regles,
        "mesures_externes": [{"code": k, "libelle": v} for k, v in LIBELLES_MESURES.items()
                             if any(k == x[2] for x in exploitation)],
        "libelles_comptes": pcg,
    }


def _groupes_crees(feuille, residences):
    """Groupes actifs de l'onglet Groupes (manuels ou dynamiques)."""
    out = []
    par_code = {r["code"]: r for r in residences}
    attributs = {"Activité": "activite", "Région": "region"}
    for g in feuille:
        if str(g.get("Statut") or "").strip() != "actif":
            continue
        membres = set()
        if str(g.get("Type") or "").strip() == "dynamique":
            criteres = []
            for col in ("Critère 1 (attribut = valeur)", "Critère 2"):
                txt = str(g.get(col) or "").strip()
                if "=" in txt:
                    a, v = (x.strip() for x in txt.split("=", 1))
                    if a in attributs:
                        criteres.append((attributs[a], v))
            et = str(g.get("Opérateur (ET / OU)") or "ET").strip().upper() != "OU"
            for r in residences:
                tests = [r[a] == v for a, v in criteres]
                if tests and (all(tests) if et else any(tests)):
                    membres.add(r["code"])
        for x in str(g.get("Inclusions manuelles (codes RES, séparés par ;)") or "").split(";"):
            if x.strip() in par_code:
                membres.add(x.strip())
        for x in str(g.get("Exclusions (codes RES, séparés par ;)") or "").split(";"):
            membres.discard(x.strip())
        if membres:
            out.append({"id": "GRP-" + str(g["Code groupe"]).strip(), "libelle": str(g["Nom"]).strip(),
                        "type": "groupe-cree", "dossiers": sorted(par_code[c]["dossier"] for c in membres)})
    return out


def _ecritures_detail(ecritures, residences):
    """Détail des écritures par dossier (lot 14), pour expliquer un montant et lisser écriture par écriture.

    Ligne : [identifiant, date, journal, pièce, compte, libellé, montant en centimes (crédit - débit),
    tiers, lettrage, échéance]. Identifiant stable : pièce + rang de la ligne dans la pièce.
    """
    dossiers = {r["dossier"] for r in residences}
    out, rangs = {}, {}
    for e in ecritures:
        d = e["dossier"]
        if d not in dossiers:
            continue
        cle = (d, e["piece"])
        rangs[cle] = rangs.get(cle, 0) + 1
        montant = Decimal(e["credit"] or 0) - Decimal(e["debit"] or 0)
        out.setdefault(d, []).append([f"{e['piece']}-{rangs[cle]}", e["date"], e["journal"], e["piece"], e["compte"],
                                      e.get("libelle") or "", int((montant * 100).quantize(Decimal("1"))),
                                      e.get("tiers") or "", e.get("lettrage") or "", e.get("echeance") or ""])
    return out


def _decaler(d, n):
    from datetime import date as _d
    m = d.month - 1 + n
    return _d(d.year + m // 12, m % 12 + 1, d.day)


def construire(demo=DEMO):
    ECR, EXE, MES, CONFIG = (os.path.join(demo, n) for n in
                             ("ecritures.csv", "exercices.csv", "mesures.csv", "configuration.xlsx"))
    depot = _depot(CONFIG)
    etat = depot._lire()
    version = next(v for v in etat["versions"] if v["id"] == etat["courante"])
    classeur = os.path.join(depot.fichiers, version["empreinte"] + ".xlsx")
    f = _feuilles(classeur)
    ecritures = couverture.charger_ecritures(ECR)
    exploitation = charger_exploitation(MES)
    source = Source(f.get("Rubriques", []), ecritures, exploitation)
    exercices = couverture.charger_exercices(EXE)

    residences = []
    for r in f.get("Referentiel", []):
        if str(r.get("Statut") or "").strip() != "actif":
            continue
        dossier = str(r["Dossier Pennylane (identifiant)"]).strip()
        debut, fin = exercices.get(dossier, (None, None))
        residences.append({"dossier": dossier, "code": str(r.get("Identifiant interne") or "").strip(), "nom": str(r["Nom de la résidence"]).strip(),
                           "activite": str(r["Activité"]).strip(), "region": str(r.get("Région") or "").strip(),
                           "societe": str(r.get("Société") or "").strip(), "marque": str(r.get("Marque") or "").strip(),
                           "ouverture": _date_iso(r.get("Date d'ouverture")), "date_effet": _date_iso(r.get("Date d'effet")),
                           "statut": str(r.get("Statut") or "").strip(),
                           "exercice": [debut.isoformat(), fin.isoformat()] if debut else None})
    residences.sort(key=lambda x: x["nom"])

    perimetres = [{"id": "GROUPE", "libelle": "Groupe Zenitude", "type": "groupe",
                   "dossiers": [r["dossier"] for r in residences]}]
    for act in sorted({r["activite"] for r in residences}):
        perimetres.append({"id": "ACT-" + act.upper(), "libelle": f"Activité {act}", "type": "activite",
                           "dossiers": [r["dossier"] for r in residences if r["activite"] == act]})
    for reg in sorted({r["region"] for r in residences if r["region"]}):
        perimetres.append({"id": "REG-" + reg.upper().replace(" ", "-"), "libelle": reg, "type": "region",
                           "dossiers": [r["dossier"] for r in residences if r["region"] == reg]})
    perimetres += _groupes_crees(f.get("Groupes", []), residences)
    for r in residences:
        perimetres.append({"id": r["dossier"], "libelle": r["nom"], "type": "residence",
                           "dossiers": [r["dossier"]]})

    periodes = _periodes()
    resultats = {}
    for p in perimetres:
        for per in periodes:
            res = moteur.calculer(f.get("KPI", []), source, p["dossiers"], per["mois"])
            resultats[f"{p['id']}|{per['id']}"] = _resume(res)
        if p["type"] == "residence" and p["dossiers"][0] in exercices:
            mois = liste_mois(*exercices[p["dossiers"][0]])
            res = moteur.calculer(f.get("KPI", []), source, p["dossiers"], mois)
            resultats[f"{p['id']}|EXERCICE"] = _resume(res)

    actifs = moteur.kpis_actifs(f.get("KPI", []), *bornes(liste_mois(f"{ANNEE}-01", f"{ANNEE}-12")))
    codes = [k for k in ORDRE_KPI if k in actifs] + sorted(k for k in actifs if k not in ORDRE_KPI)
    kpi_defs = [{"code": k, "nom": str(actifs[k].get("Nom") or ""), "formule": str(actifs[k].get("Formule") or ""),
                 "definition": str(actifs[k].get("Définition") or ""), "unite": str(actifs[k].get("Unité") or ""),
                 "approbateur": str(actifs[k].get("Approbateur") or ""), "principal": k in ORDRE_KPI,
                 "arbre": formules.arbre(str(actifs[k].get("Formule") or ""))}
                for k in codes]

    # Compte de résultat (lot 5) : une publication par dossier sur son exercice
    finance = []
    for r in residences:
        try:
            _pid, inst = publication.publier(depot, ECR, EXE, r["dossier"], "carol")
            finance.append({"dossier": r["dossier"], "nom": r["nom"], "exercice": inst["exercice"],
                            "resultat": inst["resultat"], "statut": "publié", "publication": _pid,
                            "compte_resultat": inst["compte_resultat"]})
        except publication.PublicationBloquee as e:
            finance.append({"dossier": r["dossier"], "nom": r["nom"], "statut": "bloqué",
                            "motif": "comptes non classés : " + ", ".join(e.non_classes)})

    # Trésorerie (lot 11) : agrégats par dossier et par arrêté (fin de mois jusqu'au dernier mois importé).
    # La page ne fait que sommer ces agrégats sur le périmètre (voir docs/decisions/0003).
    mois_treso = liste_mois(min(e["date"][:7] for e in ecritures), DERNIER_MOIS_IMPORTE)
    treso = {"mois": mois_treso, "modes": list(tresorerie.MODES),
             "tranches": [{"code": t, "libelle": tresorerie.LIBELLES_TRANCHES[t]} for t in tresorerie.TRANCHES],
             "dossiers": {r["dossier"]: tresorerie.calculer_dossier(ecritures, r["dossier"], mois_treso)
                          for r in residences}}

    # Couverture des données par dossier et par mois
    mois_annee = liste_mois(f"{ANNEE}-01", f"{ANNEE}-12")
    mois_ecr = {(e["dossier"], e["date"][:7]) for e in ecritures}
    noms_mesures = sorted({k[2] for k in exploitation})
    couv = {}
    for r in residences:
        d = r["dossier"]
        couv[d] = {m: {"compta": (d, m) in mois_ecr,
                       "exploitation": sum((d, m, x) in exploitation for x in noms_mesures),
                       "attendu": len(noms_mesures)} for m in mois_annee}

    # Tableau EBITDA (lot 8) par périmètre, mois civils de l'année
    ebitda = {p["id"]: _ebitda(ecritures, p["dossiers"], mois_annee) for p in perimetres}
    # Soldes intermédiaires de gestion (lot 8), même découpage réalisé / projection
    sig = {p["id"]: _sig(ecritures, p["dossiers"], mois_annee) for p in perimetres}

    # Import comptable : exercices N-1, N, N+1 de chaque dossier et volume d'écritures
    imports = {}
    for r in residences:
        d = r["dossier"]
        if d not in exercices:
            continue
        debut, fin = exercices[d]
        lignes_d = [e for e in ecritures if e["dossier"] == d]
        rangs = []
        for rang, n in (("N-1", -12), ("N", 0), ("N+1", 12)):
            db, fn = _decaler(debut, n), _decaler(fin, n)
            # Seules les écritures jusqu'au dernier mois importé comptent comme importées ;
            # les mois suivants servent de projection (démonstration)
            dedans = [e for e in lignes_d if db.isoformat() <= e["date"] <= fn.isoformat()
                      and e["date"][:7] <= DERNIER_MOIS_IMPORTE]
            dates = sorted(e["date"] for e in dedans)
            rangs.append({"rang": rang, "debut": db.isoformat(), "fin": fn.isoformat(), "ecritures": len(dedans),
                          "periode_importee": [dates[0], dates[-1]] if dates else None})
        imports[d] = rangs

    # Journaux et plan comptable (comptes de classes 6 et 7 présents dans les écritures)
    journaux, comptes = {}, {}
    rubriques = f.get("Rubriques", [])
    for e in ecritures:
        j = journaux.setdefault(e["journal"], {"code": e["journal"], "libelle": LIBELLES_JOURNAUX.get(e["journal"], ""),
                                               "lignes": 0, "dossiers": set()})
        j["lignes"] += 1
        j["dossiers"].add(e["dossier"])
        c_ = comptes.setdefault(e["compte"], {"compte": e["compte"], "lignes": 0})
        c_["lignes"] += 1
    libelles = {l[0]: l[1] for l in LIGNES_EBITDA}
    libelles_sig = {l[0]: l[1] for l in LIGNES_SIG}
    plan = []
    for num in sorted(comptes):
        rub = [r for r in rubriques if num.startswith(str(r.get("Préfixe ou plage de comptes") or "#"))]
        ligne = _ligne_du_compte(num) if num[:1] in "67" else None
        ligne_sig = _ligne_du_compte(num, LIGNES_SIG) if num[:1] in "67" else None
        plan.append({"compte": num, "classe": num[0], "lignes": comptes[num]["lignes"],
                     "rubrique": rub[0]["Code rubrique"] if rub else None,
                     "agregat": rub[0]["Agrégat de base"] if rub else None,
                     "ligne_ebitda": libelles.get(ligne) if ligne else None,
                     "ligne_sig": libelles_sig.get(ligne_sig) if ligne_sig else None})
    journaux = [dict(j, dossiers=len(j["dossiers"])) for j in sorted(journaux.values(), key=lambda x: x["code"])]

    statut = depot.statut()
    return {
        "meta": {"version_config": version["id"], "empreinte_config": version["empreinte"],
                 "genere_le": datetime.now().strftime("%d/%m/%Y à %H:%M"), "annee": ANNEE,
                 "periode_defaut": DERNIER_MOIS_IMPORTE,
                 "nb_ecritures": len(ecritures), "nb_mesures": len(exploitation),
                 "mesures": noms_mesures, "donnees": "fictives (phase test)",
                 "dernier_mois_importe": DERNIER_MOIS_IMPORTE},
        "residences": residences, "perimetres": perimetres, "periodes": periodes,
        "kpi": kpi_defs, "resultats": resultats, "finance": finance, "couverture": couv,
        "cr_lignes": pcg.lignes_exportees(), "cr_reference": pcg.REFERENCE, "tresorerie": treso,
        "mois": mois_annee,
        "lignes_ebitda": _lignes_exportees(LIGNES_EBITDA),
        "ratios_ebitda": RATIOS_EBITDA,
        "import_kpi": IMPORT_KPI, "ratios_consolide": RATIOS_CONSOLIDE,
        # Lot 20 : catalogue de départ (démonstration locale ; en ligne, la page lit la base)
        "catalogue_defaut": catalogue_kpi.CATALOGUE, "modeles_defaut": catalogue_kpi.MODELES,
        "modele_par_activite": catalogue_kpi.MODELE_PAR_ACTIVITE,
        # Lot 24 : rubriques et règles de FEES de départ (démonstration locale ; en ligne, la page lit la base)
        "fees_depart": {"rubriques": fees.RUBRIQUES_DEPART, "regles": fees.REGLES_DEPART},
        "ebitda": ebitda,
        "lignes_sig": _lignes_exportees(LIGNES_SIG),
        "sig": sig, "imports": imports, "journaux": journaux, "plan": plan,
        "calcul": _donnees_calcul(ecritures, exploitation, f.get("Rubriques", []), residences),
        "ecritures": _ecritures_detail(ecritures, residences),
        "versions": statut["versions"], "journal": statut["journal"],
        # Lot 25 : définition du paquet pour Claude (fichiers, contrôles, modèles de texte), commune à toutes les résidences
        "socle": socle.definition(),
    }


def main(sortie, demo=DEMO, en_ligne=False):
    """Écrit la page. en_ligne=False (tests, démonstration locale en file://) : toutes les données de
    démonstration sont intégrées à la page. en_ligne=True (index.html publié par GitHub Pages, lot 13) :
    la page ne contient aucune donnée ; elle les lit dans la base, filtrées par le parc de la personne
    connectée (voir publier_supabase.py et docs/decisions/0007)."""
    donnees = None
    if not en_ligne:
        if not os.path.exists(os.path.join(demo, "configuration.xlsx")):
            sys.path.insert(0, os.path.join(RACINE, "interface"))
            import generer_demo
            generer_demo.main(demo)
        donnees = construire(demo)
    ecrire(sortie, donnees)
    print("site écrit :", sortie, "(en ligne, sans données)" if en_ligne else "(démonstration complète)")


def ecrire(sortie, donnees):
    """Écrit la page avec ces données intégrées (None : page en ligne, sans données)."""
    texte = "null" if donnees is None else \
        json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    gabarit = open(GABARIT, encoding="utf-8").read()
    import base64
    with open(LOGO, "rb") as fh:
        logo = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    with open(sortie, "w", encoding="utf-8") as fh:
        fh.write(gabarit.replace("__LOGO__", logo).replace("/*__DONNEES__*/null", texte))


if __name__ == "__main__":
    # Sans argument : index.html à la racine, version en ligne (aucune donnée dans la page).
    # Avec un chemin : démonstration complète, à ouvrir directement dans un navigateur.
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main(os.path.join(RACINE, "index.html"), en_ligne=True)
