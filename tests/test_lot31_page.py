"""Lot 31 dans un vrai navigateur (données fictives, démonstration locale) : page Société, création, noms et codes
des autres outils, classements et groupes, exercices N-2 à N+2, cinq derniers ajustements, archivage.
Ignorés si Playwright est absent."""
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
    dossier = tmp_path_factory.mktemp("site31")
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
    pg = site["nav"].new_page(viewport={"width": 1400, "height": 900})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    sel = "#choix-groupes" if perimetre == "GROUPE" else "#choix-res"
    pg.click(f"{sel} button[data-p={perimetre}]")
    pg.click("#lat-nav [data-section=residence]")
    pg.wait_for_selector("#contenu h1")
    return pg, erreurs


def test_sans_modification_les_perimetres_ne_changent_pas(site):
    pg, err = ouvrir(site)
    avant = pg.evaluate("JSON.stringify(D.perimetres)")
    pg.evaluate("socAppliquer()")
    assert pg.evaluate("JSON.stringify(D.perimetres)") == avant
    assert pg.inner_text("#contenu h1") == "Sociétés" and not err


def test_creer_une_societe_et_la_retrouver(site):
    pg, err = ouvrir(site)
    pg.click("#soc-nouvelle")
    assert pg.input_value("#soc-f-id") == "RES-009"
    pg.click("#soc-mod-ok")
    assert "nom est obligatoire" in pg.inner_text("#soc-mod-err")
    pg.fill("#soc-f-nom", "Résidence Nouvelle (fictive)")
    pg.fill("#soc-f-siren", "12345")
    pg.click("#soc-mod-ok")
    assert "SIREN" in pg.inner_text("#soc-mod-err")
    pg.fill("#soc-f-siren", "123 456 789")
    pg.click("#soc-mod-ok")
    pg.wait_for_selector("#soc-modale", state="detached")
    ligne = pg.inner_text("tr[data-soc=RES-009]")
    assert "Résidence Nouvelle" in ligne and "En attente de données" in ligne
    pg.reload()
    pg.click("#lat-nav [data-section=residence]")
    pg.wait_for_selector("tr[data-soc]")
    assert pg.locator("tr[data-soc=RES-009]").count() == 1  # gardée dans le navigateur
    assert "création" in pg.inner_text("#contenu") and not err


def test_noms_et_codes_des_autres_outils(site):
    pg, err = ouvrir(site, "DEMO-2006")
    pg.fill(".soc-id-lib", "Mews")
    pg.fill(".soc-id-code", "TRT")
    pg.click(".soc-id-ok")
    pg.wait_for_selector("text=TRT")
    assert pg.evaluate("SOC.ids.length") == 1
    pg.evaluate("choisir('DEMO-2001')")
    pg.fill(".soc-id-lib", "mews")
    pg.fill(".soc-id-code", "trt")
    pg.click(".soc-id-ok")
    assert "déjà attribué à Campus Rive Gauche" in pg.inner_text(".soc-id-err")
    assert pg.evaluate("SOC.ids.length") == 1
    # recherche par code dans le choix des sociétés
    pg.click("#btn-zenitude")
    pg.fill("#choix-rech", "trt")
    assert pg.locator("#choix-res button[data-p]").count() == 1
    assert pg.locator("#choix-res button[data-p=DEMO-2006]").count() == 1 and not err


def test_classement_exclusif_et_groupes(site):
    pg, err = ouvrir(site)
    pg.fill("#soc-c-lib", "Responsable régional")
    pg.click("#soc-c-ok")
    pg.wait_for_selector(".soc-g-nouv[data-c=CL-RESPONSABLE-REGIONAL]")
    pg.click(".soc-g-nouv[data-c=CL-RESPONSABLE-REGIONAL]")
    pg.fill("#soc-g-lib", "RM Est")
    pg.check(".soc-g-m[value=RES-006]")
    pg.check(".soc-g-m[value=RES-002]")
    pg.click("#soc-g-ok")
    pg.wait_for_selector("#soc-modale-g", state="detached")
    p = pg.evaluate("perimetre('GRP-RM-EST')")
    assert p["dossiers"] == ["DEMO-2002", "DEMO-2006"] and p["classement"] == "Responsable régional"
    pg.click(".soc-g-nouv[data-c=CL-RESPONSABLE-REGIONAL]")
    pg.fill("#soc-g-lib", "RM Ouest")
    pg.check(".soc-g-m[value=RES-006]")
    pg.click("#soc-g-ok")
    assert "classement exclusif" in pg.inner_text("#soc-g-err")
    pg.click("#soc-g-annuler")
    # renommer puis supprimer
    pg.click(".soc-g-mod[data-g=GRP-RM-EST]")
    pg.fill("#soc-g-lib", "RM Grand Est")
    pg.uncheck(".soc-g-m[value=RES-002]")
    pg.click("#soc-g-ok")
    pg.wait_for_selector("#soc-modale-g", state="detached")
    assert pg.evaluate("perimetre('GRP-RM-EST').libelle") == "RM Grand Est"
    assert pg.evaluate("perimetre('GRP-RM-EST').dossiers") == ["DEMO-2006"]
    pg.click(".soc-g-sup[data-g=GRP-RM-EST]")
    assert pg.evaluate("perimetre('GRP-RM-EST')") is None
    pg.click(".soc-c-sup[data-c=CL-RESPONSABLE-REGIONAL]")
    assert pg.evaluate("SOC.cls.length") == 0 and not err


def test_fiche_exercices_et_ajustements(site):
    pg, err = ouvrir(site, "DEMO-2006")
    lignes = pg.locator("#contenu table").nth(0).locator("tbody tr")
    rangs = [lignes.nth(i).locator("td").nth(0).inner_text().split()[0] for i in range(lignes.count())]
    assert rangs == ["N-2", "N-1", "N", "N+1", "N+2"]
    assert pg.locator("#soc-ex-tous").count() == 0
    pg.evaluate("""D.imports['DEMO-2006'].unshift({ rang: 'N-3', debut: '2022-10-01', fin: '2023-06-30', ecritures: 0, periode_importee: null }); majContenu()""")
    assert pg.inner_text("#soc-ex-tous") == "Voir plus (1)"
    pg.click("#soc-ex-tous")
    assert "9 mois" in pg.inner_text("#contenu table >> nth=0")
    for i in range(7):
        pg.evaluate(f"""AJ.liste.push({{ id: 'AJ-90{i}', actif: true, type: 'provision', libelle: 'Provision {i}', compte: '681000', mode: 'regle', portee: 'tous',
          termes: [{{ t: 'fixe', montant: '1' }}], du: '', au: '', modifie_le: '2026-11-0{i + 1}T10:00:00Z', modifie_par: 'auteur{i}@exemple.invalid' }})""")
    pg.evaluate("ajVider(); majContenu()")
    texte = pg.inner_text("#contenu")
    assert "5 derniers sur 7" in texte
    assert "Provision 6" in texte and "auteur6@exemple.invalid" in texte and "Provision 1" not in texte
    pg.click("#soc-aj-tous")
    assert pg.evaluate("etat.page") == "provisions" and not err


def test_modifier_et_archiver(site):
    pg, err = ouvrir(site, "DEMO-2006")
    pg.click("#soc-modifier")
    pg.fill("#soc-f-region", "Région Centre")
    pg.fill("#soc-f-raison_sociale", "")
    pg.click("#soc-mod-ok")
    pg.wait_for_selector("#soc-modale", state="detached")
    assert pg.evaluate("residence('DEMO-2006').region") == "Région Centre"
    assert pg.evaluate("residence('DEMO-2006').societe") == "Société Campus Rive Gauche (fictive)"  # vide = configuration
    assert pg.evaluate("perimetre('REG-RÉGION-CENTRE').dossiers") == ["DEMO-2006"]
    pg.click("#soc-archiver")
    assert "Société archivée" in pg.inner_text("#contenu")
    pg.click("#btn-zenitude")
    assert pg.locator("#choix-res button[data-p=DEMO-2006]").count() == 0
    pg.click("#choix-groupes button[data-p=GROUPE]")
    pg.click("#lat-nav [data-section=residence]")
    assert pg.locator("tr[data-p=DEMO-2006]").count() == 0
    pg.check("#soc-archives")
    assert pg.locator("tr[data-p=DEMO-2006]").count() == 1
    assert "archivage" in pg.inner_text("#contenu") and not err


def test_lecture_seule_sans_bouton(site):
    pg, err = ouvrir(site, "DEMO-2006")
    pg.evaluate("D.enLigne = { email: 'l@exemple.invalid', nom: 'L', role: 'lecture' }; D.lot31 = true; majContenu()")
    assert pg.locator("#soc-modifier").count() == 0 and pg.locator(".soc-id-ok").count() == 0
    pg.evaluate("D.lot31 = false; D.enLigne.role = 'administrateur'; majContenu()")
    assert "Migration 020 non appliquée" in pg.inner_text("#contenu") and pg.locator("#soc-modifier").count() == 0 and not err
