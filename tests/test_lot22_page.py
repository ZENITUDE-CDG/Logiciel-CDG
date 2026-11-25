"""Lots 22-23 dans un vrai navigateur : la page Import comptable propose le choix des mois (lot 23). Le premier mois
proposé est le début de l'exercice N-1 (première intégration d'une société), la fin est libre (jusqu'à la fin de
N+1, ou sans limite). Les écritures anticipées restent signalées. Données fictives, base simulée."""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_lot18b_page import aller, demarrer, site  # noqa: E402,F401

SOURCE = """D.sources['PENNY-TEST'] = Object.assign({}, D.sources['PENNY-TEST'], { regle: 'n1_n', periode: ['2025-10-01', '2027-09-30'],
  exercices_importes: { 'N-1': ['2025-10-01', '2026-09-30'], N: ['2026-10-01', '2027-09-30'] },
  anticipees: { lignes: 12, mois: ['2026-12', '2027-01'] }, lignes_anterieures: 3 }); true"""
SANS_PARAM = "D.parametres_import = []; true"


def _bornes(pg, d):
    return pg.evaluate("(function () { var p = { dossiers: ['%s'] }, b = bornesImport(p), ex = exercicesDe('%s'); return { b: b, ex: ex }; })()" % (d, d))


def test_choix_des_mois_depuis_n_moins_1(site):
    pg, erreurs = demarrer(site)
    pg.evaluate(SOURCE + "; " + SANS_PARAM)
    aller(pg, "PENNY-TEST")
    r = _bornes(pg, "PENNY-TEST")
    debut = pg.evaluate("Array.from(document.querySelectorAll('#imp-debut option')).map(o => o.value)")
    fin = pg.evaluate("Array.from(document.querySelectorAll('#imp-fin option')).map(o => o.value)")
    assert debut[0] == r["b"]["debut"] and pg.input_value("#imp-debut") == r["b"]["debut"]  # défaut : début de N-1
    assert pg.input_value("#imp-fin") == r["b"]["finN"]  # défaut : fin de N
    assert fin[-1] == "" and fin[-2] == r["b"]["finMax"]  # fin libre, jusqu'à N+1 ou sans limite
    assert "12 ligne(s) datée(s) après aujourd’hui" in pg.inner_text("#imp-anticipees")
    assert "Dernière synchronisation : du 01/10/2025 au 30/09/2027" in pg.inner_text("#imp-periode")
    pg.select_option("#imp-fin", "")
    pg.click("#imp-synchro")
    pg.wait_for_function("appelsFonction.length === 1")
    body = pg.evaluate("appelsFonction[0].body")
    assert body["mois_debut"] == r["b"]["debut"] and body["mois_fin"] is None
    assert erreurs == []
    pg.close()


def test_debut_avant_fin(site):
    pg, erreurs = demarrer(site)
    pg.evaluate(SANS_PARAM)
    aller(pg, "PENNY-TEST")
    fin = pg.evaluate("Array.from(document.querySelectorAll('#imp-fin option')).map(o => o.value)")
    pg.select_option("#imp-debut", fin[-2])
    pg.select_option("#imp-fin", fin[0])
    pg.click("#imp-synchro")
    assert "Le mois de début est après le mois de fin" in pg.inner_text("#imp-message")
    assert pg.evaluate("appelsFonction.length") == 0
    assert erreurs == []
    pg.close()


def test_groupe_meme_choix_pour_toutes(site):
    pg, erreurs = demarrer(site)
    pg.evaluate(SOURCE + "; " + SANS_PARAM)
    aller(pg, "GROUPE")
    assert "le plus ancien des résidences du périmètre" in pg.inner_text("#imp-periode")
    ligne = pg.evaluate("Array.from(document.querySelectorAll('#contenu table tr')).map(r => r.innerText).find(t => t.indexOf('PENNY-TEST') >= 0)")
    assert "01/10/2025 → 30/09/2027" in ligne and "12" in ligne
    pg.click("#imp-synchro")
    pg.wait_for_function("appelsFonction.length === 1")
    body = pg.evaluate("appelsFonction[0].body")
    assert body["mois_debut"] == pg.input_value("#imp-debut") and body["mois_fin"] == pg.input_value("#imp-fin")
    assert erreurs == []
    pg.close()


def test_societe_sans_ecriture_commence_a_n_moins_1(site):
    """Nouvelle société : aucun exercice lu, seul l'exercice N de la fiche résidence est connu ; le choix commence
    douze mois avant le début de N, pas au mois courant."""
    pg, erreurs = demarrer(site)
    pg.evaluate("D.imports['DEMO-2001'] = []; residence('DEMO-2001').exercice = ['2026-10-01', '2027-09-30']; true")
    aller(pg, "DEMO-2001")
    assert pg.input_value("#imp-debut") == "2025-10"
    assert "rien n’a encore été lu" in pg.inner_text("#imp-periode")
    assert erreurs == []
    pg.close()
