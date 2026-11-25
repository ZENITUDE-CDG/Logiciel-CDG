"""Lot 16 dans un vrai navigateur (données fictives) : ruban supérieur avec l'exercice de référence et le
périmètre (résidence ou groupe). L'exercice fixe la période de chaque page. Ignorés si Playwright est absent."""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site16")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    complet = dossier / "complet.html"
    generer_site.ecrire(str(complet), generer_site.construire(str(demo)))
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield {"nav": nav, "complet": complet}
        nav.close()


def ouvrir(site, largeur=1400, perimetre="DEMO-2006"):
    pg = site["nav"].new_page(viewport={"width": largeur, "height": 900})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.click(f"#choix-res button[data-p={perimetre}]")
    pg.wait_for_selector("#rub-haut")
    # Lot 21 : on arrive sur Import comptable ; ces tests portent sur la réglette de la Synthèse.
    assert pg.evaluate("etat.section + '/' + etat.page") == "import/pennylane"
    pg.evaluate("allerA('tableaux', 'synthese')")
    pg.wait_for_selector("#reg-lib")
    return pg, erreurs


def test_ruban_exercice_et_perimetre(site):
    pg, erreurs = ouvrir(site)
    # Le bouton Périmètre n'est plus dans le menu latéral : il est dans le ruban, à côté de l'exercice.
    assert pg.locator("#lateral #btn-perim").count() == 0
    assert pg.locator("#rub-haut #btn-exercice").count() == 1 and pg.locator("#rub-haut #btn-perim").count() == 1
    assert "Exercice N, en cours" in pg.inner_text("#btn-exercice")
    assert "Campus Rive Gauche" in pg.inner_text("#btn-perim") and "Résidence" in pg.inner_text("#btn-perim")
    # Le ruban est bleu (charte) et la période de la réglette est celle de l'exercice.
    assert pg.evaluate("getComputedStyle(document.getElementById('rub-haut')).backgroundColor") == "rgb(15, 80, 108)"
    assert pg.inner_text("#reg-lib") == pg.inner_text("#exercice-dates")
    assert not erreurs


def test_exercice_fixe_la_periode_et_le_perimetre_la_suit(site):
    pg, erreurs = ouvrir(site)
    avant = pg.inner_text("#reg-lib")
    pg.click("#btn-exercice")
    options = pg.locator("#der-ex-liste .opt")
    assert options.count() >= 2
    pg.click("#der-ex-liste .opt[data-ex='N+1']")
    apres = pg.inner_text("#reg-lib")
    assert apres != avant and "N+1" in pg.inner_text("#btn-exercice") and apres == pg.inner_text("#exercice-dates")
    # Autre résidence : l'exercice choisi (N+1) reste, la période prend les dates de cette résidence.
    pg.click("#btn-perim")
    pg.click("#der-liste button[data-p=DEMO-2002]")
    assert "N+1" in pg.inner_text("#btn-exercice") and pg.inner_text("#reg-lib") == pg.inner_text("#exercice-dates")
    assert not erreurs


def test_periode_reglee_a_la_main_est_signalee_et_conservee(site):
    pg, erreurs = ouvrir(site)
    pg.click("#reg-rac button[data-r='0']")  # « Dernier mois importé »
    assert "Période modifiée" in pg.inner_text("#btn-exercice")
    modifiee = pg.inner_text("#reg-lib")
    pg.click("#btn-perim")
    pg.click("#der-liste button[data-p=DEMO-2002]")
    assert pg.inner_text("#reg-lib") == modifiee  # la période réglée à la main est conservée
    pg.click("#btn-exercice")
    pg.click("#der-ex-liste .opt[data-ex='N']")  # revenir aux dates de l'exercice
    assert "Période modifiée" not in pg.inner_text("#btn-exercice")
    assert not erreurs


def test_ruban_fixe_sur_toutes_les_pages_et_groupe(site):
    pg, erreurs = ouvrir(site)
    pg.click(".lat-item[data-section=residence]")  # page sans réglette
    assert pg.is_visible("#rub-haut") and pg.is_visible("#btn-exercice")
    pg.click(".lat-item[data-section=tableaux]")
    pg.evaluate("window.scrollTo(0, 700)")
    haut = pg.evaluate("document.getElementById('rub-haut').getBoundingClientRect().top")
    zone = pg.evaluate("document.getElementById('zone-periode').getBoundingClientRect().top")
    assert haut == 0 and zone == 52  # le ruban reste en haut, la réglette se fixe juste dessous
    pg.evaluate("window.scrollTo(0, 0)")
    pg.click("#btn-perim")
    pg.click("#der-liste button.opt[data-p]:has-text('Groupe Zenitude')")
    assert "Groupe" in pg.inner_text("#btn-perim") and "Exercice" in pg.inner_text("#btn-exercice")
    assert "décalés" in pg.inner_text("#exercice-dates")  # exercices de dates différentes dans le groupe
    assert not erreurs


def test_ruban_sur_telephone(site):
    pg, erreurs = ouvrir(site, largeur=390)
    assert pg.is_visible("#btn-burger") and pg.is_visible("#btn-exercice") and pg.is_visible("#btn-perim")
    pg.click("#btn-burger")
    assert pg.evaluate("document.getElementById('app').classList.contains('menu-ouvert')")
    assert not erreurs
