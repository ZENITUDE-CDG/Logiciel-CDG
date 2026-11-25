"""Lot 15 dans un vrai navigateur (données fictives) : comptes bancaires, analyse du solde, FRNG / BFR / TN,
graphiques liés à la réglette, tableau EBITDA, en local et avec une base simulée (l'import des KPI du lot 15 est remplacé par le modèle du catalogue, lot 21).
Ignorés si Playwright n'est pas installé."""
import json
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "tests"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
import publier_supabase as pub  # noqa: E402
from test_lot13_page import CLIENT_SIMULE  # noqa: E402
from zenitude.config import couverture  # noqa: E402
from zenitude.kpi.mesures import charger_exploitation  # noqa: E402


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site15")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    donnees = generer_site.construire(str(demo))
    complet, vide = dossier / "complet.html", dossier / "en_ligne.html"
    generer_site.ecrire(str(complet), donnees)
    generer_site.ecrire(str(vide), None)
    commun, par = pub.decouper(donnees, couverture.charger_ecritures(str(demo / "ecritures.csv")),
                               charger_exploitation(str(demo / "mesures.csv")))
    base = [{"id": c["residence"]["code"], "dossier_pennylane": d, "fictif": True} for d, c in par.items()]
    commune, lignes, _ = pub.lignes_a_publier(commun, par, base)
    lignes = json.loads(json.dumps([{"residence_id": l["residence_id"], "contenu": l["contenu"]} for l in lignes]))
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield {"nav": nav, "complet": complet, "vide": vide, "dossier": dossier,
               "commun": json.loads(json.dumps(commune["contenu"])), "lignes": lignes}
        nav.close()


def ouvrir(site):
    pg = site["nav"].new_page(viewport={"width": 1500, "height": 1000})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    return pg, erreurs


def test_graphiques_suivent_la_reglette(site):
    pg, erreurs = ouvrir(site)
    pg.evaluate("choisir('GROUPE'); allerA('tableaux', 'synthese'); reglerFenetre(3, 9)")
    pg.wait_for_timeout(100)
    n = pg.evaluate("document.querySelector('.graphe svg').querySelectorAll('circle[data-x]').length")
    assert n == 6
    assert erreurs == []
    pg.close()


def test_tableau_ebitda_du_groupe(site):
    pg, _ = ouvrir(site)
    pg.evaluate("choisir('GROUPE'); allerA('tableaux', 'synthese')")
    texte = pg.inner_text("table.fin")
    for lib in ("Données commerciales", "Marge variable", "% marge variable", "EBITDAR hors frais de siège",
                "Loyers propriétaires", "EBITDA en % du CA total", "Éléments hors CR", "Résultat net"):
        assert lib.lower() in texte.lower(), lib
    pg.close()


def test_comptes_bancaires_parametres_et_virement_conseille(site):
    pg, erreurs = ouvrir(site)
    pg.evaluate("choisir('DEMO-2008'); allerA('tresorerie', 'tr_banques')")
    assert "Virement conseillé" in pg.inner_text("#contenu")         # le secondaire est à découvert
    pg.click("[data-bq='DEMO-2008|5122']")
    pg.fill("#bq-lib", "Compte travaux")
    pg.fill("#bq-min", "5000")
    pg.click("#bq-ok")
    assert "Compte travaux" in pg.inner_text("#contenu")
    assert json.loads(pg.evaluate("localStorage.getItem('zen-comptes-bancaires')"))["DEMO-2008|5122"]["solde_min"] == 500000
    besoin = pg.evaluate("(function(){ var A = arreteTreso(), s = soldeBq('DEMO-2008', '5122', A)[0]; return 500000 - s; })()")
    assert pg.evaluate("document.querySelector('tr.bq-alerte td:nth-last-child(2)').innerText.trim()") == pg.evaluate(f"eurC({besoin})")
    assert erreurs == []
    pg.close()


def test_analyse_du_solde_n_moins_1(site):
    pg, erreurs = ouvrir(site)
    pg.evaluate("choisir('GROUPE'); allerA('tresorerie', 'tr_analyse')")
    assert pg.evaluate("etat.hi - etat.lo") >= 12                      # lot 16 : la période est celle de l'exercice (12 mois ou plus)
    texte = pg.inner_text("#contenu")
    assert "N-1 absent pour" in texte and "n.d." in texte               # historique non importé : jamais zéro
    pg.select_option("#an-cpt", "5122")
    assert "5122" in pg.evaluate("document.querySelector('#an-cpt').value")
    assert erreurs == []
    pg.close()


def test_equilibre_financier(site):
    pg, _ = ouvrir(site)
    pg.evaluate("choisir('GROUPE'); allerA('tableaux', 'equilibre')")
    assert "Équilibré" in pg.inner_text("#contenu")
    r = pg.evaluate("""() => { var A = arreteTreso(); return ['frng', 'bfr', 'tn', 'capitaux', 'resultat', 'emplois', 'creances', 'dettes', 'disponibilites', 'concours'].map(function (k) {
      var R = EXPLIQUER.bil({ t: 'bil', k: k, d: perimetre('GROUPE').dossiers, A: A }); return [k, R.controle ? R.controle.ok : null]; }); }""")
    assert all(ok is not False for _, ok in r)
    pg.close()


def demarrer_en_ligne(site, role):
    pg = site["nav"].new_page(viewport={"width": 1500, "height": 1000})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(site["vide"].as_uri())
    pg.evaluate(CLIENT_SIMULE)
    tables = {"donnees_communes": [{"id": "SITE", "contenu": site["commun"]}], "donnees_residences": site["lignes"],
              "groupes": [], "residence_groupe": [], "ajustements": [], "comptes_simules": [], "lissages": [],
              "mesures_importees": [], "comptes_bancaires": [{"dossier": "DEMO-2001", "compte": "5122", "libelle": "Travaux", "role": "secondaire", "solde_min": 100000}]}
    pg.evaluate("([t, r]) => demarrerAvecClient(clientSimule(t), { email: 'x@exemple.invalid', nom: 'X', role: r })", [tables, role])
    pg.wait_for_selector("#ecran-choix.visible")
    return pg, erreurs


def test_en_ligne_collaborateur_sans_import_ni_comptes_bancaires(site):
    pg, _ = demarrer_en_ligne(site, "collaborateur")
    pg.evaluate("choisir('GROUPE'); allerA('tresorerie', 'tr_banques')")
    assert pg.evaluate("etat.page") == "tr_position"
    assert "Comptes bancaires" not in pg.inner_text("#lat-nav")
    pg.evaluate("allerA('import', 'externes')")
    assert not pg.query_selector("#imp-fichier") and "Réservé aux administrateurs" in pg.inner_text("#contenu")
    pg.close()
