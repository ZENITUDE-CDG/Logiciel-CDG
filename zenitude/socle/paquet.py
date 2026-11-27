"""Construction du paquet de données pour Claude (lot 25, décision 0019).

Entrée : les données de la page (sortie de interface/generer_site.construire, ou données assemblées en ligne),
un périmètre (liste de dossiers) et une période (premier et dernier mois, inclus).
Sortie : {nom de fichier: texte}, fichiers CSV (virgule, point décimal, UTF-8) et Markdown.

Règles (identiques dans la page, fonction socleConstruire de interface/gabarit.html) :
- uniquement des chiffres réels : écritures publiées depuis Pennylane, mesures d'exploitation importées ;
  aucun ajustement, lissage, hypothèse ni retraitement ;
- montants calculés en centimes entiers, écrits en euros avec deux décimales ;
- une donnée absente est une case vide, jamais zéro (invariant 1) ;
- les contrôles sont des constats (faits vérifiables), pas des corrections.
"""
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# --------------------------------------------------------------------------------------------------
# Définition partagée avec la page (publiée dans les données communes, clé « socle »)
# --------------------------------------------------------------------------------------------------

CONTROLES = [
    ["C01", "Mois sans données comptables", "Mois de la période non couvert par la comptabilité synchronisée."],
    ["C02", "Mois sans chiffre d’affaires", "Mois couvert sans aucune écriture sur un compte de classe 7."],
    ["C03", "Mois sans paie", "Mois couvert sans écriture sur un compte 641, alors que la résidence en a sur la période."],
    ["C04", "Fournisseur récurrent sans facture", "Fournisseur facturé au moins la moitié des mois couverts (3 au minimum), absent ce mois-ci. Montant = médiane de ses mois facturés."],
    ["C05", "Facture en double possible", "Deux pièces différentes, même fournisseur, même montant, à 5 jours d’écart au plus."],
    ["C06", "Fournisseur débiteur", "Compte fournisseur (40) à solde débiteur à la fin de la période : avoir non imputé, acompte, facture non saisie…"],
    ["C07", "Client créditeur", "Compte client (41) à solde créditeur à la fin de la période."],
    ["C08", "Compte d’attente non soldé", "Compte 47 non soldé à la fin de la période."],
    ["C09", "Virement interne non soldé", "Compte 58 non soldé à la fin de la période."],
    ["C10", "Taxe de séjour en chiffre d’affaires", "Écriture de classe 7 dont le libellé évoque la taxe de séjour (elle doit être en compte de tiers)."],
]

FICHIERS = [
    {"nom": "residences.csv", "complet": False, "groupe": False,
     "description": "Une ligne par résidence : identité, société, activité, région, exercice, groupes, couverture des données.",
     "colonnes": ["dossier", "code", "nom", "societe", "activite", "region", "marque", "ouverture", "statut",
                  "exercice_debut", "exercice_fin", "groupes", "mois_couverts_periode", "premier_mois_donnees",
                  "dernier_mois_donnees"]},
    {"nom": "cr_gestion_mensuel.csv", "complet": False, "groupe": False,
     "description": "Compte de résultat de gestion du groupe (jusqu’à l’EBITDA puis résultat net), par résidence et par mois. Montants positifs dans le sens de la ligne (produits et charges positifs).",
     "colonnes": ["dossier", "ligne", "libelle", "niveau", "mois", "montant"]},
    {"nom": "cr_gestion_periode.csv", "complet": False, "groupe": False,
     "description": "Même compte de résultat sur toute la période, comparé aux mêmes mois de l’année précédente (vide si non disponible).",
     "colonnes": ["dossier", "ligne", "libelle", "niveau", "montant_periode", "montant_n1", "ecart"]},
    {"nom": "groupe_cr_gestion.csv", "complet": False, "groupe": True,
     "description": "Somme du compte de résultat de gestion sur toutes les résidences du périmètre (période et N-1).",
     "colonnes": ["ligne", "libelle", "niveau", "montant_periode", "montant_n1", "ecart", "nb_residences"]},
    {"nom": "groupe_residences.csv", "complet": False, "groupe": True,
     "description": "Une ligne par résidence avec les totaux principaux du compte de résultat de gestion sur la période (une colonne par ligne de niveau 0 ou 1) et le nombre de contrôles.",
     "colonnes": None},
    {"nom": "balance_mensuelle.csv", "complet": False, "groupe": False,
     "description": "Mouvements de chaque compte (toutes classes) par mois de la période : débit et crédit.",
     "colonnes": ["dossier", "compte", "libelle_compte", "mois", "debit", "credit"]},
    {"nom": "balance_fin.csv", "complet": False, "groupe": False,
     "description": "Balance à la fin de la période : cumul de toutes les écritures publiées jusqu’à cette date (à-nouveaux compris).",
     "colonnes": ["dossier", "compte", "libelle_compte", "debit", "credit", "solde_debiteur"]},
    {"nom": "tiers_soldes.csv", "complet": False, "groupe": False,
     "description": "Soldes par tiers des comptes fournisseurs (40) et clients (41) à la fin de la période, part non lettrée et dernière écriture.",
     "colonnes": ["dossier", "compte", "tiers", "debit", "credit", "solde_debiteur", "non_lettre_solde_debiteur", "derniere_ecriture"]},
    {"nom": "fournisseurs_mensuel.csv", "complet": False, "groupe": False,
     "description": "Charges (classe 6, débit − crédit) de chaque pièce fournisseur, regroupées par fournisseur et par mois de la pièce (mois de comptabilisation, pas de consommation).",
     "colonnes": ["dossier", "tiers", "mois", "charges", "nb_pieces", "comptes"]},
    {"nom": "banque_mensuel.csv", "complet": False, "groupe": False,
     "description": "Comptes bancaires 512 : encaissements et décaissements du mois (hors à-nouveaux) et solde comptable à la fin du mois (à-nouveaux compris).",
     "colonnes": ["dossier", "compte", "mois", "encaissements", "decaissements", "solde_fin"]},
    {"nom": "kpi_mensuel.csv", "complet": False, "groupe": False,
     "description": "Données d’exploitation importées (KPI) par résidence et par mois, telles qu’importées.",
     "colonnes": ["dossier", "mois", "donnee", "valeur"]},
    {"nom": "controles.csv", "complet": False, "groupe": False,
     "description": "Constats automatiques (pas des retraitements) : voir la liste des contrôles ci-dessous.",
     "colonnes": ["dossier", "code", "controle", "compte", "tiers", "mois", "montant", "detail"]},
    {"nom": "ecritures.csv", "complet": True, "groupe": False,
     "description": "Toutes les lignes d’écritures de la période (grand livre).",
     "colonnes": ["dossier", "date", "journal", "piece", "ligne", "compte", "libelle_compte", "libelle", "tiers",
                  "lettrage", "echeance", "debit", "credit"]},
    {"nom": "banque_mouvements.csv", "complet": True, "groupe": False,
     "description": "Chaque mouvement des comptes 512 de la période, avec les comptes et tiers de contrepartie de la pièce. Montant = débit − crédit (positif = entrée d’argent).",
     "colonnes": ["dossier", "compte", "date", "piece", "libelle", "montant", "contreparties", "tiers"]},
]

ENTETE_MISSION = """Je joins un paquet de données Zenitude (fichier .zip) produit par le logiciel de pilotage. Lis d’abord LISEZ-MOI.md.

Règles communes à toutes les missions :
1. Les fichiers du paquet sont la seule source des chiffres réels : n’interroge pas Pennylane ni aucune autre source pour les retrouver.
2. Les hypothèses, taux, scénarios et retraitements sont uniquement ceux de la mission ci-dessous ; s’il en manque un, prends une hypothèse prudente, écris-la et signale-la.
3. Chaque document produit commence par un cartouche : référence du paquet, empreinte des données, mission (code et version), périmètre, période, date.
4. Chaque chiffre est sourcé : fichier du paquet et ligne (ou filtre) d’où il vient, ou hypothèse de la mission, ou calcul avec sa formule. Distingue constaté, estimé et à confirmer.
5. Chaque document se termine par une section « Sources et hypothèses » : fichiers utilisés, hypothèses appliquées, contrôles automatiques retenus ou écartés et pourquoi.
6. Signale toute incohérence entre les fichiers au lieu de la corriger en silence.
7. Pour un groupe, applique la même méthode à chaque résidence, puis consolide à partir des fichiers groupe_* ; ne traite pas les résidences une par une dans des échanges séparés."""

LISEZ_MOI = """# Paquet de données Zenitude pour Claude

- Périmètre : {{perimetre}} ({{nb_residences}} résidence(s))
- Période : {{debut}} à {{fin}} (mois inclus)
- Niveau : {{niveau}}
- Généré le : {{genere_le}} par {{auteur}}
- Configuration : version {{version_config}} ; dernier mois importé : {{dernier_mois}}
- Référence du paquet : {{reference}} ; empreinte des données : {{empreinte}}

## Règles pour Claude

1. Ces fichiers sont la seule source des chiffres réels. N’interroge pas Pennylane ni aucune autre source pour les retrouver.
2. Les hypothèses, taux, scénarios et retraitements viennent uniquement de la mission (MISSION.md ou message joint), jamais de ces fichiers.
3. Si tu as besoin d’un agrégat absent, calcule-le à partir de ces fichiers et donne la formule et les fichiers utilisés.
4. Une case vide signifie « donnée non disponible », jamais zéro.
5. controles.csv liste des constats automatiques, pas des corrections : qualifie-les (anomalie, normal, à vérifier) selon la mission.
6. Signale toute incohérence entre fichiers au lieu de la corriger en silence.
7. Cite la référence du paquet et l’empreinte des données dans chaque document produit, et source chaque chiffre (fichier et ligne).

## Conventions

- Montants en euros hors taxes tels que comptabilisés, point décimal, deux décimales, sans séparateur de milliers.
- debit et credit sont positifs ; solde_debiteur = débit − crédit (négatif = solde créditeur).
- Comptes de résultat de gestion (cr_gestion_*) : format du compte de résultat de gestion du groupe ; produits et charges en positif dans le sens de leur ligne ; les totaux sont calculés par le logiciel.
- Mois au format AAAA-MM, dates au format AAAA-MM-JJ. Écritures datées après le dernier mois importé = écritures anticipées déjà saisies dans Pennylane.
- Chiffres réels uniquement : écritures synchronisées depuis Pennylane et données d’exploitation importées, sans ajustement, lissage ni retraitement du logiciel.

## Fichiers

{{fichiers}}

## Résidences

{{residences}}

## Contrôles automatiques

{{controles}}
"""

LIGNES_GROUPE_NIVEAU_MAX = 1
RE_TAXE_SEJOUR = re.compile(r"taxe\s*(de\s*)?s[eéEÉ]jour", re.IGNORECASE)


def definition():
    """Définition publiée pour la page (données communes) : fichiers, contrôles, modèles de texte."""
    return {"fichiers": FICHIERS, "controles": CONTROLES, "lisez_moi": LISEZ_MOI, "entete_mission": ENTETE_MISSION}


# --------------------------------------------------------------------------------------------------
# Outils (mêmes règles d'écriture que la page)
# --------------------------------------------------------------------------------------------------

def euros(c):
    """Centimes entiers -> texte « 1234.56 » (« -0.05 »). None -> vide."""
    if c is None:
        return ""
    s = "-" if c < 0 else ""
    a = abs(c)
    return f"{s}{a // 100}.{a % 100:02d}"


def nombre(v):
    """Valeur d'exploitation -> texte (entier sans décimale, sinon écriture courte)."""
    if v is None or v == "":
        return ""
    x = float(v)
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return repr(x)


def centimes(texte):
    return int((Decimal(str(texte)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def champ(v):
    s = "" if v is None else str(v)
    if any(ch in s for ch in ",\"\n\r"):
        s = '"' + s.replace('"', '""') + '"'
    return s


def csv(colonnes, lignes):
    out = [",".join(colonnes)]
    for l in lignes:
        out.append(",".join(champ(x) for x in l))
    return "\n".join(out) + "\n"


def fin_de_mois(m):
    a, mo = int(m[:4]), int(m[5:7])
    suivant = date(a + (mo == 12), mo % 12 + 1, 1)
    return (suivant - timedelta(days=1)).isoformat()


def moins_douze(m):
    return f"{int(m[:4]) - 1:04d}-{m[5:7]}"


def ecart_jours(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def empreinte(fichiers):
    """SHA-256 des fichiers de données (CSV, dans l'ordre du paquet) : « nom\ntexte » de chacun, à la suite.
    Même calcul dans la page (socleEmpreinte) ; identifie les données exactes utilisées par un document."""
    import hashlib
    h = hashlib.sha256()
    for nom, texte in fichiers:
        h.update((nom + "\n" + texte).encode("utf-8"))
    return h.hexdigest()


def texte_mission(mission, reference="", emp=""):
    """MISSION.md : titre, code et version, référence du paquet, règles communes, consignes, livrables."""
    t = "# Mission : " + mission["titre"] + "\n\n"
    t += "- Code : " + (mission.get("code") or "—") + " ; version " + str(mission.get("version") or 1) + "\n"
    t += "- Référence du paquet : " + (reference or "—") + " ; empreinte des données : " + (emp or "—") + "\n\n"
    t += ENTETE_MISSION + "\n\n## Consignes\n\n" + mission["consignes"].rstrip("\n") + "\n"
    if (mission.get("livrables") or "").strip():
        t += "\n## Livrables attendus\n\n" + mission["livrables"].rstrip("\n") + "\n"
    return t


def tableau_md(entetes, lignes):
    t = ["| " + " | ".join(entetes) + " |", "|" + "|".join(" --- " for _ in entetes) + "|"]
    for l in lignes:
        t.append("| " + " | ".join(str(x).replace("|", "/") for x in l) + " |")
    return "\n".join(t)


# --------------------------------------------------------------------------------------------------
# Compte de résultat de gestion (mêmes règles que la page : ligneDuCompte, calcLignes)
# --------------------------------------------------------------------------------------------------

def ligne_du_compte(compte, lignes, libelle):
    exact, mot, best = None, None, None
    for l in lignes:
        for p in (l["regle"].get("prefixes") or []):
            if p.startswith("="):
                if compte == p[1:]:
                    exact = l["code"]
                continue
            if ":" in p and p.index(":") > 0:
                pr, w = p.split(":", 1)
                if libelle and compte.startswith(pr) and w in libelle and (mot is None or len(pr) > mot[1]):
                    mot = (l["code"], len(pr))
                continue
            if compte.startswith(p) and (best is None or len(p) > best[1]):
                best = (l["code"], len(p))
    return exact or (mot[0] if mot else None) or (best[0] if best else None)


def calc_lignes(lignes, valeurs):
    out, defs = {}, {l["code"]: l for l in lignes}

    def val(code):
        if code in out:
            return out[code]
        l = defs[code]
        if l["regle"].get("prefixes") is not None:
            v = valeurs.get(code)
            out[code] = None if v is None else (v if l["sens"] == "produit" else -v)
        else:
            t = [(x[0], val(x[1])) for x in l["regle"]["termes"]]
            if all(x[1] is None for x in t):
                out[code] = None
            else:
                out[code] = sum((x[1] or 0) * x[0] for x in t)
        return out[code]

    for l in lignes:
        val(l["code"])
    return out


# --------------------------------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------------------------------

def construire(donnees, dossiers, debut, fin, complet=True, genere_le="", auteur="", perimetre="",
               mission=None, exploitation=None, reference=""):
    """Fichiers du paquet {nom: texte}. dossiers : liste de dossiers ; debut, fin : « AAAA-MM » inclus.

    exploitation : {dossier: {mois: {donnée: valeur}}} (par défaut celle des données publiées).
    mission : {"titre", "consignes", "code", "version", "livrables"} ou None ; reference : référence du paquet
    (journal partagé, « PQ-000123 »), citée dans LISEZ-MOI.md et MISSION.md.
    """
    calcul = donnees["calcul"]
    tous_mois = calcul["mois"]
    mois = [m for m in tous_mois if debut <= m <= fin]
    if not mois:
        raise ValueError("période vide")
    date_fin = fin_de_mois(mois[-1])
    date_debut = mois[0] + "-01"
    dossiers = sorted(set(dossiers))
    res = {r["dossier"]: r for r in donnees["residences"]}
    for d in dossiers:
        if d not in res:
            raise ValueError(f"dossier inconnu : {d}")
    exploitation = exploitation if exploitation is not None else calcul["exploitation"]
    libelles = calcul.get("libelles_comptes") or {}
    lib_maj = {p["compte"]: str(p["libelle_compte"]).upper() for p in donnees.get("plan", []) if p.get("libelle_compte")}
    lignes_cr = donnees["lignes_ebitda"]
    groupe = len(dossiers) > 1

    def libelle_compte(c):
        for i in range(len(c), 2, -1):
            if libelles.get(c[:i]):
                return libelles[c[:i]]
        return ""

    cache_ligne = {}

    def ligne_de(c):
        if c not in cache_ligne:
            cache_ligne[c] = ligne_du_compte(c, lignes_cr, lib_maj.get(c, ""))
        return cache_ligne[c]

    t = {k: [] for k in ("residences", "cr_m", "cr_p", "bal_m", "bal_f", "tiers", "fourn", "banque", "kpi",
                         "controles", "ecritures", "bq_mvt")}
    cr_periode_par_d = {}
    nb_ctrl = {}

    for d in dossiers:
        r = res[d]
        ecr = donnees["ecritures"].get(d, [])
        couverts = sorted(calcul["couverts"].get(d, []))
        couverts_p = [m for m in mois if m in set(couverts)]
        groupes = [p["libelle"] for p in donnees["perimetres"]
                   if p["type"] in ("groupe-cree", "region", "activite") and d in p["dossiers"]]
        ex = r.get("exercice") or ["", ""]
        t["residences"].append([d, r.get("code", ""), r.get("nom", ""), r.get("societe", ""), r.get("activite", ""),
                                r.get("region", ""), r.get("marque", ""), r.get("ouverture", ""), r.get("statut", ""),
                                ex[0] or "", ex[1] or "", " | ".join(groupes), len(couverts_p),
                                couverts[0] if couverts else "", couverts[-1] if couverts else ""])

        # Compte de résultat de gestion
        compta = calcul["compta"].get(d, {})

        def brut_de(ms):
            b = {}
            for m in ms:
                for c, v in (compta.get(m) or {}).items():
                    l = ligne_de(c)
                    if l is None:
                        continue
                    b[l] = b.get(l, 0) + centimes(v)
            return b

        for m in mois:
            vals = calc_lignes(lignes_cr, brut_de([m]))
            for l in lignes_cr:
                v = vals[l["code"]]
                if v is not None:
                    t["cr_m"].append([d, l["code"], l["libelle"], l["niveau"], m, euros(v)])
        per = calc_lignes(lignes_cr, brut_de(mois))
        m1 = [moins_douze(m) for m in mois]
        n1 = calc_lignes(lignes_cr, brut_de(m1)) if all(m in tous_mois for m in m1) else None
        cr_periode_par_d[d] = (per, n1)
        for l in lignes_cr:
            v, w = per[l["code"]], (n1 or {}).get(l["code"])
            if v is None and w is None:
                continue
            t["cr_p"].append([d, l["code"], l["libelle"], l["niveau"], euros(v), euros(w),
                              euros(v - w) if v is not None and w is not None else ""])

        # Index des écritures
        dans_periode = [e for e in ecr if date_debut <= e[1] <= date_fin]
        jusqua_fin = [e for e in ecr if e[1] <= date_fin]
        pieces = {}
        for e in ecr:
            pieces.setdefault(e[3], []).append(e)

        # Balance mensuelle et balance à la fin
        bm = {}
        for e in dans_periode:
            k = (e[4], e[1][:7])
            x = bm.setdefault(k, [0, 0])
            if e[6] < 0:
                x[0] += -e[6]
            else:
                x[1] += e[6]
        for (c, m) in sorted(bm):
            x = bm[(c, m)]
            t["bal_m"].append([d, c, libelle_compte(c), m, euros(x[0]), euros(x[1])])
        bf = {}
        for e in jusqua_fin:
            x = bf.setdefault(e[4], [0, 0])
            if e[6] < 0:
                x[0] += -e[6]
            else:
                x[1] += e[6]
        for c in sorted(bf):
            x = bf[c]
            t["bal_f"].append([d, c, libelle_compte(c), euros(x[0]), euros(x[1]), euros(x[0] - x[1])])

        controles = []

        def ctrl(code, compte="", tiers="", m="", montant=None, detail=""):
            lib = next(x[1] for x in CONTROLES if x[0] == code)
            controles.append([d, code, lib, compte, tiers, m, euros(montant), detail])

        # Tiers
        ti = {}
        for e in jusqua_fin:
            if not (e[4].startswith("40") or e[4].startswith("41")) or not e[7]:
                continue
            x = ti.setdefault((e[4], e[7]), [0, 0, 0, ""])
            if e[6] < 0:
                x[0] += -e[6]
            else:
                x[1] += e[6]
            if not e[8]:
                x[2] += -e[6]
            if e[1] > x[3]:
                x[3] = e[1]
        for (c, tr) in sorted(ti):
            x = ti[(c, tr)]
            solde = x[0] - x[1]
            if solde == 0 and x[2] == 0:
                continue
            t["tiers"].append([d, c, tr, euros(x[0]), euros(x[1]), euros(solde), euros(x[2]), x[3]])

        # Fournisseurs par mois (pièces de la période ayant une ligne 40 avec tiers)
        fo = {}
        for p in sorted(pieces):
            ls = pieces[p]
            if not (date_debut <= ls[0][1] <= date_fin):
                continue
            tr = next((e[7] for e in ls if e[4].startswith("40") and e[7]), None)
            charges = [e for e in ls if e[4].startswith("6")]
            if not tr or not charges:
                continue
            x = fo.setdefault((tr, ls[0][1][:7]), [0, 0, set()])
            x[0] += sum(-e[6] for e in charges)
            x[1] += 1
            x[2].update(e[4] for e in charges)
        for (tr, m) in sorted(fo):
            x = fo[(tr, m)]
            t["fourn"].append([d, tr, m, euros(x[0]), x[1], "|".join(sorted(x[2]))])

        # Banque mensuelle
        comptes_bq = sorted({e[4] for e in jusqua_fin if e[4].startswith("512")})
        for c in comptes_bq:
            lignes_c = [e for e in ecr if e[4] == c]
            for m in mois:
                enc = sum(-e[6] for e in lignes_c if e[1][:7] == m and e[6] < 0 and e[2] != "AN")
                dec = sum(e[6] for e in lignes_c if e[1][:7] == m and e[6] > 0 and e[2] != "AN")
                solde = sum(-e[6] for e in lignes_c if e[1] <= fin_de_mois(m))
                t["banque"].append([d, c, m, euros(enc), euros(dec), euros(solde)])

        # KPI
        ex_d = exploitation.get(d, {})
        for m in mois:
            for k in sorted((ex_d.get(m) or {}).keys()):
                v = ex_d[m][k]
                if v is None or v == "":
                    continue
                t["kpi"].append([d, m, k, nombre(v)])

        # Contrôles C01 à C03
        for m in mois:
            if m not in couverts_p:
                ctrl("C01", m=m, detail="aucune donnée comptable synchronisée pour ce mois")
        mois_avec = {}
        for e in dans_periode:
            mois_avec.setdefault(e[1][:7], set()).add(e[4][:3] if e[4].startswith("641") else e[4][:1])
        for m in couverts_p:
            if "7" not in mois_avec.get(m, set()):
                ctrl("C02", m=m, detail="aucune écriture de classe 7")
        if any(e[4].startswith("641") for e in dans_periode):
            for m in couverts_p:
                if "641" not in mois_avec.get(m, set()):
                    ctrl("C03", compte="641", m=m, detail="aucune écriture 641 ce mois")

        # C04 : fournisseur récurrent sans facture
        n = len(couverts_p)
        if n >= 3:
            par_tiers = {}
            for (tr, m), x in fo.items():
                if m in couverts_p:
                    par_tiers.setdefault(tr, {})[m] = x[0]
            seuil = max(3, (n + 1) // 2)
            for tr in sorted(par_tiers):
                ms = par_tiers[tr]
                k = len(ms)
                if k < seuil or k >= n:
                    continue
                vals = sorted(ms.values())
                med = vals[(k - 1) // 2]
                for m in couverts_p:
                    if m not in ms:
                        ctrl("C04", tiers=tr, m=m, montant=med, detail=f"facturé {k} mois sur {n} ; montant = médiane des mois facturés")

        # C05 : doublons possibles
        fact = [e for e in ecr if e[4].startswith("40") and e[7] and e[6] > 0 and e[2] != "AN" and e[1] <= date_fin]
        grp = {}
        for e in fact:
            grp.setdefault((e[7], e[6]), []).append(e)
        for (tr, mt) in sorted(grp):
            ls = sorted(grp[(tr, mt)], key=lambda e: (e[1], e[3]))
            for a, b in zip(ls, ls[1:]):
                if a[3] != b[3] and ecart_jours(a[1], b[1]) <= 5 and b[1] >= date_debut:
                    ctrl("C05", compte=b[4], tiers=tr, m=b[1][:7], montant=mt,
                         detail=f"pièces {a[3]} ({a[1]}) et {b[3]} ({b[1]})")

        # C06 à C09 : soldes à la fin
        for (c, tr) in sorted(ti):
            x = ti[(c, tr)]
            solde = x[0] - x[1]
            if c.startswith("40") and solde > 0:
                ctrl("C06", compte=c, tiers=tr, m=mois[-1], montant=solde, detail="solde débiteur à la fin de la période")
            if c.startswith("41") and solde < 0:
                ctrl("C07", compte=c, tiers=tr, m=mois[-1], montant=solde, detail="solde créditeur à la fin de la période")
        for c in sorted(bf):
            solde = bf[c][0] - bf[c][1]
            if solde != 0 and c.startswith("47"):
                ctrl("C08", compte=c, m=mois[-1], montant=solde, detail="solde débiteur (négatif = créditeur) à la fin de la période")
            if solde != 0 and c.startswith("58"):
                ctrl("C09", compte=c, m=mois[-1], montant=solde, detail="solde débiteur (négatif = créditeur) à la fin de la période")

        # C10 : taxe de séjour en CA
        ts = {}
        for e in dans_periode:
            if e[4].startswith("7") and (RE_TAXE_SEJOUR.search(e[5] or "") or RE_TAXE_SEJOUR.search(libelle_compte(e[4]))):
                k = (e[4], e[1][:7])
                ts[k] = ts.get(k, 0) + e[6]
        for (c, m) in sorted(ts):
            ctrl("C10", compte=c, m=m, montant=ts[(c, m)], detail="montant crédit − débit des écritures concernées")

        t["controles"] += controles
        nb_ctrl[d] = len(controles)

        if complet:
            for e in dans_periode:
                t["ecritures"].append([d, e[1], e[2], e[3], e[0], e[4], libelle_compte(e[4]), e[5], e[7], e[8], e[9],
                                       euros(-e[6] if e[6] < 0 else 0), euros(e[6] if e[6] > 0 else 0)])
            for e in dans_periode:
                if not e[4].startswith("512"):
                    continue
                autres = [x for x in pieces[e[3]] if x[0] != e[0]]
                t["bq_mvt"].append([d, e[4], e[1], e[3], e[5], euros(-e[6]),
                                    "|".join(sorted({x[4] for x in autres})), "|".join(sorted({x[7] for x in autres if x[7]}))])

    # Fichiers
    defs = {f["nom"]: f for f in FICHIERS}
    out = {}

    def ecrire(nom, lignes, colonnes=None):
        out[nom] = csv(colonnes or defs[nom]["colonnes"], lignes)
        return len(lignes)

    nb = {}
    nb["residences.csv"] = ecrire("residences.csv", t["residences"])
    nb["cr_gestion_mensuel.csv"] = ecrire("cr_gestion_mensuel.csv", t["cr_m"])
    nb["cr_gestion_periode.csv"] = ecrire("cr_gestion_periode.csv", t["cr_p"])
    if groupe:
        g = []
        for l in lignes_cr:
            vs = [cr_periode_par_d[d][0][l["code"]] for d in dossiers]
            ws = [(cr_periode_par_d[d][1] or {}).get(l["code"]) for d in dossiers]
            n1_dispo = all(cr_periode_par_d[d][1] is not None for d in dossiers)
            v = None if all(x is None for x in vs) else sum(x or 0 for x in vs)
            w = None if (not n1_dispo or all(x is None for x in ws)) else sum(x or 0 for x in ws)
            if v is None and w is None:
                continue
            g.append([l["code"], l["libelle"], l["niveau"], euros(v), euros(w),
                      euros(v - w) if v is not None and w is not None else "", sum(1 for x in vs if x is not None)])
        nb["groupe_cr_gestion.csv"] = ecrire("groupe_cr_gestion.csv", g)
        principales = [l for l in lignes_cr if l["niveau"] <= LIGNES_GROUPE_NIVEAU_MAX]
        cols = ["dossier", "nom", "activite"] + [l["code"] for l in principales] + ["nb_controles"]
        gr = []
        for d in dossiers:
            per = cr_periode_par_d[d][0]
            gr.append([d, res[d].get("nom", ""), res[d].get("activite", "")] + [euros(per[l["code"]]) for l in principales] + [nb_ctrl[d]])
        nb["groupe_residences.csv"] = ecrire("groupe_residences.csv", gr, cols)
    for nom, cle in (("balance_mensuelle.csv", "bal_m"), ("balance_fin.csv", "bal_f"), ("tiers_soldes.csv", "tiers"),
                     ("fournisseurs_mensuel.csv", "fourn"), ("banque_mensuel.csv", "banque"), ("kpi_mensuel.csv", "kpi"),
                     ("controles.csv", "controles")):
        nb[nom] = ecrire(nom, t[cle])
    if complet:
        nb["ecritures.csv"] = ecrire("ecritures.csv", t["ecritures"])
        nb["banque_mouvements.csv"] = ecrire("banque_mouvements.csv", t["bq_mvt"])

    # LISEZ-MOI et mission
    fichiers_md = tableau_md(["Fichier", "Lignes", "Contenu"],
                             [[f["nom"], nb[f["nom"]], f["description"]] for f in FICHIERS if f["nom"] in nb])
    residences_md = tableau_md(["Dossier", "Résidence", "Activité", "Mois couverts", "Contrôles"],
                               [[x[0], x[2], x[4], f"{x[12]} / {len(mois)}", nb_ctrl[x[0]]] for x in t["residences"]])
    compte = {}
    for x in t["controles"]:
        compte[x[1]] = compte.get(x[1], 0) + 1
    controles_md = tableau_md(["Code", "Contrôle", "Nombre", "Définition"],
                              [[c[0], c[1], compte.get(c[0], 0), c[2]] for c in CONTROLES])
    valeurs = {
        "perimetre": perimetre or (res[dossiers[0]].get("nom", dossiers[0]) if not groupe else "Sélection"),
        "nb_residences": str(len(dossiers)), "debut": mois[0], "fin": mois[-1],
        "niveau": "complet (avec écritures et mouvements bancaires)" if complet else "synthèse (sans le détail des écritures)",
        "genere_le": genere_le, "auteur": auteur or "—",
        "version_config": str(donnees["meta"].get("version_config", "")),
        "dernier_mois": str(donnees["meta"].get("dernier_mois_importe", "")),
        "reference": reference or "—", "empreinte": empreinte(list(out.items())),
        "fichiers": fichiers_md, "residences": residences_md, "controles": controles_md,
    }
    texte = LISEZ_MOI
    for k, v in valeurs.items():
        texte = texte.replace("{{" + k + "}}", v)
    resultat = {"LISEZ-MOI.md": texte}
    if mission:
        resultat["MISSION.md"] = texte_mission(mission, reference or "—", valeurs["empreinte"])
    resultat.update(out)
    return resultat
