"""Lot 20 : catalogue de départ (interface/catalogue_kpi.py) cohérent et identique à l'amorce de la migration 012."""
import pathlib
import re
import sys

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import catalogue_kpi as ck  # noqa: E402
import generer_site  # noqa: E402

MIGRATION = RACINE / "migrations" / "012_suivi_kpi_parametrable.sql"


def test_amorce_de_la_migration_a_jour():
    assert ck.sql_amorce() in MIGRATION.read_text(encoding="utf-8"), \
        "amorce à régénérer : python interface/catalogue_kpi.py, puis remplacer le bloc dans la migration 012"


def test_codes_uniques_et_formats():
    codes = [x["code"] for x in ck.CATALOGUE]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch(r"[A-Z0-9_]{2,40}", c) for c in codes)
    assert len({x["ordre"] for x in ck.CATALOGUE}) == len(codes)
    modeles = {m["id"] for m in ck.MODELES}
    assert all(set(x["modeles"]) <= modeles and x["modeles"] for x in ck.CATALOGUE)
    assert set(ck.MODELE_PAR_ACTIVITE.values()) <= modeles


def test_formules_coherentes():
    par = {x["code"]: x for x in ck.CATALOGUE}
    for ind in (x for x in ck.CATALOGUE if x["type"] == "indicateur"):
        assert ind["numerateur"]
        for c in ind["numerateur"] + ind["denominateur"]:
            d = par[c]
            assert d["type"] == "donnee", (ind["code"], c)
            assert set(ind["modeles"]) <= set(d["modeles"]), (ind["code"], c)  # chaque modèle suit les données de la formule
    for d in (x for x in ck.CATALOGUE if x["type"] == "donnee"):
        assert d["signe"] == ("signe" if d["code"].startswith("CA_") else "positif")


def test_reprend_le_consolide_du_lot_19():
    """Mêmes colonnes et mêmes ratios que la reprise du consolidé (lot 19) : rien ne change pour l'utilisateur."""
    donnees = {x["code"]: x["colonne_consolide"] for x in ck.CATALOGUE if x["type"] == "donnee"}
    assert donnees == {k["code"]: k["consolide"] for k in generer_site.IMPORT_KPI}
    ratios = {x["colonne_consolide"]: (x["numerateur"], x["denominateur"]) for x in ck.CATALOGUE
              if x["type"] == "indicateur" and x["colonne_consolide"]}
    assert ratios == {r["colonne"]: ([r["num"]], [r["den"]]) for r in generer_site.RATIOS_CONSOLIDE}
