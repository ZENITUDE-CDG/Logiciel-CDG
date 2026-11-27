"""Lot 31 en ligne (base simulée, données fictives) : écritures de la page Société dans les tables de la migration 020,
migration absente. Ignorés si Playwright n'est pas installé."""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
from test_lot18b_page import demarrer, site  # noqa: E402,F401


def tables31():
    res = [{"id": f"RES-00{i}", "libelle": f"R{i} (fictif)", "dossier_pennylane": f"DEMO-200{i}", "fictif": True, "archivee": False} for i in range(1, 9)]
    return {"residences": res, "classements": [], "residence_identifiants": [], "societes_journal": []}


def test_en_ligne_ecritures(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables31())
    assert pg.evaluate("D.lot31") is True
    pg.evaluate("choisir('DEMO-2006'); allerA('residence', 'residence')")
    pg.wait_for_selector("#soc-identite")
    pg.fill(".soc-id-lib", "Pennylane")
    pg.fill(".soc-id-code", "YTR")
    pg.click(".soc-id-ok")
    pg.wait_for_function("tablesTest.residence_identifiants.length === 1")
    assert pg.evaluate("tablesTest.residence_identifiants[0]") == {"residence_id": "RES-006", "libelle": "Pennylane", "code": "YTR"}
    pg.wait_for_selector("text=YTR")
    pg.click("#soc-modifier")
    pg.fill("#soc-f-marque", "Marque Z")
    pg.click("#soc-mod-ok")
    pg.wait_for_function("tablesTest.residences.find(function (r) { return r.id === 'RES-006'; }).marque === 'Marque Z'")
    r = pg.evaluate("tablesTest.residences.find(function (r) { return r.id === 'RES-006'; })")
    assert r["nom"] is None and r["dossier_pennylane"] == "DEMO-2006"  # valeurs de la configuration non recopiées
    assert pg.evaluate("residence('DEMO-2006').marque") == "Marque Z"
    pg.evaluate("choisir('GROUPE')")
    pg.fill("#soc-c-lib", "RM")
    pg.click("#soc-c-ok")
    pg.wait_for_function("tablesTest.classements.length === 1")
    pg.click(".soc-g-nouv[data-c=CL-RM]")
    pg.fill("#soc-g-lib", "RM Nord")
    pg.check(".soc-g-m[value=RES-006]")
    pg.click("#soc-g-ok")
    pg.wait_for_function("tablesTest.residence_groupe.length === 1")
    assert pg.evaluate("tablesTest.groupes[0]") == {"id": "GRP-RM-NORD", "libelle": "RM Nord", "classement_id": "CL-RM", "fictif": True}
    assert pg.evaluate("perimetre('GRP-RM-NORD').dossiers") == ["DEMO-2006"]
    pg.click("#soc-nouvelle")
    pg.fill("#soc-f-nom", "Nouvelle (fictif)")
    pg.click("#soc-mod-ok")
    pg.wait_for_function("tablesTest.residences.length === 9")
    n = pg.evaluate("tablesTest.residences[8]")
    assert n["id"] == "RES-009" and n["fictif"] is True and n["libelle"] == "Nouvelle (fictif)"
    pg.click(".soc-arc[data-soc=RES-009]")
    pg.wait_for_function("tablesTest.residences[8].archivee === true")
    assert erreurs == []
    pg.close()


def test_en_ligne_collaborateur_et_migration_absente(site):
    pg, erreurs = demarrer(site, role="collaborateur", tables_en_plus=tables31())
    pg.evaluate("choisir('DEMO-2006'); allerA('residence', 'residence')")
    assert pg.query_selector("#soc-modifier") and pg.query_selector("#soc-archiver") is None and pg.query_selector(".soc-id-ok")
    pg.evaluate("choisir('GROUPE')")
    assert pg.query_selector("#soc-nouvelle") is None and pg.query_selector("#soc-c-ok") is None
    pg.close()
    t = tables31()
    pg, erreurs = demarrer(site, tables_en_plus=t)
    pg.evaluate("D.lot31 = false; choisir('DEMO-2006'); allerA('residence', 'residence')")
    assert "Migration 020 non appliquée" in pg.inner_text("#contenu") and pg.query_selector("#soc-modifier") is None
    assert erreurs == []
    pg.close()
