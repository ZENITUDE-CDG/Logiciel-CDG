"""Génère un jeu d'écritures synthétiques (phase test, données fictives).

Comptes : PCG (config_modele/pcg_reference.csv). Montants : tirés au hasard avec une graine fixe.
Chaque opération est équilibrée (une facture ou un encaissement a toujours une contrepartie).

Usage : python tests/generer_ecritures.py <sortie_dossier>
"""
import csv
import os
import random
import sys
from datetime import date, timedelta

GRAINE = 20261113
EXERCICES = [
    # dossier, début, fin (dates fictives ; PENNY-1002 décalé, PENNY-1003 court de 9 mois)
    ("PENNY-1001", date(2026, 1, 1), date(2026, 12, 31)),
    ("PENNY-1002", date(2025, 4, 1), date(2026, 3, 31)),
    ("PENNY-1003", date(2026, 3, 1), date(2026, 11, 30)),
]


def mois(debut, fin):
    d = date(debut.year, debut.month, 1)
    while d <= fin:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def dernier_jour(d):
    return (date(d.year + (d.month == 12), d.month % 12 + 1, 1) - timedelta(days=1))


def ecritures_dossier(rng, dossier, debut, fin):
    out = []
    piece = 0

    def operation(dt, journal, debit, credit, libelle, montant):
        nonlocal piece
        piece += 1
        num = f"{journal}{piece:05d}"
        out.append([dossier, f"{debut.isoformat()}/{fin.isoformat()}", dt.isoformat(), journal, num, debit, libelle, f"{montant:.2f}", ""])
        out.append([dossier, f"{debut.isoformat()}/{fin.isoformat()}", dt.isoformat(), journal, num, credit, libelle, "", f"{montant:.2f}"])

    for m in mois(debut, fin):
        jour = lambda: min(m.replace(day=rng.randint(1, 28)), fin)
        # Charges mensuelles (facture puis règlement)
        charges = [
            ("606", "Fournitures d'entretien (exemple)", (400, 1400)),
            ("615", "Entretien et réparations (exemple)", (200, 1800)),
            ("625", "Déplacements (exemple)", (50, 400)),
            ("626", "Télécommunications (exemple)", (80, 250)),
            ("641", "Salaires (exemple)", (22000, 28000)),
            ("645", "Charges sociales (exemple)", (7000, 9500)),
            ("661", "Intérêts d'emprunt (exemple)", (300, 900)),
            ("658", "Charges diverses (exemple)", (20, 300)),
        ]
        for compte, lib, (lo, hi) in charges:
            montant = round(rng.uniform(lo, hi), 2)
            dt = jour()
            operation(dt, "HA", compte, "401", f"{lib} - facture", montant)
            operation(dt, "BQ", "401", "512", f"{lib} - règlement", montant)
        # Assurance : trimestrielle (6161) pour les dossiers 1001 et 1002
        if m.month in (1, 4, 7, 10) and dossier in ("PENNY-1001", "PENNY-1002"):
            montant = round(rng.uniform(900, 1600), 2)
            dt = jour()
            operation(dt, "HA", "6161", "401", "Assurance multirisques (exemple) - facture", montant)
            operation(dt, "BQ", "401", "512", "Assurance multirisques (exemple) - règlement", montant)
        # Produits mensuels (facture client puis encaissement)
        produits = [
            ("706", "Hébergement (exemple)", (38000, 56000)),
            ("708", "Prestations annexes (exemple)", (1500, 4200)),
        ]
        for compte, lib, (lo, hi) in produits:
            montant = round(rng.uniform(lo, hi), 2)
            dt = jour()
            operation(dt, "VT", "411", compte, f"{lib} - facture", montant)
            operation(dt, "BQ", "512", "411", f"{lib} - encaissement", montant)
        # Achats de stock occasionnels (601) sur un mois sur trois
        if m.month % 3 == 0:
            montant = round(rng.uniform(500, 2500), 2)
            dt = jour()
            operation(dt, "HA", "601", "401", "Matières premières (exemple) - facture", montant)
            operation(dt, "BQ", "401", "512", "Matières premières (exemple) - règlement", montant)
    return out


def main(sortie):
    os.makedirs(sortie, exist_ok=True)
    rng = random.Random(GRAINE)
    lignes = []
    for dossier, debut, fin in EXERCICES:
        lignes += ecritures_dossier(rng, dossier, debut, fin)
    with open(os.path.join(sortie, "ecritures_synthetiques.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["dossier", "exercice", "date", "journal", "piece", "compte", "libelle", "debit", "credit"])
        w.writerows(lignes)
    with open(os.path.join(sortie, "exercices.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["dossier", "debut", "fin", "duree_mois"])
        for dossier, debut, fin in EXERCICES:
            duree = (fin.year - debut.year) * 12 + fin.month - debut.month + 1
            w.writerow([dossier, debut.isoformat(), fin.isoformat(), duree])
    print(f"{len(lignes)} lignes écrites dans {sortie}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures")
