"""Modèle Excel d'import des KPI mensuels de toutes les résidences (lot 15, page Données externes).

Une ligne = une résidence et un mois ; une colonne par KPI (mesure d'exploitation). Cellule vide = valeur non
fournie (jamais zéro). Le fichier se dépose tel quel dans la page Données externes : la page vérifie tout et
refuse l'import entier à la moindre erreur (ligne, colonne et motif affichés).

Usage : python interface/generer_modele_import.py   (écrit modeles/Zenitude_Import_KPI_modele.xlsx)
"""
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "interface"))
from generer_site import IMPORT_KPI  # noqa: E402
from generer_demo import RESIDENCES  # noqa: E402

SORTIE = os.path.join(RACINE, "modeles", "Zenitude_Import_KPI_modele.xlsx")
ENTETES = ["Code résidence", "Résidence (facultatif)", "Mois (AAAA-MM)"] + [k["entete"] for k in IMPORT_KPI]
POLICE, GRAS = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True, color="FFFFFF")
TETE, SAISIE = PatternFill("solid", fgColor="0F506C"), PatternFill("solid", fgColor="FFF2CC")
BLEU = Font(name="Arial", size=10, color="0000FF")


def feuille_saisie(ws, lignes=0):
    for i, h in enumerate(ENTETES, 1):
        c = ws.cell(1, i, h)
        c.font, c.fill, c.alignment = GRAS, TETE, Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[c.column_letter].width = 26 if i == 2 else 18
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "D2"
    for r in range(2, 2 + lignes):
        for i in range(1, len(ENTETES) + 1):
            c = ws.cell(r, i)
            c.font = BLEU
            if i != 2:
                c.fill = SAISIE
            if i == 3:
                c.number_format = "@"
            if i > 3:
                c.number_format = "#,##0.##"
    if lignes:
        dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                            error="Nombre positif ou nul attendu ; laisser vide si la valeur n'est pas connue.")
        ws.add_data_validation(dv)
        dv.add(f"D2:{ws.cell(1 + lignes, len(ENTETES)).coordinate}")


def main(sortie=SORTIE):
    wb = Workbook()
    ws = wb.active
    ws.title = "Saisie"
    feuille_saisie(ws, 1200)

    ex = wb.create_sheet("Exemple")
    feuille_saisie(ex)
    exemple = [["RES-001", "Les Terrasses du Port (fictif)", "2026-03", 1540, 2232, 712, 2198, 1650],
               ["RES-001", "Les Terrasses du Port (fictif)", "2026-04", 1610, 2160, None, 2290, 1702]]
    for r, ligne in enumerate(exemple, 2):
        for i, v in enumerate(ligne, 1):
            ex.cell(r, i, v).font = POLICE
    ex.cell(5, 1, "Exemple fictif : la deuxième ligne n'a pas de nombre de séjours (cellule vide = non fourni, jamais zéro).").font = Font(name="Arial", size=9, italic=True)

    mo = wb.create_sheet("Mode d'emploi")
    textes = [
        ("Import des KPI mensuels - Zenitude Pilotage (phase test, données fictives)", True),
        ("", False),
        ("1. Remplir l'onglet Saisie : une ligne par résidence et par mois, toutes les résidences dans le même fichier.", False),
        ("2. Code résidence : le code interne (RES-001) ou le dossier Pennylane (voir l'onglet Résidences).", False),
        ("3. Mois : au format AAAA-MM (2026-03). Une date Excel ou 03/2026 sont aussi acceptées.", False),
        ("4. Une colonne par KPI. Cellule vide = valeur non fournie (le KPI sera « non calculable », jamais zéro).", False),
        ("5. Cellules jaunes, police bleue : à remplir. Ne pas renommer les en-têtes de la ligne 1.", False),
        ("6. Dans le logiciel : Import et paramètres, Données externes, Importer un fichier. Rien n'est enregistré si", False),
        ("   une seule ligne est en erreur : la page liste chaque erreur (ligne, colonne, motif) pour correction.", False),
        ("7. Une valeur importée remplace la valeur déjà présente pour la même résidence, le même mois et le même KPI.", False),
        ("", False),
        ("Colonnes", True),
    ] + [(f"{k['entete']} : mesure {k['code']} (autres en-têtes acceptés : {', '.join(k['alias'])})", False) for k in IMPORT_KPI]
    for r, (t, gras) in enumerate(textes, 1):
        mo.cell(r, 1, t).font = Font(name="Arial", size=10, bold=gras)
    mo.column_dimensions["A"].width = 120

    rs = wb.create_sheet("Résidences")
    for i, h in enumerate(["Code résidence", "Résidence", "Dossier Pennylane", "Activité"], 1):
        c = rs.cell(1, i, h)
        c.font, c.fill = GRAS, TETE
        rs.column_dimensions[c.column_letter].width = 28
    for r, (code, nom, dossier, act, *_x) in enumerate(RESIDENCES, 2):
        for i, v in enumerate([code, nom + " (fictif)", dossier, act], 1):
            rs.cell(r, i, v).font = POLICE
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    wb.save(sortie)
    print("modèle écrit :", sortie)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else SORTIE)
