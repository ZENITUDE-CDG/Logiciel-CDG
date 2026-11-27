"""Paquet Claude en ligne de commande (lot 25), sur les données de démonstration ou un dossier de données.

  python -m zenitude.socle paquet --perimetre GROUPE --du 2025-10 --au 2026-09 [--synthese] [--demo DIR] --sortie paquet.zip

Mêmes fichiers que le bouton « Télécharger le paquet » de la page (sans le classeur synthese.xlsx, propre à la page).
"""
import argparse
import os
import sys
import zipfile
from datetime import datetime

from . import construire


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m zenitude.socle")
    sous = ap.add_subparsers(dest="commande", required=True)
    p = sous.add_parser("paquet", help="construit le paquet de données pour Claude")
    p.add_argument("--perimetre", required=True, help="identifiant du périmètre (GROUPE, une activité, une résidence…)")
    p.add_argument("--du", required=True, help="premier mois AAAA-MM")
    p.add_argument("--au", required=True, help="dernier mois AAAA-MM")
    p.add_argument("--synthese", action="store_true", help="sans le détail des écritures ni des mouvements bancaires")
    p.add_argument("--demo", default=None, help="dossier des données (par défaut interface/demo)")
    p.add_argument("--sortie", required=True, help="fichier .zip à écrire")
    a = ap.parse_args(argv)
    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(racine, "interface"))
    import generer_site  # noqa: E402
    donnees = generer_site.construire(a.demo) if a.demo else generer_site.construire()
    per = next((x for x in donnees["perimetres"] if x["id"] == a.perimetre), None)
    if per is None:
        ap.error(f"périmètre inconnu : {a.perimetre}")
    fichiers = construire(donnees, per["dossiers"], a.du, a.au, complet=not a.synthese,
                          genere_le=datetime.now().strftime("%d/%m/%Y à %H:%M"), auteur="ligne de commande",
                          perimetre=per["libelle"])
    with zipfile.ZipFile(a.sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, texte in fichiers.items():
            z.writestr(nom, texte)
    print(f"{a.sortie} : {len(fichiers)} fichiers, {len(per['dossiers'])} résidence(s), {a.du} à {a.au}")


if __name__ == "__main__":
    main()
