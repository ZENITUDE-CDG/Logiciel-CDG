"""Moteur de KPI (lot 6) : calcul par dossier et vue groupe, avec la configuration appliquée.

Point d'entrée unique pour les écrans et exports (CLAUDE.md, Architecture) :
aucune formule officielle n'est recopiée ailleurs.
"""
import os

from zenitude.config import controles as c
from zenitude.config import couverture
from .mesures import Source, charger_exploitation, liste_mois, libelle_mois, NonCalculable
from . import moteur


class RefusCalcul(Exception):
    """Demande de calcul impossible (aucune version appliquée, dossier ou période inconnus)."""


def _configuration(depot):
    etat = depot._lire()
    if not etat["courante"]:
        raise RefusCalcul("aucune version de configuration appliquée : calcul impossible")
    version = next(v for v in etat["versions"] if v["id"] == etat["courante"])
    classeur = os.path.join(depot.fichiers, version["empreinte"] + ".xlsx")
    rap = c.Rapport(chemin=str(classeur))
    ctx = c._Ctx(rap, set(), None)
    c._lire(ctx, classeur)
    return version, ctx.feuilles


def _resultat(version, feuilles, ecritures_csv, mesures_csv, dossiers, mois, perimetre):
    source = Source(feuilles.get("Rubriques", []), couverture.charger_ecritures(ecritures_csv),
                    charger_exploitation(mesures_csv))
    return {
        "perimetre": perimetre,
        "dossiers": list(dossiers),
        "periode": {"du": mois[0], "au": mois[-1], "nb_mois": len(mois),
                    "libelle": f"{libelle_mois(mois[0])} à {libelle_mois(mois[-1])}"},
        "version_config": version["id"],
        "empreinte_config": version["empreinte"],
        "kpi": moteur.calculer(feuilles.get("KPI", []), source, dossiers, mois),
        "donnees": "fictives (phase test)",
    }


def calculer_dossier(depot, dossier, ecritures_csv, exercices_csv, mesures_csv, du=None, au=None):
    """KPI d'un dossier. Sans période, l'exercice Pennylane du dossier (jamais supposé janvier-décembre)."""
    version, feuilles = _configuration(depot)
    if du and au:
        mois = liste_mois(du, au)
    else:
        exercices = couverture.charger_exercices(exercices_csv)
        if dossier not in exercices:
            raise RefusCalcul(f"exercice inconnu pour {dossier}")
        mois = liste_mois(*exercices[dossier])
    if not mois:
        raise RefusCalcul("période vide")
    return _resultat(version, feuilles, ecritures_csv, mesures_csv, [dossier], mois, dossier)


def dossiers_par_activite(feuilles, activite):
    """Dossiers Pennylane des résidences actives de l'activité (onglet Referentiel)."""
    out = []
    for r in feuilles.get("Referentiel", []):
        if str(r.get("Statut") or "").strip() != "actif":
            continue
        if str(r.get("Activité") or "").strip().lower() == activite.strip().lower():
            out.append(str(r.get("Dossier Pennylane (identifiant)") or "").strip())
    return sorted(d for d in out if d)


def calculer_groupe(depot, ecritures_csv, mesures_csv, du, au, dossiers=None, activite=None):
    """Vue groupe : mesures sommées sur tous les dossiers, puis formule (ratio de sommes).

    La période est obligatoire : les exercices des dossiers peuvent être décalés.
    """
    version, feuilles = _configuration(depot)
    if activite:
        dossiers = dossiers_par_activite(feuilles, activite)
        perimetre = f"activité {activite}"
    else:
        perimetre = "groupe : " + ", ".join(dossiers or [])
    if not dossiers:
        raise RefusCalcul("périmètre vide : aucun dossier")
    if not (du and au):
        raise RefusCalcul("période obligatoire pour une vue groupe (--du AAAA-MM --au AAAA-MM)")
    mois = liste_mois(du, au)
    if not mois:
        raise RefusCalcul("période vide")
    return _resultat(version, feuilles, ecritures_csv, mesures_csv, dossiers, mois, perimetre)
