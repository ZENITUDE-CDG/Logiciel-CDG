"""Lots 28 à 30 : jeu de démonstration avec des anomalies fictives qui déclenchent chaque écart repéré.

Les écritures et les mesures sont ajoutées aux fichiers de la démonstration AVANT le calcul du site, pour que la
comptabilité mensuelle, les écritures et les données d'exploitation restent cohérentes entre elles.
"""
import pathlib
import sys

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402

EXE = "2025-10-01/2026-09-30"


def _e(d, date, j, piece, compte, lib, debit="", credit="", tiers=""):
    return f"{d};{EXE};{date};{j};{piece};{compte};{lib} (fictif);{debit};{credit};{tiers};;\n"


ECRITURES = [
    # A2 : écriture inhabituelle sur un compte habituel (625, déplacements)
    _e("DEMO-2001", "2026-09-10", "HA", "ZA1", "625", "Séminaire", debit="48000.00"),
    _e("DEMO-2001", "2026-09-10", "HA", "ZA1", "401", "Séminaire", credit="48000.00", tiers="FOU-SEMI"),
    # A3 : compte nouveau (6237)
    _e("DEMO-2001", "2026-09-12", "HA", "ZA2", "6237", "Annonces", debit="9000.00"),
    _e("DEMO-2001", "2026-09-12", "HA", "ZA2", "401", "Annonces", credit="9000.00", tiers="FOU-ANN"),
    # A4 : prime d'assurance annuelle en une écriture (616)
    _e("DEMO-2001", "2026-09-15", "HA", "ZA3", "616", "Assurance annuelle", debit="24000.00"),
    _e("DEMO-2001", "2026-09-15", "HA", "ZA3", "401", "Assurance annuelle", credit="24000.00", tiers="FOU-ASSU"),
    # F4 : facture en double (même fournisseur, même montant, 3 jours d'écart)
    _e("DEMO-2001", "2026-09-20", "HA", "ZA4", "6156", "Maintenance", debit="3100.00"),
    _e("DEMO-2001", "2026-09-20", "HA", "ZA4", "401", "Maintenance", credit="3100.00", tiers="FOU-MAINT"),
    _e("DEMO-2001", "2026-09-23", "HA", "ZA5", "6156", "Maintenance", debit="3100.00"),
    _e("DEMO-2001", "2026-09-23", "HA", "ZA5", "401", "Maintenance", credit="3100.00", tiers="FOU-MAINT"),
]
# R1 : CA Mews (fictif) différent du CA comptable de septembre 2026 pour DEMO-2001 ; égal pour DEMO-2002
MESURES = ["DEMO-2001;2026-09;CA_MEWS_TOTAL;100000;fictif\n"]


def construire(dossier):
    """Démonstration + anomalies dans `dossier`, puis données du site (generer_site.construire)."""
    demo = pathlib.Path(dossier)
    generer_demo.main(str(demo))
    with open(demo / "ecritures.csv", "a", encoding="utf-8") as f:
        f.writelines(ECRITURES)
    with open(demo / "mesures.csv", "a", encoding="utf-8") as f:
        f.writelines(MESURES)
    return generer_site.construire(str(demo))
