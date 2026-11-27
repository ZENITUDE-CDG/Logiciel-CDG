"""Lot 25 dans un vrai navigateur (données fictives) : paquet pour Claude et missions.

- les fichiers construits par la page (socleConstruire) sont exactement ceux de la référence Python
  (zenitude/socle/paquet.py), sur plusieurs périmètres et périodes, avec des anomalies fictives ajoutées ;
- le bouton télécharge un .zip complet (CSV, LISEZ-MOI.md, MISSION.md, synthese.xlsx lisible) ;
- missions : code, catégorie, livrables, versions (chaque modification crée une version), archivage, recherche, copie ;
- historique : chaque paquet reçoit une référence (citée dans LISEZ-MOI.md et MISSION.md avec l'empreinte des
  données) et le document produit se note ensuite.
Ignorés si Playwright n'est pas installé.
"""
import copy
import csv
import io
import pathlib
import sys
import zipfile

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
from zenitude import socle  # noqa: E402


def anomalies(donnees):
    """Ajoute à DEMO-2001 des écritures fictives qui déclenchent les contrôles C05 à C10."""
    d = copy.deepcopy(donnees)
    def e(i, date, j, piece, compte, lib, m, tiers=""):
        return [f"{piece}-{i}", date, j, piece, compte, lib, m, tiers, "", ""]
    d["ecritures"]["DEMO-2001"] += [
        e(1, "2026-03-12", "HA", "ZZ1", "401", "Linge (fictif)", 33300, "FOU-ZZ"), e(2, "2026-03-12", "HA", "ZZ1", "6135", "Linge (fictif)", -33300),
        e(1, "2026-03-15", "HA", "ZZ2", "401", "Linge (fictif)", 33300, "FOU-ZZ"), e(2, "2026-03-15", "HA", "ZZ2", "6135", "Linge (fictif)", -33300),
        e(1, "2026-03-20", "BQ", "ZZ3", "401", "Acompte (fictif)", -7700, "FOU-ACOMPTE"), e(2, "2026-03-20", "BQ", "ZZ3", "512", "Acompte (fictif)", 7700),
        e(1, "2026-03-21", "BQ", "ZZ4", "512", "Avance, client \"X\" (fictif)", -2500), e(2, "2026-03-21", "BQ", "ZZ4", "411", "Avance (fictif)", 2500, "CLI-ZZ"),
        e(1, "2026-03-22", "BQ", "ZZ5", "471", "Inconnu (fictif)", -999), e(2, "2026-03-22", "BQ", "ZZ5", "512", "Inconnu (fictif)", 999),
        e(1, "2026-03-23", "BQ", "ZZ6", "580", "Virement (fictif)", -5000), e(2, "2026-03-23", "BQ", "ZZ6", "512", "Virement (fictif)", 5000),
        e(1, "2026-03-24", "VT", "ZZ7", "411", "Taxe de séjour (fictif)", -1500, "CLI001"), e(2, "2026-03-24", "VT", "ZZ7", "708", "Taxe de séjour (fictif)", 1500)]
    return d


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site25")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    donnees = anomalies(generer_site.construire(str(demo)))
    complet = dossier / "complet.html"
    generer_site.ecrire(str(complet), donnees)
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as ex:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {ex}")
        yield {"nav": nav, "complet": complet, "donnees": donnees}
        nav.close()


REPONSES = []


def ouvrir(site, perimetre="GROUPE"):
    ctx = site["nav"].new_context(viewport={"width": 1500, "height": 1000}, accept_downloads=True, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda x: erreurs.append(str(x)))
    pg.on("dialog", lambda x: x.accept(REPONSES.pop(0)) if REPONSES else x.accept())
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.click(f"#ecran-choix [data-p='{perimetre}']")
    pg.wait_for_selector("#rub-haut")
    return pg, erreurs


def dossiers(site, per):
    return next(p for p in site["donnees"]["perimetres"] if p["id"] == per)["dossiers"]


@pytest.mark.parametrize("per, du, au, complet", [("GROUPE", "2025-10", "2026-09", True), ("DEMO-2001", "2025-10", "2026-09", True),
                                                 ("DEMO-2003", "2026-01", "2027-06", False), ("GROUPE", "2026-03", "2026-03", False)])
def test_page_identique_a_la_reference_python(site, per, du, au, complet):
    pg, erreurs = ouvrir(site)
    ds = dossiers(site, per)
    page = pg.evaluate("(a) => { var P = socleConstruire(a[0], a[1], a[2], a[3], { perimetre: 'P', genere_le: 'G', auteur: 'A' }); var o = {}; P.fichiers.forEach(function (f) { o[f.nom] = f.texte; }); return o; }",
                       [ds, du, au, complet])
    ref = socle.construire(site["donnees"], ds, du, au, complet=complet, genere_le="G", auteur="A", perimetre="P")
    assert list(page) == list(ref)
    for nom in ref:
        assert page[nom] == ref[nom], nom
    if per in ("GROUPE", "DEMO-2001") and du <= "2026-03" <= au:
        codes = {r["code"] for r in csv.DictReader(io.StringIO(ref["controles.csv"])) if r["dossier"] == "DEMO-2001"}
        assert {"C05", "C06", "C07", "C08", "C09", "C10"} <= codes
    assert erreurs == []
    pg.close()


def test_telechargement_du_paquet_avec_mission(site):
    pg, erreurs = ouvrir(site)
    # une mission créée par l'écran, puis choisie pour le paquet
    pg.evaluate("allerA('rapports', 'missions')")
    pg.click("#mi-nouvelle")
    pg.fill("#mi-code", "normatif-test")
    pg.fill("#mi-cat", "Budget")
    pg.fill("#mi-livrables", "Normatif_<dossier>.xlsx")
    pg.fill("#mi-titre", "Normatif de test")
    pg.fill("#mi-consignes", "Hypothèse : taux Choice 4,6 %.\nLivrable : synthèse.")
    pg.click("#mi-ok")
    pg.wait_for_selector("text=Normatif de test")
    pg.evaluate("allerA('rapports', 'claude')")
    pg.wait_for_selector("#soc-telecharger")
    assert "Contrôles automatiques" in pg.inner_text("#contenu") and "Ajusté" not in pg.inner_text("#zone-periode")  # paquet toujours en réel
    pg.select_option("#soc-mission", label="Normatif de test (NORMATIF-TEST, v1)")
    with pg.expect_download() as dl:
        pg.click("#soc-telecharger")
    chemin = dl.value.path()
    assert dl.value.suggested_filename.startswith("Paquet_Claude_LOCAL-000001_Groupe") and dl.value.suggested_filename.endswith(".zip")
    z = zipfile.ZipFile(chemin)
    noms = z.namelist()
    assert noms[:2] == ["LISEZ-MOI.md", "MISSION.md"] and "synthese.xlsx" in noms and "ecritures.csv" in noms
    mission = z.read("MISSION.md").decode("utf-8")
    assert mission.startswith("# Mission : Normatif de test\n\n- Code : NORMATIF-TEST ; version 1\n- Référence du paquet : LOCAL-000001")
    assert "taux Choice 4,6 %" in mission and "n’interroge pas Pennylane" in mission and mission.endswith("## Livrables attendus\n\nNormatif_<dossier>.xlsx\n")
    lisez = z.read("LISEZ-MOI.md").decode("utf-8")
    assert "par demo@exemple.invalid" in lisez and "Référence du paquet : LOCAL-000001" in lisez
    emp = socle.empreinte([(n, z.read(n).decode("utf-8")) for n in noms if n.endswith(".csv")])
    assert "empreinte des données : " + emp in lisez and emp in mission
    # historique : le paquet apparaît avec sa mission, puis on note le document produit
    pg.wait_for_selector("text=LOCAL-000001")
    assert "NORMATIF-TEST v1" in pg.inner_text("#contenu")
    REPONSES[:] = ["https://exemple.invalid/Normatif_Groupe.xlsx", "première version"]
    pg.click("[data-noter='1']")
    pg.wait_for_selector("a[href='https://exemple.invalid/Normatif_Groupe.xlsx']")
    assert "première version" in pg.inner_text("#contenu")
    # CSV identiques à la référence pour la période de la page
    f = pg.evaluate("fenetre()")
    ref = socle.construire(site["donnees"], dossiers(site, "GROUPE"), f[0], f[-1], complet=True)
    for nom in ref:
        if nom.endswith(".csv"):
            assert z.read(nom).decode("utf-8") == ref[nom], nom
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(z.read("synthese.xlsx")))
    assert wb.sheetnames == ["Lisez-moi", "Résidences", "CR de gestion", "Contrôles"]
    assert wb["Résidences"].max_row == 1 + len(dossiers(site, "GROUPE"))
    assert erreurs == []
    pg.close()


def test_niveau_synthese_et_copie(site):
    pg, erreurs = ouvrir(site, "DEMO-2002")
    pg.evaluate("allerA('rapports', 'claude')")
    pg.wait_for_selector("#soc-niveau")
    assert "ecritures.csv" in pg.inner_text("#contenu")  # une résidence : complet par défaut
    pg.select_option("#soc-niveau", "synthese")
    pg.wait_for_function("!document.querySelector('#contenu').innerText.includes('ecritures.csv')")
    pg.click("#soc-copier")
    pg.wait_for_function("document.querySelector('#soc-etat').textContent.includes('copié')")
    assert pg.evaluate("navigator.clipboard.readText()").startswith(socle.ENTETE_MISSION)
    assert erreurs == []
    pg.close()


def test_missions_modifier_archiver_copier(site):
    pg, erreurs = ouvrir(site)
    pg.evaluate("allerA('rapports', 'missions')")
    pg.click("[data-mi-modifier='demo-1']")
    pg.fill("#mi-titre", "")
    pg.fill("#mi-code", "x")
    pg.click("#mi-ok")
    assert "titre est obligatoire" in pg.inner_text("#mi-erreur") and "Code" in pg.inner_text("#mi-erreur")
    pg.fill("#mi-code", "LECTURE-RESIDENCE")
    pg.fill("#mi-titre", "Lecture d’une résidence (modifiée)")
    pg.click("#mi-ok")
    pg.wait_for_selector("text=Lecture d’une résidence (modifiée)")
    assert "v2" in pg.inner_text("#contenu table")  # la modification a créé une version
    pg.click("[data-mi-copier='demo-1']")
    pg.wait_for_function("document.querySelector('#mi-etat').textContent.includes('copié')")
    texte = pg.evaluate("navigator.clipboard.readText()")
    assert texte.startswith("# Mission : Lecture d’une résidence (modifiée)\n\n- Code : LECTURE-RESIDENCE ; version 2") and socle.ENTETE_MISSION in texte
    pg.click("[data-mi-versions='demo-1']")
    pg.click("[data-v-copier='1']")
    pg.wait_for_function("navigator.clipboard.readText().then(function (t) { return t.indexOf('version 1') > 0; })")
    assert pg.evaluate("navigator.clipboard.readText()").startswith("# Mission : Exemple : lecture d’une résidence")
    pg.fill("#mi-rech", "introuvable")
    pg.press("#mi-rech", "Enter")
    pg.wait_for_selector("text=Aucune mission ne correspond")
    pg.fill("#mi-rech", "")
    pg.press("#mi-rech", "Enter")
    pg.click("[data-mi-archiver='demo-1']")
    pg.wait_for_selector("text=archivée")
    pg.evaluate("allerA('rapports', 'claude')")
    assert "Lecture d’une résidence" not in pg.inner_text("#soc-mission")  # une mission archivée ne se joint plus
    assert erreurs == []
    pg.close()


def test_chargement_en_ligne_lit_les_tables_du_lot25():
    texte = (RACINE / "interface" / "gabarit.html").read_text(encoding="utf-8")
    assert 'from("missions_claude")' in texte and 'from("paquets_claude")' in texte
    assert "socleConstruire" in (RACINE / "index.html").read_text(encoding="utf-8")  # page publiée régénérée
