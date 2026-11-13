"""Génère la configuration de test du lot 6 : config_complete_v1 + six KPI actifs (données fictives).

KPI ajoutés (définitions à valider par le contrôle de gestion) :
  TO-SEN       Taux d'occupation            RATIO([LN_VENDUES];[LN_DISPONIBLES])
  PRIX-MOYEN   Prix moyen chambre           RATIO([CA_HEBERGEMENT];[LN_VENDUES])
  REVPAR       Revenu par chambre dispo.    RATIO([CA_HEBERGEMENT];[LN_DISPONIBLES])
  REVPAC       Revenu par client            RATIO([CA_HEBERGEMENT]+[CA_SERVICES];[NUITEES_CLIENTS])
  DMS          Durée moyenne de séjour      RATIO([LN_VENDUES];[NB_SEJOURS])
  CAPTAGE-PDJ  Taux de captage PDJ          RATIO([COUVERTS_PDJ];[NUITEES_CLIENTS])

Usage : python tests/generer_config_kpi.py <config_complete_v1.xlsx> <sortie.xlsx>
"""
import sys
from datetime import date

from openpyxl import load_workbook

KPI = [
    ("TO-SEN", "Taux d'occupation", "Logements-nuits vendus / logements-nuits disponibles",
     "RATIO([LN_VENDUES];[LN_DISPONIBLES])", "%", "ratio de sommes"),
    ("PRIX-MOYEN", "Prix moyen chambre", "CA hébergement / logements-nuits vendus",
     "RATIO([CA_HEBERGEMENT];[LN_VENDUES])", "€", "ratio de sommes"),
    ("REVPAR", "RevPAR", "CA hébergement / logements-nuits disponibles",
     "RATIO([CA_HEBERGEMENT];[LN_DISPONIBLES])", "€", "ratio de sommes"),
    ("REVPAC", "RevPAC", "CA hébergement et services / nuitées clients",
     "RATIO([CA_HEBERGEMENT]+[CA_SERVICES];[NUITEES_CLIENTS])", "€", "ratio de sommes"),
    ("DMS", "Durée moyenne de séjour", "Logements-nuits vendus / nombre de séjours",
     "RATIO([LN_VENDUES];[NB_SEJOURS])", "nuitées", "ratio de sommes"),
    ("CAPTAGE-PDJ", "Taux de captage petit-déjeuner", "Couverts petit-déjeuner / nuitées clients",
     "RATIO([COUVERTS_PDJ];[NUITEES_CLIENTS])", "%", "ratio de sommes"),
]


def main(source, sortie):
    wb = load_workbook(source)
    ws = wb["KPI"]
    cols = {ws.cell(4, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(4, c).value}
    ligne = 5
    while ws.cell(ligne, cols["Code KPI"]).value:
        ligne += 1
    for code, nom, definition, formule, unite, agregation in KPI:
        valeurs = {"Code KPI": code, "Nom": nom, "Définition": definition, "Formule": formule,
                   "Unité": unite, "Agrégation": agregation,
                   "Traitement de l'absence de donnée": "non calculable", "Grain": "résidence-mois",
                   "Temps de référence": "période choisie", "Responsable": "Contrôle de gestion",
                   "Statut": "actif", "Version": 1, "Date d'effet": date(2025, 1, 1),
                   "Approbateur": "Contrôle de gestion (fictif)"}
        for h, v in valeurs.items():
            ws.cell(ligne, cols[h]).value = v
        ligne += 1
    wb.save(sortie)
    print("classeur écrit :", sortie)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
