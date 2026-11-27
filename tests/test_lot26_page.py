"""Lot 26 dans un vrai navigateur (DSN fictives) : lecture DSN, import, pages Social.

- lecture : la page donne exactement les mêmes totaux que zenitude/social/dsn.py, sur les 13 fichiers fictifs ;
- arrêts de travail : jours par établissement et par mois identiques ;
- import par l'écran (rattachement SIRET -> résidence, enregistrement), puis aucune donnée nominative stockée ;
- tableau de bord et rapprochement : effectif, brut, écart DSN / 641 et DSN manquante détectés ;
- réimport : les mois identiques ne sont pas réenregistrés ; Social masqué hors administrateurs (en ligne).
Ignorés si Playwright n'est pas installé.
"""
import json
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE))
import generer_demo  # noqa: E402
import generer_dsn  # noqa: E402
import generer_site  # noqa: E402
from zenitude.social import dsn  # noqa: E402

FICHIERS = sorted((RACINE / "interface" / "demo" / "dsn").glob("*.dsn"))


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site26")
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


def ouvrir(site, perimetre="GROUPE"):
    pg = site["nav"].new_page(viewport={"width": 1500, "height": 1000})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.click(f"#ecran-choix [data-p='{perimetre}']")
    pg.wait_for_selector("#rub-haut")
    return pg, erreurs


def reference():
    par_siret = {}
    for f in FICHIERS:
        for x in dsn.analyser(f.read_bytes())["declarations"]:
            par_siret.setdefault(x["siret"], {})[x["mois"]] = x["contenu"]
    return par_siret


def importer(pg):
    pg.evaluate("allerA('import', 'so_import')")
    pg.set_input_files("#so-fichiers", [str(f) for f in FICHIERS])
    pg.wait_for_selector("#so-apercu")
    for s in pg.query_selector_all("[data-so-rat]"):
        siret = s.get_attribute("data-so-rat")
        pg.select_option(f"[data-so-rat='{siret}']", "DEMO-" + siret[5:9])
    pg.click("#so-enregistrer")
    pg.wait_for_selector("#so-journal")


def test_lecture_identique_a_la_reference_python(site):
    pg, erreurs = ouvrir(site)
    for f in FICHIERS:
        js = json.loads(pg.evaluate("(o) => JSON.stringify(dsnAnalyser(new Uint8Array(o)))", list(f.read_bytes())))
        assert js == json.loads(json.dumps(dsn.analyser(f.read_bytes()))), f.name
    ref = reference()
    js = json.loads(pg.evaluate("(c) => JSON.stringify(Object.keys(c).map(s => Object.keys(c[s]).map(m => [s, m, dsnJoursArret(c[s], m)])))", ref))
    for ligne in js:
        for s, m, j in ligne:
            assert j == dsn.jours_arret(ref[s], m), (s, m)
    # fichier illisible : refus en entier, même motif
    msg = pg.evaluate("() => { try { dsnAnalyser(new TextEncoder().encode(\"S10.G00.00.001,'X'\\nBONJOUR\")); } catch (e) { return e.dsnErreur; } }")
    with pytest.raises(dsn.ErreurDSN) as e:
        dsn.analyser("S10.G00.00.001,'X'\nBONJOUR".encode())
    assert msg == str(e.value)
    assert erreurs == []


def test_import_et_pages_sociales(site):
    pg, erreurs = ouvrir(site)
    importer(pg)
    stock = pg.evaluate("localStorage.getItem('zen-dsn')")
    assert "FICTIF" not in stock and "SALARIE" not in stock and '"nir"' not in stock
    assert pg.evaluate("DSN.mois.length") == 13 * 8 - 1 and pg.evaluate("DSN.etablissements.length") == 8
    ref = reference()
    # effectif et brut du groupe, octobre 2026
    pg.evaluate("etat.lo = MOIS.indexOf('2026-10'); etat.hi = etat.lo + 1; allerA('social', 'so_synthese')")
    assert pg.evaluate("dsnSomme('effectif', perimetre('GROUPE').dossiers, ['2026-10'])") == sum(c["2026-10"]["effectif_fin"] for c in ref.values())
    assert pg.evaluate("dsnSomme('brut', perimetre('GROUPE').dossiers, ['2026-10'])") == sum(c["2026-10"]["brut"] for c in ref.values())
    assert pg.evaluate("dsnSomme('etp', ['DEMO-2007'], ['2026-03'])") is None  # quotité manquante : non calculable
    # rapprochement : écart de DEMO-2003 en juin et DSN manquante de DEMO-2005 en février
    assert pg.evaluate("dsnRatio('ecart', ['DEMO-2003'], ['2026-06']).ecart") == -123456
    assert pg.evaluate("dsnRatio('ecart', ['DEMO-2001'], ['2026-06']).ecart") == 0
    pg.evaluate("etat.lo = MOIS.indexOf('2025-10'); etat.hi = MOIS.indexOf('2026-10') + 1; allerA('social', 'so_controle')")
    texte = pg.inner_text("#contenu")
    assert "DSN ?" in texte and "-1 235 €" in texte
    for page in ["so_synthese", "so_effectifs", "so_absences", "so_controle"]:
        pg.evaluate(f"allerA('social', '{page}')")
        assert "Non calculable." not in pg.inner_text("#contenu")
        ko = pg.evaluate("""() => { var ko = []; document.querySelectorAll('#contenu [data-x]').forEach(function (e) {
          var s = JSON.parse(e.getAttribute('data-x')); try { var R = EXPLIQUER[s.t](s); if (!R || !R.titre) ko.push(s); } catch (x) { ko.push(String(x)); } }); return ko; }""")
        assert ko == [], (page, ko[:3])
    # détail des calculs
    pg.evaluate("allerA('social', 'so_synthese')")
    pg.click(".indic[data-x]")
    pg.wait_for_selector("#panneau.ouvert")
    assert "Effectif fin de mois" in pg.inner_text("#panneau")
    pg.keyboard.press("Escape")
    # réimport : tout est déjà importé
    pg.evaluate("allerA('import', 'so_import')")
    pg.set_input_files("#so-fichiers", [str(f) for f in FICHIERS[:2]])
    pg.wait_for_selector("#so-apercu")
    assert pg.is_disabled("#so-enregistrer")
    assert erreurs == []


def test_social_reserve_aux_administrateurs(site):
    pg, erreurs = ouvrir(site)
    menu = lambda: pg.evaluate("dessinerMenu(); Array.from(document.querySelectorAll('#lat-nav [data-section]')).map(b => b.dataset.section)")
    assert "social" in menu()
    pg.evaluate("D.enLigne = { email: 'x@exemple.invalid', nom: 'X', role: 'collaborateur' }")
    assert "social" not in menu()
    assert pg.evaluate("sousVisibles('import').map(x => x[0])").count("so_import") == 0
    assert erreurs == []
