"""Génère une configuration de test complète pour le lot 5 (données fictives, comptes PCG).

Chaque compte de classe 6 ou 7 présent dans les écritures synthétiques reçoit sa rubrique.
Produit deux classeurs :
  - config_complete_v1.xlsx : toutes les rubriques actives ;
  - config_complete_v2.xlsx : identique, sauf la rubrique CH-625 archivée (compte 625 non classé).

Usage : python tests/generer_config_complete.py <modele.xlsx> <sortie> <ecritures.csv>
"""
import csv
import os
import sys
from datetime import date

from openpyxl import load_workbook

COMPTES_PRODUIT = {"706": ("CA-HEB", "CA_HEBERGEMENT", "Prestations d'hébergement (exemple)"),
                   "708": ("CA-SERV", "CA_SERVICES", "Produits annexes (exemple)")}


def comptes_utilises(chemin):
    with open(chemin, encoding="utf-8") as f:
        return sorted({r["compte"] for r in csv.DictReader(f, delimiter=";")})


def lignes_rubriques(comptes):
    out = []
    for compte in comptes:
        if compte in COMPTES_PRODUIT:
            code, agr, lib = COMPTES_PRODUIT[compte]
            out.append([code, lib, "produit", "*", compte, "", agr, 1, date(2026, 1, 1), None, "actif",
                        "Exemple fictif : compte PCG"])
        elif compte[:1] == "6":
            out.append([f"CH-{compte}", f"Charge {compte} (exemple)", "charge", "*", compte, "",
                        "PL_CHARGES", 1, date(2026, 1, 1), None, "actif", "Exemple fictif : compte PCG"])
    return out


def ecrire(modele, sortie, lignes, archiver=None):
    wb = load_workbook(modele)
    ws = wb["Rubriques"]
    # Efface les lignes d'exemple (à partir de la ligne 5), en gardant les colonnes et la validation
    for r in range(5, ws.max_row + 1):
        for c in range(1, 13):
            ws.cell(r, c).value = None
    cols = {ws.cell(4, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(4, c).value}
    entetes = ["Code rubrique", "Libellé", "Type", "Dossier Pennylane (ou * pour tous)",
               "Préfixe ou plage de comptes", "Exceptions (comptes exclus, séparés par ;)",
               "Agrégat de base", "Priorité", "Date d'effet", "Date de fin", "Statut", "Justification"]
    for i, ligne in enumerate(lignes):
        for h, v in zip(entetes, ligne):
            if archiver and ligne[0] == archiver and h == "Statut":
                v = "archivé"
            ws.cell(5 + i, cols[h]).value = v
    # Référentiel et autres onglets : on garde les exemples du modèle (résidences connues)
    wb.save(sortie)


def main(modele, sortie_dir, ecritures):
    os.makedirs(sortie_dir, exist_ok=True)
    lignes = lignes_rubriques(comptes_utilises(ecritures))
    ecrire(modele, os.path.join(sortie_dir, "config_complete_v1.xlsx"), lignes)
    ecrire(modele, os.path.join(sortie_dir, "config_complete_v2.xlsx"), lignes, archiver="CH-625")
    print("classeurs écrits dans", sortie_dir)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
