"""Lot 24 - CA par résidence et FEES à refacturer depuis le siège (décision 0018).

Référence Python des calculs que la page refait dans le navigateur (`interface/gabarit.html`,
« Lot 24 : comptabilité »). Un test compare les deux sur les données de démonstration
(`tests/test_lot24_page.py`). Mêmes règles des deux côtés :

CA d'une résidence pour un mois
    Somme, en crédit - débit, des comptes qui commencent par un préfixe « inclus » et par aucun préfixe
    « exclu » de la règle de CA de la résidence. Règle de la résidence si elle existe, sinon règle du
    groupe (dossier « * »), sinon tous les comptes 7. Mois sans aucune écriture de classe 6 ou 7 :
    non calculable (jamais zéro).

Rubriques de refacturation
    Une rubrique a pour base le CA (elle compte dans le total refacturé : droit de marque, management
    fees...) ou une autre rubrique de base CA (répartition : compta, communication... en % des
    management fees ; elle ne compte pas dans le total, elle le détaille).

Règles datées (versions)
    Une règle = rubrique, dossier (ou « * » pour le groupe), mois d'effet, mode :
      - « taux »    : valeur en % de la base ;
      - « montant » : montant brut mensuel en euros ;
      - « groupe »  : la résidence revient à la règle du groupe à partir de ce mois.
    Pour un mois M : la règle de la résidence en vigueur (mois d'effet le plus récent <= M) l'emporte,
    sauf si elle est en mode « groupe » ; sinon la règle du groupe en vigueur ; sinon « non paramétré »
    (affiché comme tel, jamais 0). Une nouvelle version ne change que les mois à partir de son effet ;
    les mois clôturés gardent leur instantané.

Arrondi
    Montants en centimes. Taux à quatre décimales au plus. Montant = base x taux / 100 arrondi au
    centime, demi-centime loin de zéro. Une répartition se calcule sur le montant arrondi de sa base
    (le montant refacturé).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TOUS = "*"
REGLE_CA_DEFAUT = {"inclus": ["7"], "exclus": []}

# Rubriques et règles de départ (tableau de refacturation du siège, novembre 2026). Source unique :
# la migration 015 en est tirée (sql_amorce, vérifié par tests/test_lot24_fees.py) et la page locale les reçoit.
RUBRIQUES_DEPART = [
    {"code": "DROIT_MARQUE", "libelle": "Droit de marque", "base": "CA", "base_rubrique": None, "ordre": 10},
    {"code": "MGT_FEES", "libelle": "Management fees", "base": "CA", "base_rubrique": None, "ordre": 20},
    {"code": "COMPTA", "libelle": "Compta", "base": "RUBRIQUE", "base_rubrique": "MGT_FEES", "ordre": 30},
    {"code": "COMMUNICATION", "libelle": "Communication", "base": "RUBRIQUE", "base_rubrique": "MGT_FEES", "ordre": 40},
    {"code": "COMMERCIAL", "libelle": "Commercial", "base": "RUBRIQUE", "base_rubrique": "MGT_FEES", "ordre": 50},
    {"code": "GERANCE", "libelle": "Gérance", "base": "RUBRIQUE", "base_rubrique": "MGT_FEES", "ordre": 60},
    {"code": "SUIVI_EXPLOITATION", "libelle": "Suivi exploitation", "base": "RUBRIQUE", "base_rubrique": "MGT_FEES", "ordre": 70},
]
EFFET_DEPART = "2025-01"
REGLES_DEPART = [
    {"rubrique": "MGT_FEES", "dossier": TOUS, "mois_effet": EFFET_DEPART, "mode": "taux", "valeur": "8"},
    {"rubrique": "COMPTA", "dossier": TOUS, "mois_effet": EFFET_DEPART, "mode": "taux", "valeur": "40"},
    {"rubrique": "COMMUNICATION", "dossier": TOUS, "mois_effet": EFFET_DEPART, "mode": "taux", "valeur": "20"},
    {"rubrique": "COMMERCIAL", "dossier": TOUS, "mois_effet": EFFET_DEPART, "mode": "taux", "valeur": "20"},
    {"rubrique": "GERANCE", "dossier": TOUS, "mois_effet": EFFET_DEPART, "mode": "taux", "valeur": "15"},
    {"rubrique": "SUIVI_EXPLOITATION", "dossier": TOUS, "mois_effet": EFFET_DEPART, "mode": "taux", "valeur": "5"},
]


def _cents(x) -> int:
    return int((Decimal(str(x)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def appliquer_taux(base: int, taux) -> int:
    """base (centimes) x taux % arrondi au centime, demi loin de zéro ; taux à 4 décimales."""
    t = Decimal(str(taux)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return int((Decimal(base) * t / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def regle_ca(regles_ca: list[dict], dossier: str) -> dict:
    propre = [r for r in regles_ca if r["dossier"] == dossier]
    groupe = [r for r in regles_ca if r["dossier"] == TOUS]
    r = (propre or groupe or [REGLE_CA_DEFAUT])[0]
    return {"inclus": list(r.get("inclus") or []), "exclus": list(r.get("exclus") or []),
            "source": "résidence" if propre else "groupe" if groupe else "défaut"}


def compte_retenu(compte: str, regle: dict) -> bool:
    return any(compte.startswith(p) for p in regle["inclus"]) and not any(compte.startswith(p) for p in regle["exclus"])


def ca_mois(compta_dossier: dict, mois: str, regle: dict):
    """compta_dossier : {mois: {compte: montant crédit - débit (texte ou Decimal, euros)}}. Centimes ou None."""
    if mois not in compta_dossier:
        return None
    return sum(_cents(v) for c, v in compta_dossier[mois].items() if compte_retenu(c, regle))


def regle_applicable(regles: list[dict], rubrique: str, dossier: str, mois: str):
    def derniere(d):
        xs = [r for r in regles if r["rubrique"] == rubrique and r["dossier"] == d and r["mois_effet"] <= mois]
        return max(xs, key=lambda r: r["mois_effet"]) if xs else None
    propre = derniere(dossier)
    if propre and propre["mode"] != "groupe":
        return propre
    return derniere(TOUS)


def calculer(rubriques: list[dict], regles: list[dict], ca, dossier: str, mois: str) -> dict:
    """Montant de chaque rubrique active pour une résidence et un mois. ca : centimes ou None."""
    actives = sorted([r for r in rubriques if r.get("actif", True)], key=lambda r: (r["ordre"], r["code"]))
    par_code = {r["code"]: r for r in rubriques}
    sortie, montants = [], {}

    def montant(rub):
        if rub["code"] in montants:
            return montants[rub["code"]]
        r = regle_applicable(regles, rub["code"], dossier, mois)
        if r is None:
            res = {"montant": None, "motif": "non paramétré", "regle": None}
        elif r["mode"] == "montant":
            res = {"montant": _cents(r["valeur"]), "motif": None, "regle": r}
        else:
            if rub["base"] == "CA":
                base = ca
                motif = "CA non calculable (aucune écriture ce mois)"
            else:
                parent = par_code.get(rub["base_rubrique"])
                base = montant(parent)["montant"] if parent and parent.get("actif", True) else None
                motif = "base non calculable"
            res = {"montant": None if base is None else appliquer_taux(base, r["valeur"]),
                   "motif": motif if base is None else None, "regle": r}
        montants[rub["code"]] = res
        return res

    total = 0
    for rub in actives:
        x = montant(rub)
        r = x["regle"]
        sortie.append({"code": rub["code"], "libelle": rub["libelle"], "base": rub["base"], "base_rubrique": rub.get("base_rubrique"),
                       "mode": r["mode"] if r else None, "valeur": str(r["valeur"]) if r and r["valeur"] is not None else None,
                       "effet": r["mois_effet"] if r else None, "dossier_regle": r["dossier"] if r else None,
                       "montant": x["montant"], "motif": x["motif"]})
        if rub["base"] == "CA" and x["montant"] is not None:
            total += x["montant"]
    return {"ca": ca, "lignes": sortie, "total": total}


def instantane(rubriques, regles, regles_ca, compta_dossier, dossier, mois) -> dict:
    """Contenu figé d'une clôture (table fees_clotures) : CA, règle de CA, montants et règles appliquées."""
    rc = regle_ca(regles_ca, dossier)
    ca = ca_mois(compta_dossier, mois, rc)
    res = calculer(rubriques, regles, ca, dossier, mois)
    res["regle_ca"] = {"inclus": rc["inclus"], "exclus": rc["exclus"]}
    return res


def _lit(v):
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def sql_amorce() -> str:
    """Bloc d'amorce de la migration 015 (rubriques et règles de départ)."""
    lignes = ["INSERT INTO fees_rubriques (code, libelle, base, base_rubrique, ordre) VALUES"]
    lignes.append(",\n".join(f"  ({_lit(r['code'])}, {_lit(r['libelle'])}, {_lit(r['base'])}, {_lit(r['base_rubrique'])}, {r['ordre']})"
                             for r in RUBRIQUES_DEPART) + "\nON CONFLICT (code) DO NOTHING;")
    lignes.append("INSERT INTO fees_regles (rubrique, dossier, mois_effet, mode, valeur) VALUES")
    lignes.append(",\n".join(f"  ({_lit(r['rubrique'])}, {_lit(r['dossier'])}, {_lit(r['mois_effet'])}, {_lit(r['mode'])}, {r['valeur']})"
                             for r in REGLES_DEPART) + "\nON CONFLICT (rubrique, dossier, mois_effet) DO NOTHING;")
    return "\n".join(lignes) + "\n"
