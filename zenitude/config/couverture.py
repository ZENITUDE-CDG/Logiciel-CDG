"""Contrôle de couverture des comptes mouvementés (P1, lot 3).

Un compte de classe 6 ou 7 mouvementé sur un dossier et un exercice doit être classé
dans une rubrique active (ou exclu explicitement). Sinon il reste « non classé » et la
donnée ne peut pas être publiée comme validée. Les comptes de bilan (classes 1 à 5)
ne sont pas concernés par ce contrôle.
"""
import csv
from datetime import date

from . import controles as c


def charger_rubriques(chemin_classeur):
    rap = c.Rapport(chemin=str(chemin_classeur))
    ctx = c._Ctx(rap, set(), None)
    c._lire(ctx, chemin_classeur)
    return ctx.feuilles.get("Rubriques", [])


def charger_exercices(chemin_csv):
    with open(chemin_csv, encoding="utf-8") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    return {r["dossier"]: (date.fromisoformat(r["debut"]), date.fromisoformat(r["fin"])) for r in lignes}


def charger_ecritures(chemin_csv):
    with open(chemin_csv, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _rubrique_active(r, debut, fin):
    if str(r.get("Statut") or "").strip() != "actif":
        return False
    eff = c._date(r.get("Date d'effet")) or date.min
    fin_r = c._date(r.get("Date de fin")) or date.max
    return eff <= fin and debut <= fin_r


def _rubrique_couvre_dossier(r, dossier):
    d = str(r.get("Dossier Pennylane (ou * pour tous)") or "").strip()
    return d == "*" or d == dossier


def comptes_non_classes(rubriques, dossier, debut, fin, ecritures):
    """Comptes de classe 6 ou 7 mouvementés sur le dossier qu'aucune rubrique active ne couvre."""
    mouvementes = {e["compte"] for e in ecritures
                   if e["dossier"] == dossier and e["compte"][:1] in ("6", "7")}
    actives = [r for r in rubriques
               if _rubrique_couvre_dossier(r, dossier) and _rubrique_active(r, debut, fin)]
    non_classes = []
    for compte in sorted(mouvementes):
        couvert = False
        for r in actives:
            pref = str(r.get("Préfixe ou plage de comptes") or "").strip()
            if not pref or not c._periode_valide(pref):
                continue
            if not c._compte_dans(compte, pref):
                continue
            exc = c._liste_codes(r.get("Exceptions (comptes exclus, séparés par ;)"), casse=False)
            if any(compte.startswith(e) for e in exc):
                continue  # exception explicite : compte exclu de la rubrique
            couvert = True
            break
        if not couvert:
            non_classes.append(compte)
    return non_classes
