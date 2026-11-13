"""Compte de résultat du Plan comptable général, système de base (lot 11).

Référence : règlement ANC n° 2014-03 modifié par le règlement ANC n° 2022-06 (homologué par arrêté du
26 décembre 2023), applicable aux exercices ouverts à compter du 1er janvier 2025. Modèle en liste de
l'article 821-2 et tableau de passage indicatif entre le plan de comptes minimal et les postes (IR4).
Depuis ce règlement, le « système développé » n'existe plus : seuls subsistent le système de base et le
système abrégé. Les transferts de charges (comptes 791, 796, 797) sont supprimés.

Règles :
- chaque compte de classe 6 ou 7 tombe dans un seul poste : celui de son préfixe le plus long
  (invariant 3) ; un compte qu'aucun préfixe ne couvre est « non classé » et bloque le compte de
  résultat (même logique que le contrôle P1) ;
- poste de produit = crédit - débit ; poste de charge = débit - crédit (les comptes à solde inverse,
  par exemple 7097 ou 609, viennent donc en déduction du poste auquel ils se rattachent) ;
- montants en Decimal, aucune annualisation, exercice court conservé tel quel ;
- une absence d'écriture sur l'exercice n'est jamais zéro : « non calculable » avec motif (invariant 1) ;
- exercice précédent (N-1) : non disponible tant que les écritures de N-1 ne sont pas importées.

Choix de rattachement à faire valider par la direction financière (le règlement impose de rattacher
les subdivisions aux postes concernés, ce que le seul numéro de compte ne permet pas toujours) :
708 et 709 sans subdivision -> production vendue ; 608 -> achats de marchandises ; 648 et 649 ->
cotisations sociales ; 6094, 6095, 6096, 6098 -> autres achats et charges externes.
Les comptes 643, 644, 646, 681 sans subdivision, 697, 768 restent non classés tant qu'ils ne sont pas
tranchés : ils ne figurent pas dans le tableau de passage du règlement.
"""
from datetime import date
from decimal import Decimal

REFERENCE = "ANC 2014-03 modifié par ANC 2022-06, système de base (art. 821-2)"
VERSION = "cr-pcg-v1"

# code, libellé, règle, sens, niveau
#   règle : liste de préfixes de comptes (poste), ou liste de (signe, code) (total) ;
#   sens  : "produit" | "charge" | "total" | "titre" | "memo" ;
#   niveau : 0 = résultat, 1 = total, 2 = poste, 3 = mémo, 9 = titre de rubrique.
LIGNES_CR = [
    ("T_PE", "Produits d'exploitation", [], "titre", 9),
    ("V_MARCH", "Ventes de marchandises", ["707", "7097"], "produit", 2),
    ("PROD_VENDUE", "Production vendue", ["701", "702", "703", "704", "705", "706", "708", "709",
                                          "7091", "7092", "7094", "7095", "7096", "7098"], "produit", 2),
    ("CA_NET", "Montant net du chiffre d'affaires", [(1, "V_MARCH"), (1, "PROD_VENDUE")], "total", 1),
    ("PROD_STOCK", "Production stockée", ["71"], "produit", 2),
    ("PROD_IMMO", "Production immobilisée", ["72"], "produit", 2),
    ("SUBV", "Subventions", ["74"], "produit", 2),
    ("REPR_EXPL", "Reprises sur amortissements, dépréciations et provisions", ["781"], "produit", 2),
    ("CESS_PROD", "Produits des cessions d'immobilisations incorporelles et corporelles", ["757"], "produit", 2),
    ("AUT_PROD", "Autres produits", ["75"], "produit", 2),
    ("TOT_PE", "Total des produits d'exploitation (I)",
     [(1, "CA_NET"), (1, "PROD_STOCK"), (1, "PROD_IMMO"), (1, "SUBV"), (1, "REPR_EXPL"), (1, "CESS_PROD"), (1, "AUT_PROD")], "total", 1),

    ("T_CE", "Charges d'exploitation", [], "titre", 9),
    ("A_MARCH", "Achats de marchandises", ["607", "608", "6097"], "charge", 2),
    ("VAR_MARCH", "Variation de stocks (marchandises)", ["6037"], "charge", 2),
    ("A_MP", "Achats de matières premières et autres approvisionnements", ["601", "602", "6091", "6092"], "charge", 2),
    ("VAR_MP", "Variation de stocks (matières premières et approvisionnements)", ["6031", "6032"], "charge", 2),
    ("A_EXT", "Autres achats et charges externes", ["604", "605", "606", "61", "62", "6094", "6095", "6096", "6098"], "charge", 2),
    ("TAXES", "Impôts, taxes et versements assimilés", ["63"], "charge", 2),
    ("SAL", "Salaires", ["641"], "charge", 2),
    ("COTIS", "Cotisations sociales", ["645", "647", "648", "649"], "charge", 2),
    ("DOT_AMORT", "Dotations aux amortissements sur immobilisations", ["6811"], "charge", 2),
    ("DOT_DEPR_IMMO", "Dotations aux dépréciations sur immobilisations", ["6816"], "charge", 2),
    ("DOT_DEPR_AC", "Dotations aux dépréciations sur actif circulant", ["6817"], "charge", 2),
    ("DOT_PROV", "Dotations aux provisions", ["6815"], "charge", 2),
    ("VC_CESS", "Valeurs comptables des immobilisations incorporelles et corporelles cédées", ["657"], "charge", 2),
    ("AUT_CH", "Autres charges", ["65"], "charge", 2),
    ("TOT_CE", "Total des charges d'exploitation (II)",
     [(1, c) for c in ("A_MARCH", "VAR_MARCH", "A_MP", "VAR_MP", "A_EXT", "TAXES", "SAL", "COTIS", "DOT_AMORT",
                       "DOT_DEPR_IMMO", "DOT_DEPR_AC", "DOT_PROV", "VC_CESS", "AUT_CH")], "total", 1),
    ("R_EXPL", "1. Résultat d'exploitation (I - II)", [(1, "TOT_PE"), (-1, "TOT_CE")], "total", 0),

    ("QP_BEN", "Quote-part de résultat sur opérations faites en commun : bénéfice attribué ou perte transférée (III)",
     ["755"], "produit", 2),
    ("QP_PERTE", "Quote-part de résultat sur opérations faites en commun : perte supportée ou bénéfice transféré (IV)",
     ["655"], "charge", 2),

    ("T_PF", "Produits financiers", [], "titre", 9),
    ("PF_PART", "De participation", ["761"], "produit", 2),
    ("PF_VM", "D'autres valeurs mobilières et créances de l'actif immobilisé", ["762", "764"], "produit", 2),
    ("PF_INT", "Autres intérêts et produits assimilés", ["763", "765"], "produit", 2),
    ("PF_REPR", "Reprises sur dépréciations et provisions", ["786"], "produit", 2),
    ("PF_CHG", "Différences positives de change", ["766"], "produit", 2),
    ("PF_CESS_IMMO", "Produits des cessions d'immobilisations financières", ["7671", "7672"], "produit", 2),
    ("PF_CESS_VMP", "Produits nets sur cessions de valeurs mobilières de placement et d'instruments de trésorerie",
     ["7673", "7674"], "produit", 2),
    ("TOT_PF", "Total des produits financiers (V)",
     [(1, c) for c in ("PF_PART", "PF_VM", "PF_INT", "PF_REPR", "PF_CHG", "PF_CESS_IMMO", "PF_CESS_VMP")], "total", 1),

    ("T_CF", "Charges financières", [], "titre", 9),
    ("CF_DOT", "Dotations aux amortissements, aux dépréciations et aux provisions", ["686"], "charge", 2),
    ("CF_INT", "Intérêts et charges assimilées", ["661", "664", "665"], "charge", 2),
    ("CF_CHG", "Différences négatives de change", ["666"], "charge", 2),
    ("CF_VC", "Valeurs comptables des immobilisations financières cédées", ["6671", "6672"], "charge", 2),
    ("CF_CESS_VMP", "Charges nettes sur cessions de valeurs mobilières de placement et d'instruments de trésorerie",
     ["6673", "6674"], "charge", 2),
    ("TOT_CF", "Total des charges financières (VI)",
     [(1, c) for c in ("CF_DOT", "CF_INT", "CF_CHG", "CF_VC", "CF_CESS_VMP")], "total", 1),
    ("R_FIN", "2. Résultat financier (V - VI)", [(1, "TOT_PF"), (-1, "TOT_CF")], "total", 0),
    ("R_COURANT", "3. Résultat courant avant impôts (I - II + III - IV + V - VI)",
     [(1, "R_EXPL"), (1, "QP_BEN"), (-1, "QP_PERTE"), (1, "R_FIN")], "total", 0),

    ("PX", "Produits exceptionnels (VII)", ["77", "787"], "produit", 2),
    ("CX", "Charges exceptionnelles (VIII)", ["67", "687"], "charge", 2),
    ("R_EXC", "4. Résultat exceptionnel (VII - VIII)", [(1, "PX"), (-1, "CX")], "total", 0),
    ("PARTICIP", "Participation des salariés aux résultats (IX)", ["691"], "charge", 2),
    ("IS", "Impôts sur les bénéfices (X)", ["695", "696", "6981", "6989", "699"], "charge", 2),

    ("TOT_PROD", "Total des produits (I + III + V + VII)",
     [(1, "TOT_PE"), (1, "QP_BEN"), (1, "TOT_PF"), (1, "PX")], "total", 1),
    ("TOT_CH", "Total des charges (II + IV + VI + VIII + IX + X)",
     [(1, "TOT_CE"), (1, "QP_PERTE"), (1, "TOT_CF"), (1, "CX"), (1, "PARTICIP"), (1, "IS")], "total", 1),
    ("RESULTAT", "Bénéfice ou perte", [(1, "TOT_PROD"), (-1, "TOT_CH")], "total", 0),

    # Mémos (« y compris » du modèle) : calculés à part, jamais ajoutés aux postes
    ("M_CB_MOB", "dont redevances de crédit-bail mobilier (compris dans les autres achats et charges externes)",
     ["6122"], "memo", 3),
    ("M_CB_IMMO", "dont redevances de crédit-bail immobilier (compris dans les autres achats et charges externes)",
     ["6125"], "memo", 3),
]

_FEUILLES = [(c, r, s) for c, _, r, s, _ in LIGNES_CR if s in ("produit", "charge")]
_TOTAUX = [(c, r) for c, _, r, s, _ in LIGNES_CR if s == "total"]
_MEMOS = [(c, r) for c, _, r, s, _ in LIGNES_CR if s == "memo"]
SENS = {c: s for c, _, _, s, _ in LIGNES_CR}
ZERO = Decimal("0")


def ligne_du_compte(compte):
    """Code du poste d'un compte de classe 6 ou 7 (préfixe le plus long), ou None si non classé."""
    meilleur = None
    for code, prefixes, _ in _FEUILLES:
        for pref in prefixes:
            if compte.startswith(pref) and (meilleur is None or len(pref) > meilleur[1]):
                meilleur = (code, len(pref))
    return meilleur[0] if meilleur else None


def lignes_exportees():
    """Structure du modèle pour l'affichage (ordre, libellés, niveaux)."""
    return [{"code": c, "libelle": lib, "sens": s, "niveau": n} for c, lib, _, s, n in LIGNES_CR]


def _arrondi(v):
    return str(v.quantize(Decimal("0.01")))


def calculer(ecritures, dossiers, debut, fin):
    """Compte de résultat des dossiers sur [debut, fin] (dates).

    Retourne {"statut": "calculé" | "bloqué" | "non calculable", "lignes": {code: "montant"},
    "non_classes": [...], "motif": str, "reference": ..., "version": ...}.
    Les montants des dossiers sont additionnés poste par poste : à n'utiliser pour plusieurs dossiers
    que s'ils ont le même exercice (exercices décalés jamais additionnés).
    """
    dossiers = set(dossiers)
    brut, non_classes, vu, memos = {}, set(), False, {c: ZERO for c, _ in _MEMOS}
    for e in ecritures:
        if e["dossier"] not in dossiers or e["compte"][:1] not in ("6", "7"):
            continue
        if e.get("date") and not (debut <= date.fromisoformat(e["date"]) <= fin):
            continue
        vu = True
        compte = e["compte"]
        d, k = Decimal(e["debit"] or 0), Decimal(e["credit"] or 0)
        for code, prefixes in _MEMOS:
            if any(compte.startswith(p) for p in prefixes):
                memos[code] += d - k
        poste = ligne_du_compte(compte)
        if poste is None:
            non_classes.add(compte)
            continue
        montant = (k - d) if SENS[poste] == "produit" else (d - k)
        brut[poste] = brut.get(poste, ZERO) + montant
    base = {"reference": REFERENCE, "version": VERSION, "precedent": None,
            "motif_precedent": "Exercice précédent non disponible : écritures de N-1 non importées."}
    if not vu:
        return dict(base, statut="non calculable", lignes={}, non_classes=[],
                    motif="Aucune écriture de classe 6 ou 7 sur l'exercice : le résultat n'est pas égal à zéro, il est inconnu.")
    out = {}
    for code, _, _ in _FEUILLES:
        out[code] = brut.get(code, ZERO)
    for code, termes in _TOTAUX:
        out[code] = sum((sg * out[c] for sg, c in termes), ZERO)
    out.update(memos)
    statut = "bloqué" if non_classes else "calculé"
    motif = ("Comptes de classe 6 ou 7 non classés dans le modèle : " + ", ".join(sorted(non_classes))) if non_classes else ""
    return dict(base, statut=statut, lignes={c: _arrondi(v) for c, v in out.items()},
                non_classes=sorted(non_classes), motif=motif)
