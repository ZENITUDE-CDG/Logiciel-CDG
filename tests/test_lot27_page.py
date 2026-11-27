"""Lot 27 dans un vrai navigateur (DSN fictives) : détail par salarié, rémunérations, productivité, contrôles,
base budget, référentiel des postes. Ignorés si Playwright n'est pas installé."""
import json
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE))
import generer_dsn  # noqa: E402
from test_lot26_page import FICHIERS, importer, ouvrir, site  # noqa: E402,F401
from zenitude.social import dsn  # noqa: E402


def detail():
    out = {}
    for f in FICHIERS:
        for x in dsn.analyser(f.read_bytes())["declarations"]:
            out[(x["siret"], x["mois"])] = x["contenu"]
    return out


def periode(pg, du="2025-10", au="2026-10"):
    pg.evaluate(f"etat.lo = MOIS.indexOf('{du}'); etat.hi = MOIS.indexOf('{au}') + 1")


def test_remunerations_egales_a_la_reference(site):
    pg, erreurs = ouvrir(site)
    importer(pg)
    periode(pg)
    brut = etp = 0
    for c in detail().values():
        for s in c["salaries"]:
            if s["complet"] and s["etp_milli"] and s["brut"] > 0:
                brut += s["brut"]
                etp += s["etp_milli"]
    moy = pg.evaluate("dsnStats(dsnObs(perimetre('GROUPE').dossiers, fenetre())).moy")
    assert abs(moy - brut / (etp / 1000)) < 1e-6
    pg.evaluate("allerA('social', 'so_remun')")
    texte = pg.inner_text("#contenu")
    assert "RECEPTIONNISTE" in texte and "RÉCEPTIONNISTE H/F" not in texte  # libellés regroupés automatiquement
    stock = pg.evaluate("localStorage.getItem('zen-dsn')")
    assert "FICTIF" not in stock and "SALARIE" not in stock and "naissance" not in stock and '"nir"' not in stock
    for dim in ["famille", "niveau", "statut", "contrat"]:
        pg.select_option("#so-dim", dim)
        pg.select_option("#so-col", "residence")
    assert erreurs == []


def test_controles_de_paie(site):
    pg, erreurs = ouvrir(site)
    importer(pg)
    periode(pg)
    A = pg.evaluate("dsnControles(perimetre('GROUPE').dossiers, fenetre())")
    smic = {(a["d"], a["m"]) for a in A if a["k"] == "smic"}
    assert ("DEMO-2004", "2026-03") in smic  # salaire de base fictif sous le SMIC
    var = {(a["d"], a["m"]) for a in A if a["k"] == "variation"}
    assert ("DEMO-2001", "2026-07") in var and ("DEMO-2001", "2026-08") in var  # baisse puis retour
    cdd = [a["id"] for a in A if a["k"] == "cdd"]
    assert len(cdd) == len(set(cdd))  # une alerte par salarié
    assert erreurs == []


def test_pages_et_details(site):
    pg, erreurs = ouvrir(site)
    importer(pg)
    periode(pg)
    for page in ["so_remun", "so_productivite", "so_paie", "so_budget"]:
        pg.evaluate(f"allerA('social', '{page}')")
        ko = pg.evaluate("""() => { var ko = []; document.querySelectorAll('#contenu [data-x]').forEach(function (e) {
          var s = JSON.parse(e.getAttribute('data-x')); try { var R = EXPLIQUER[s.t](s); if (!R || !R.titre) ko.push(s); } catch (x) { ko.push(String(x)); } }); return ko; }""")
        assert ko == [], (page, ko[:3])
    # base budget : ETP = ETP fin de mois de la DSN
    pg.evaluate("allerA('social', 'so_budget')")
    etp = pg.evaluate("dsnSomme('etp', perimetre('GROUPE').dossiers, ['2026-10'])") / 1000
    assert f"{etp:.1f}".replace(".", ",") in pg.inner_text("#contenu")
    # productivité : ratio de sommes
    R = pg.evaluate("dsnProdLigne(perimetre('GROUPE').dossiers, fenetre())")
    assert R["caEtp"] and R["ebitdaEtp"] is not None and 0 < R["msCa"] < 1
    assert erreurs == []


def test_referentiel_des_postes(site):
    pg, erreurs = ouvrir(site)
    importer(pg)
    pg.evaluate("allerA('import', 'so_postes')")
    i = pg.evaluate("Array.from(document.querySelectorAll('[data-so-poste]')).findIndex(e => e.closest('tr').innerText.indexOf('SERVEUR') === 0)")
    pg.fill(f"[data-so-poste='{i}']", "Serveur restaurant")
    pg.select_option(f"[data-so-famille='{i}']", "Restauration")
    pg.click(f"[data-so-enr='{i}']")
    pg.wait_for_selector("text=Règle")
    assert pg.evaluate("dsnPoste('SERVEUR')") == {"poste": "SERVEUR RESTAURANT", "famille": "Restauration", "regle": True}
    periode(pg)
    pg.evaluate("allerA('social', 'so_remun')")
    assert "SERVEUR RESTAURANT" in pg.inner_text("#contenu")
    assert erreurs == []
