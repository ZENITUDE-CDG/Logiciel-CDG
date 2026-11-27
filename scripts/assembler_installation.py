"""Assemble scripts/installation_supabase.sql (installation complète de la base de test en un collage).

Ordre : remise à zéro, migrations (dans l'ordre des numéros), données de départ, puis la résidence du
dossier Pennylane de test (lot 18, scripts/lot18_residence_test.sql).
Usage : python scripts/assembler_installation.py
Un test (tests/test_lot13_publication.py) vérifie que le fichier du dépôt est à jour.
"""
import pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent
SORTIE = RACINE / "scripts" / "installation_supabase.sql"

ENTETE = """-- INSTALLATION COMPLÈTE DE LA BASE DE TEST SUPABASE (lots 12 à 26). À coller en une fois dans SQL Editor.
-- Fichier assemblé par scripts/assembler_installation.py : remise à zéro + migrations + données de départ.
-- Remet la base de test à zéro : données fictives uniquement. Ne jamais exécuter sur une base réelle.
-- Après l'avoir lancé, relancer la publication des données (GitHub, Actions, « Run workflow »).
"""


def morceaux():
    fichiers = [RACINE / "scripts" / "reinitialiser_base_test.sql"]
    fichiers += sorted((RACINE / "migrations").glob("*.sql"))
    fichiers += [RACINE / "scripts" / "donnees_test.sql", RACINE / "scripts" / "lot18_residence_test.sql"]
    return fichiers


def assembler():
    texte = ENTETE
    for f in morceaux():
        rel = f.relative_to(RACINE).as_posix()
        texte += f"\n-- ===================== {rel} =====================\n"
        texte += f.read_text(encoding="utf-8").rstrip("\n") + "\n"
    return texte


if __name__ == "__main__":
    SORTIE.write_text(assembler(), encoding="utf-8")
    print("écrit :", SORTIE.relative_to(RACINE))
