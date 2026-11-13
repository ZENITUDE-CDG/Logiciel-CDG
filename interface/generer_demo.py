"""Jeu de démonstration du site : huit résidences fictives sur l'année 2026 (données fictives).

Distinct des fixtures de test (tests/fixtures), qui ne sont pas modifiées.
Produit dans interface/demo/ :
  - ecritures.csv  : écritures équilibrées d'octobre 2025 à décembre 2026 ;
  - exercices.csv  : exercice en cours de chaque dossier (octobre-septembre ou janvier-décembre) ;
  - mesures.csv    : mesures d'exploitation mensuelles ; une valeur volontairement absente
                     (Le Belvédère, LN_VENDUES, août 2026) pour montrer « non calculable » ;
  - configuration.xlsx : config_kpi_lot6.xlsx avec ces huit résidences (dossiers déclarés
                     « à créer », avertissement W6) et des rubriques en vigueur dès 2025.

Usage : python interface/generer_demo.py [dossier_sortie]
"""
import calendar
import csv
import os
import random
import sys
from datetime import date

from openpyxl import load_workbook

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "tests"))
from generer_config_complete import lignes_rubriques, ecrire  # noqa: E402

SORTIE = os.path.join(RACINE, "interface", "demo")
GRAINE = 20261113
DEBUT, FIN = date(2025, 10, 1), date(2026, 12, 31)
ABSENCE = ("DEMO-2002", "2026-08", "LN_VENDUES")

# code, nom, dossier, activité, région, logements, prix moyen visé, durée de séjour visée,
# occupation visée, exercice (oct = octobre-septembre, civil = janvier-décembre)
RESIDENCES = [
    ("RES-001", "Les Terrasses du Port", "DEMO-2001", "Hôtellerie", "Région Sud", 72, 84, 2.1, 0.74, "oct"),
    ("RES-002", "Le Belvédère", "DEMO-2002", "Hôtellerie", "Région Est", 58, 71, 1.8, 0.69, "civil"),
    ("RES-003", "Les Tilleuls", "DEMO-2003", "Seniors", "Région Ouest", 64, 52, 38.0, 0.91, "oct"),
    ("RES-004", "Le Clos Fleuri", "DEMO-2004", "Seniors", "Région Sud", 80, 49, 45.0, 0.88, "oct"),
    ("RES-005", "Les Marronniers", "DEMO-2005", "Seniors", "Région Nord", 55, 57, 31.0, 0.86, "civil"),
    ("RES-006", "Campus Rive Gauche", "DEMO-2006", "Étudiants", "Région Est", 140, 19, 120.0, 0.83, "oct"),
    ("RES-007", "Le Jardin des Sciences", "DEMO-2007", "Étudiants", "Région Ouest", 110, 17, 110.0, 0.80, "oct"),
    ("RES-008", "Les Hauts de Loire", "DEMO-2008", "Mixte", "Région Nord", 66, 63, 9.0, 0.78, "oct"),
]


def mois(debut, fin):
    d = date(debut.year, debut.month, 1)
    while d <= fin:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def saison(activite, m):
    if activite == "Hôtellerie":
        return {7: 1.22, 8: 1.25, 6: 1.1, 12: 0.92, 1: 0.82, 2: 0.86, 11: 0.88}.get(m, 1.0)
    if activite == "Étudiants":
        return {7: 0.55, 8: 0.5, 9: 1.05}.get(m, 1.06)
    return 1.0


def main(SORTIE=SORTIE):
    os.makedirs(SORTIE, exist_ok=True)
    rng = random.Random(GRAINE)
    ecr, mes, exe = [], [], []
    for code, nom, dossier, act, region, logts, prix, dms, occ, typ in RESIDENCES:
        debut_ex, fin_ex = ((date(2025, 10, 1), date(2026, 9, 30)) if typ == "oct"
                            else (date(2026, 1, 1), date(2026, 12, 31)))
        exe.append([dossier, debut_ex.isoformat(), fin_ex.isoformat(),
                    (fin_ex.year - debut_ex.year) * 12 + fin_ex.month - debut_ex.month + 1])
        piece = 0
        for m in mois(DEBUT, FIN):
            jours = calendar.monthrange(m.year, m.month)[1]
            dispo = logts * jours
            vendues = min(dispo, round(dispo * occ * saison(act, m.month) * rng.uniform(0.95, 1.04)))
            sejours = max(1, round(vendues / (dms * rng.uniform(0.9, 1.1))))
            nuitees = round(vendues * (rng.uniform(1.25, 1.6) if act == "Hôtellerie" else rng.uniform(1.0, 1.15)))
            pdj = round(nuitees * (rng.uniform(0.45, 0.65) if act in ("Hôtellerie", "Mixte")
                                   else rng.uniform(0.70, 0.92) if act == "Seniors" else rng.uniform(0.12, 0.25)))
            cle = f"{m.year:04d}-{m.month:02d}"
            for mesure, v in (("LN_DISPONIBLES", dispo), ("LN_VENDUES", vendues), ("NB_SEJOURS", sejours),
                              ("NUITEES_CLIENTS", nuitees), ("COUVERTS_PDJ", pdj)):
                if (dossier, cle, mesure) == ABSENCE:
                    continue
                mes.append([dossier, cle, mesure, v, "fictif"])
            # Écritures : hébergement, services, charges ; chaque opération est équilibrée
            ca_heb = round(vendues * prix * rng.uniform(0.96, 1.04), 2)
            ca_serv = round(pdj * rng.uniform(9, 13) + ca_heb * rng.uniform(0.03, 0.07), 2)
            charges = [("641", 0.30), ("645", 0.12), ("606", 0.04), ("615", 0.03), ("626", 0.01),
                       ("625", 0.005), ("661", 0.02), ("658", 0.005)]
            dt = date(m.year, m.month, min(jours, 28)).isoformat()
            exercice = f"{debut_ex.isoformat()}/{fin_ex.isoformat()}"

            def op(journal, debit, credit, libelle, montant):
                nonlocal piece
                piece += 1
                num = f"{journal}{piece:05d}"
                ecr.append([dossier, exercice, dt, journal, num, debit, libelle, f"{montant:.2f}", ""])
                ecr.append([dossier, exercice, dt, journal, num, credit, libelle, "", f"{montant:.2f}"])

            op("VT", "411", "706", "Hébergement (fictif)", ca_heb)
            op("VT", "411", "708", "Prestations annexes (fictif)", ca_serv)
            for compte, part in charges:
                op("HA", compte, "401", f"Charge {compte} (fictif)",
                   round((ca_heb + ca_serv) * part * rng.uniform(0.85, 1.15), 2))
            op("HA", "6132", "401", "Loyer (fictif)", round((ca_heb + ca_serv) * rng.uniform(0.15, 0.19), 2))
    entete_e = ["dossier", "exercice", "date", "journal", "piece", "compte", "libelle", "debit", "credit"]
    for nom, entete, lignes in (("ecritures.csv", entete_e, ecr),
                                ("exercices.csv", ["dossier", "debut", "fin", "duree_mois"], exe),
                                ("mesures.csv", ["dossier", "mois", "mesure", "valeur", "source"], mes)):
        with open(os.path.join(SORTIE, nom), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(entete)
            w.writerows(lignes)

    # Configuration de démonstration
    comptes = sorted({l[5] for l in ecr})
    rub = lignes_rubriques(comptes)
    for r in rub:
        r[8] = date(2025, 1, 1)
    chemin = os.path.join(SORTIE, "configuration.xlsx")
    ecrire(os.path.join(RACINE, "tests", "fixtures", "config_kpi_lot6.xlsx"), chemin, rub)
    wb = load_workbook(chemin)
    ws = wb["Referentiel"]
    cols = {ws.cell(4, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(4, c).value}
    for r in range(5, ws.max_row + 1):
        for h, c in cols.items():
            if h != "Contrôle":
                ws.cell(r, c).value = None
    for i, (code, nom, dossier, act, region, *_rest) in enumerate(RESIDENCES):
        valeurs = {"Identifiant interne": code, "Nom de la résidence": nom, "Dossier Pennylane (identifiant)": dossier,
                   "Société": f"Société {nom} (fictive)", "Activité": act, "Région": region, "Marque": "Marque A",
                   "Date d'ouverture": date(2015, 1, 1), "Date d'effet": date(2025, 1, 1), "Statut": "actif",
                   "Dossier à créer (oui / non)": "oui"}
        for h, v in valeurs.items():
            ws.cell(5 + i, cols[h]).value = v
    wb.save(chemin)
    print(f"démo écrite dans {SORTIE} : {len(ecr)} lignes d'écritures, {len(mes)} mesures")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else SORTIE)
