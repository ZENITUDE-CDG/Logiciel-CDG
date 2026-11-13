"""Aperçu des impacts entre deux versions du classeur (lot 2).

Compare les règles par clé métier. Une modification de clé (ex. changement de date d'effet)
apparaît comme un retrait et un ajout : c'est volontaire, une règle datée est une version.
"""
from datetime import date, datetime

from . import controles as c

CLES = {
    "Referentiel": ["Identifiant interne", "Date d'effet"],
    "Rubriques": ["Code rubrique", "Dossier Pennylane (ou * pour tous)", "Préfixe ou plage de comptes",
                  "Agrégat de base", "Date d'effet"],
    "KPI": ["Code KPI", "Date d'effet"],
    "Groupes": ["Code groupe", "Date d'effet"],
    "Scenarios": ["Scénario", "Résidence ou groupe", "Poste (rubrique)", "Période début", "Date d'effet"],
    "Seuils": ["Code seuil"],
    "Rapports": ["Code rapport"],
}


def _norm(v):
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return (v.date() if isinstance(v, datetime) else v).isoformat()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            return c._date(s).isoformat()
        except ValueError:
            return s
    return v


def _cle(row, champs):
    return tuple("" if _norm(row.get(h)) is None else str(_norm(row.get(h))).strip().upper() for h in champs)


def _lire_lignes(chemin):
    """Charge les règles sans contrôle (la validité est calculée séparément)."""
    rap = c.Rapport(chemin=str(chemin))
    ctx = c._Ctx(rap, set(), None)
    c._lire(ctx, chemin)
    return ctx.feuilles


def comparer(ancien, nouveau):
    """Retourne un dict : validité des deux versions et liste des changements par onglet."""
    rapport_a = c.verifier(ancien)
    rapport_n = c.verifier(nouveau)
    feuilles_a = _lire_lignes(ancien)
    feuilles_n = _lire_lignes(nouveau)
    changements = []
    for onglet, champs in CLES.items():
        lignes_a = feuilles_a.get(onglet, [])
        lignes_n = feuilles_n.get(onglet, [])
        idx_a = {_cle(r, champs): r for r in lignes_a}
        idx_n = {_cle(r, champs): r for r in lignes_n}
        for k, r in idx_n.items():
            if k not in idx_a:
                changements.append(_chg(onglet, "ajout", k, champs, None, r))
            else:
                diff = _champs_modifies(idx_a[k], r)
                if diff:
                    changements.append(_chg(onglet, "modification", k, champs, diff, r))
        for k, r in idx_a.items():
            if k not in idx_n:
                changements.append(_chg(onglet, "retrait", k, champs, None, r))
    return {
        "ancienne_version_valide": not rapport_a.erreurs,
        "nouvelle_version_valide": not rapport_n.erreurs,
        "erreurs_nouvelle_version": [str(e) for e in rapport_n.erreurs],
        "changements": changements,
        "resume": _resume(changements),
    }


def _champs_modifies(a, b):
    out = {}
    for h in a:
        if h == "_ligne" or h == "Contrôle" or h.startswith("Contrôle"):
            continue
        va, vb = _norm(a.get(h)), _norm(b.get(h))
        if va != vb:
            out[h] = {"avant": va, "après": vb}
    return out


def _chg(onglet, type_, cle, champs, diff, ligne):
    # Affichage : valeurs d'origine de la ligne (la clé de comparaison est normalisée en majuscules)
    affichage = {h: _norm(ligne.get(h)) for h in champs}
    return {
        "onglet": onglet,
        "type": type_,
        "cle": affichage,
        "champs": diff or {},
        "ligne_nouvelle": ligne.get("_ligne") if type_ != "retrait" else None,
        "archivage": bool(diff and "Statut" in diff and str(diff["Statut"]["après"]).strip() == "archivé"),
    }


def _resume(changements):
    out = {}
    for ch in changements:
        out.setdefault(ch["onglet"], {"ajout": 0, "modification": 0, "retrait": 0, "archivage": 0})
        out[ch["onglet"]][ch["type"]] += 1
        if ch["archivage"]:
            out[ch["onglet"]]["archivage"] += 1
    return out


def vers_markdown(res):
    lignes = ["# Aperçu des impacts", ""]
    lignes.append(f"- Ancienne version : {'valide' if res['ancienne_version_valide'] else 'refusée'}")
    lignes.append(f"- Nouvelle version : {'valide' if res['nouvelle_version_valide'] else 'REFUSÉE'}")
    if not res["nouvelle_version_valide"]:
        lignes += ["", "La nouvelle version est refusée : elle ne peut pas être appliquée.", ""]
        lignes += [f"- {e}" for e in res["erreurs_nouvelle_version"]]
    lignes += ["", "## Résumé", "", "| Onglet | Ajouts | Modifications | Retraits | Archivages |", "| --- | --- | --- | --- | --- |"]
    for onglet, r in res["resume"].items():
        lignes.append(f"| {onglet} | {r['ajout']} | {r['modification']} | {r['retrait']} | {r['archivage']} |")
    if not res["resume"]:
        lignes.append("| aucun changement | | | | |")
    lignes += ["", "## Détail", ""]
    for ch in res["changements"]:
        cle = ", ".join(f"{k}={v}" for k, v in ch["cle"].items() if v)
        lignes.append(f"- **{ch['onglet']} / {ch['type']}** ({cle})" + (" - archivage" if ch["archivage"] else ""))
        for champ, val in ch["champs"].items():
            lignes.append(f"    - {champ} : `{val['avant']}` → `{val['après']}`")
    return "\n".join(lignes) + "\n"
