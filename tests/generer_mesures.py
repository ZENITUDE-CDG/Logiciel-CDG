"""Génère les mesures d'exploitation synthétiques du lot 6 (données fictives).

Une ligne par dossier, mois et mesure, sur l'exercice de chaque dossier (tests/fixtures/exercices.csv).
Mesures : LN_DISPONIBLES, LN_VENDUES, NB_SEJOURS, NUITEES_CLIENTS, COUVERTS_PDJ.
Valeurs entières tirées au hasard avec une graine fixe. Colonne source = « fictif ».

Usage : python tests/generer_mesures.py <dossier_fixtures>
"""
import calendar
import csv
import os
import random
import sys
from datetime import date

GRAINE = 20261113
# dossier : (logements, durée moyenne de séjour visée en nuits) - valeurs fictives
PROFILS = {"PENNY-1001": (25, 2.2), "PENNY-1002": (20, 25.0), "PENNY-1003": (18, 6.0)}


def mois(debut, fin):
    d = date(debut.year, debut.month, 1)
    while d <= fin:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def main(sortie):
    rng = random.Random(GRAINE)
    with open(os.path.join(sortie, "exercices.csv"), encoding="utf-8") as f:
        exercices = list(csv.DictReader(f, delimiter=";"))
    lignes = []
    for ex in exercices:
        dossier = ex["dossier"]
        logements, dms = PROFILS[dossier]
        for m in mois(date.fromisoformat(ex["debut"]), date.fromisoformat(ex["fin"])):
            jours = calendar.monthrange(m.year, m.month)[1]
            dispo = logements * jours
            vendues = round(dispo * rng.uniform(0.68, 0.95))
            sejours = max(1, round(vendues / (dms * rng.uniform(0.85, 1.15))))
            nuitees = round(vendues * rng.uniform(1.05, 1.45))
            pdj = round(nuitees * rng.uniform(0.35, 0.80))
            cle = f"{m.year:04d}-{m.month:02d}"
            for mesure, v in (("LN_DISPONIBLES", dispo), ("LN_VENDUES", vendues), ("NB_SEJOURS", sejours),
                              ("NUITEES_CLIENTS", nuitees), ("COUVERTS_PDJ", pdj)):
                lignes.append([dossier, cle, mesure, v, "fictif"])
    with open(os.path.join(sortie, "mesures_exploitation.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["dossier", "mois", "mesure", "valeur", "source"])
        w.writerows(lignes)
    print(f"{len(lignes)} lignes écrites dans {sortie}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures")
