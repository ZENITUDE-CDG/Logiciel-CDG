"""Lot 22 dans un vrai navigateur : la page Import comptable affiche la règle N-1 + N, les exercices retenus de la
résidence, les écritures anticipées et les lignes antérieures au début du site. Données fictives, base simulée."""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_lot18b_page import aller, demarrer, site  # noqa: E402,F401

SOURCE = """D.sources['PENNY-TEST'] = Object.assign({}, D.sources['PENNY-TEST'], { regle: 'n1_n', periode: ['2025-10-01', '2027-09-30'],
  exercices_importes: { 'N-1': ['2025-10-01', '2026-09-30'], N: ['2026-10-01', '2027-09-30'] },
  anticipees: { lignes: 12, mois: ['2026-12', '2027-01'] }, lignes_anterieures: 3 }); true"""


def test_regle_affichee_pour_une_residence(site):
    pg, erreurs = demarrer(site)
    pg.evaluate(SOURCE)
    aller(pg, "PENNY-TEST")
    periode = pg.inner_text("#imp-periode")
    assert "Exercice précédent complet (N-1) + exercice en cours (N)" in periode
    assert "Exercice N-1 : 01/10/2025 au 30/09/2026" in periode and "Exercice N : 01/10/2026 au 30/09/2027" in periode
    assert "3 ligne(s) antérieure(s)" in periode
    assert "12 ligne(s) datée(s) après aujourd’hui" in pg.inner_text("#imp-anticipees")
    assert pg.query_selector("#imp-debut") is None and pg.query_selector("#imp-fin") is None
    assert erreurs == []
    pg.close()


def test_groupe_periode_par_residence(site):
    pg, erreurs = demarrer(site)
    pg.evaluate(SOURCE)
    aller(pg, "GROUPE")
    assert "d’après ses propres exercices" in pg.inner_text("#imp-periode")
    ligne = pg.evaluate("Array.from(document.querySelectorAll('#contenu table tr')).map(r => r.innerText).find(t => t.indexOf('PENNY-TEST') >= 0)")
    assert "01/10/2025 → 30/09/2027" in ligne and "12" in ligne
    pg.click("#imp-synchro")
    pg.wait_for_function("appelsFonction.length === 1")
    body = pg.evaluate("appelsFonction[0].body")
    assert body["mois_debut"] is None and body["mois_fin"] is None
    assert erreurs == []
    pg.close()


def test_residence_non_connectee(site):
    pg, erreurs = demarrer(site)
    aller(pg, "DEMO-2001")
    assert "la période sera calculée à la première synchronisation" in pg.inner_text("#imp-periode")
    assert erreurs == []
    pg.close()
