"""Lot 24 en ligne (base simulée, données fictives) : clôture écrite dans la base avec l'instantané de la référence
Python, nouvelle version de règle, lecture seule hors administrateurs, prévisions réservées aux administrateurs,
migration 015 absente. Ignorés si Playwright n'est pas installé.
"""
import json
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE))
from zenitude.comptabilite import fees as f  # noqa: E402
from test_lot18b_page import demarrer, site  # noqa: E402,F401


def tables24(**autres):
    t = {"fees_rubriques": [dict(r, actif=True) for r in f.RUBRIQUES_DEPART],
         "fees_regles": [dict(r, id=i + 1, valeur=float(r["valeur"])) for i, r in enumerate(f.REGLES_DEPART)],
         "ca_regles": [], "fees_clotures": [], "compta_journal": [], "tresorerie_previsions": [], "virements_suivis": [], "comptes_bancaires": []}
    t.update(autres)
    return t


def test_en_ligne_cloture_dans_la_base(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables24())
    pg.evaluate("choisir('DEMO-2003'); etat.cpMois = '2026-04'; allerA('comptabilite', 'cp_fees')")
    pg.wait_for_selector(".cp-fees")
    assert pg.evaluate("D.lot24") is True
    pg.click("[data-clore='DEMO-2003']")
    pg.wait_for_function("tablesTest.fees_clotures.length === 1")
    pg.wait_for_selector("[data-rouvrir='DEMO-2003']")
    ligne = pg.evaluate("tablesTest.fees_clotures[0]")
    compta = pg.evaluate("D.calcul.compta['DEMO-2003']")
    attendu = f.instantane([dict(r, actif=True) for r in f.RUBRIQUES_DEPART], f.REGLES_DEPART, [], compta, "DEMO-2003", "2026-04")
    assert ligne["dossier"] == "DEMO-2003" and ligne["mois"] == "2026-04" and ligne["contenu"] == json.loads(json.dumps(attendu))
    # Nouvelle version écrite dans la base (upsert sur rubrique, dossier, mois d'effet)
    pg.evaluate("allerA('comptabilite', 'cp_parametrage')")
    pg.click("[data-cel='COMPTA|DEMO-2003']")
    pg.fill("#cp-val", "35")
    pg.click("#cp-ok")
    pg.wait_for_function("tablesTest.fees_regles.length === 7")
    nouvelle = pg.evaluate("tablesTest.fees_regles[6]")
    assert {k: nouvelle[k] for k in ("rubrique", "dossier", "mode", "valeur")} == {"rubrique": "COMPTA", "dossier": "DEMO-2003", "mode": "taux", "valeur": 35}
    assert erreurs == []
    pg.close()


def test_en_ligne_droits_et_migration_absente(site):
    pg, erreurs = demarrer(site, role="collaborateur", tables_en_plus=tables24())
    pg.evaluate("choisir('GROUPE'); allerA('comptabilite', 'cp_fees')")
    pg.wait_for_selector(".cp-fees")
    assert pg.query_selector("[data-clore]") is None and pg.query_selector("#cp-clore-tout") is None
    pg.evaluate("allerA('comptabilite', 'cp_parametrage')")
    assert "Lecture seule" in pg.inner_text("#contenu") and pg.query_selector("[data-cel]") is None
    assert "Prévisions et virements" not in pg.inner_text("#lat-nav") or pg.evaluate("sousVisibles('tresorerie').some(function (x) { return x[0] === 'tr_previsions'; })") is False
    pg.evaluate("allerA('tresorerie', 'tr_previsions')")
    assert pg.evaluate("etat.page") != "tr_previsions"
    assert erreurs == []
    pg.close()
    # Migration 015 absente : message clair, pas d'erreur
    pg, erreurs = demarrer(site)
    pg.evaluate("D.lot24 = false; true")
    pg.evaluate("choisir('GROUPE'); allerA('comptabilite', 'cp_fees')")
    assert "Migration 015 non appliquée" in pg.inner_text("#contenu")
    pg.evaluate("allerA('tresorerie', 'tr_banques'); etat.bqEdition = 'DEMO-2001|512'; majContenu()")
    assert pg.query_selector("#bq-max") is None  # plafond seulement avec la migration 015
    assert erreurs == []
    pg.close()
