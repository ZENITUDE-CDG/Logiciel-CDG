"""Lot 17 dans un vrai navigateur (données fictives) : ordre du menu latéral et export Excel de la page
(tableaux, données des graphiques, détail des calculs, écritures comptables). Ignorés si Playwright est absent."""
import pathlib
import sys
from collections import defaultdict

import pytest

playwright = pytest.importorskip("playwright.sync_api")
openpyxl = pytest.importorskip("openpyxl")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site17")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    complet = dossier / "complet.html"
    generer_site.ecrire(str(complet), generer_site.construire(str(demo)))
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield {"nav": nav, "complet": complet, "dossier": dossier}
        nav.close()


def ouvrir(site, perimetre="DEMO-2006"):
    pg = site["nav"].new_page(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.click(f"#choix-res button[data-p={perimetre}]")
    pg.wait_for_selector("#rub-haut")
    return pg, erreurs


def exporter(site, pg, section, page):
    pg.evaluate(f"allerA('{section}', '{page}')")
    pg.wait_for_selector("#btn-xlsx")
    with pg.expect_download(timeout=60000) as dl:
        pg.click("#btn-xlsx")
    fichier = site["dossier"] / f"{page}.xlsx"
    dl.value.save_as(str(fichier))
    return openpyxl.load_workbook(fichier), dl.value.suggested_filename


def test_ordre_du_menu_lateral(site):
    pg, erreurs = ouvrir(site)
    noms = [t.split("\n")[0] for t in pg.locator(".lat-item").all_inner_texts()]
    assert noms == ["Résidence", "Import et paramètres", "Tableaux de bord", "Ajustements", "Trésorerie", "Budgets", "Rapports"]
    assert not erreurs


def test_export_synthese_contenu_et_liens(site):
    pg, erreurs = ouvrir(site)
    wb, nom = exporter(site, pg, "tableaux", "synthese")
    assert nom.startswith("Zenitude_Synthese-d-activite_Campus-Rive-Gauche") and nom.endswith("_ajuste.xlsx")
    feuilles = wb.sheetnames
    assert feuilles[0] == "Résumé"
    for attendu in ("Indicateurs", "Graphiques", "Détail des calculs", "Composition", "Écritures"):
        assert attendu in feuilles
    assert any(f.startswith("T1 ") for f in feuilles)
    # Les montants des tableaux sont des nombres (pas du texte) et renvoient au détail.
    t1 = wb[[f for f in feuilles if f.startswith("T1 ")][0]]
    nombres = [c for ligne in t1.iter_rows(min_row=4) for c in ligne if isinstance(c.value, (int, float))]
    assert nombres and any(c.hyperlink for c in nombres)
    lien = next(c.hyperlink.location for c in nombres if c.hyperlink)
    assert lien.startswith("'Détail des calculs'!A")
    ligne_detail = int(lien.rsplit("A", 1)[1])
    assert wb["Détail des calculs"].cell(ligne_detail, 1).value.startswith("C")
    # Les données de chaque graphique sont présentes (période + séries).
    graphes = [c.value for ligne in wb["Graphiques"].iter_rows(min_col=1, max_col=1) for c in ligne if c.value]
    assert "Taux d'occupation par mois" in graphes and "Période" in graphes
    assert not erreurs


def test_export_ecritures_redonnent_les_montants(site):
    """Pour un montant comptable, crédit moins débit des écritures exportées = montant affiché dans le détail."""
    pg, erreurs = ouvrir(site)
    wb, _ = exporter(site, pg, "tableaux", "resultat")
    somme = defaultdict(float)
    for r in wb["Écritures"].iter_rows(min_row=2, values_only=True):
        somme[r[0]] += (r[10] or 0) - (r[9] or 0)
    verifies = 0
    for r in wb["Détail des calculs"].iter_rows(min_row=2, values_only=True):
        if r[0] in somme and isinstance(r[3], (int, float)) and r[3] != 0:
            assert abs(abs(somme[r[0]]) - abs(r[3])) < 1, (r[0], r[1], r[3], somme[r[0]])
            verifies += 1
    assert verifies >= 10
    # Un résultat composé (produits moins charges) remonte jusqu'aux écritures de ses produits et de ses charges.
    composes = {r[0] for r in wb["Détail des calculs"].iter_rows(min_row=2, values_only=True) if str(r[1]).startswith("3. Résultat courant")}
    origines = {r[2] for r in wb["Écritures"].iter_rows(min_row=2, values_only=True) if r[0] in composes}
    assert any("Ventes" in str(o) or "Prestations" in str(o) for o in origines) and any("Salaires" in str(o) for o in origines)
    assert not erreurs


def test_export_present_sur_les_pages_de_donnees_seulement(site):
    pg, erreurs = ouvrir(site)
    for section, page, present in [("tableaux", "resultat", True), ("tresorerie", "tr_position", True), ("tableaux", "equilibre", True), ("import", "pennylane", False)]:
        pg.evaluate(f"allerA('{section}', '{page}')")
        assert (pg.locator("#btn-xlsx").count() == 1) == present, page
    assert not erreurs


def test_export_vue_reelle_sans_feuille_d_ajustements(site):
    pg, erreurs = ouvrir(site)
    pg.evaluate("etat.vue = 'reel'; allerA('tableaux', 'synthese')")
    wb, nom = exporter(site, pg, "tableaux", "synthese")
    assert nom.endswith("_reel.xlsx") and "Ajustements actifs" not in wb.sheetnames
    assert "Réelles" in str([c.value for c in wb["Résumé"]["B"]])
    assert not erreurs
