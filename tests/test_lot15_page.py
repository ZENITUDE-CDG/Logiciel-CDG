"""Lot 15 dans un vrai navigateur (données fictives) : comptes bancaires, analyse du solde, FRNG / BFR / TN,
graphiques liés à la réglette, tableau EBITDA, import des KPI (tout ou rien), en local et avec une base simulée.
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
    assert pg.evaluate("etat.hi - etat.lo") == 12                      # élargie aux 12 derniers mois
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


CSV_OK = "\\ufeffCode résidence;Résidence (facultatif);Mois (AAAA-MM);Chambres vendues;Chambres disponibles;Séjours;Clients présents (nuitées);Petits-déjeuners servis\\nRES-001;;2026-03;1;2232;;2198;1650\\nDEMO-2002;;03/2026;3000;2000;;;\\n"
CSV_KO = "Code résidence;Mois (AAAA-MM);Chambres vendues;Inconnue\\nRES-999;2026-03;10;1\\nRES-001;2026-13;10;\\nRES-001;2026-03;-5;\\nRES-001;2026-04;10;\\nRES-001;2026-04;11;\\n"


def test_controle_de_l_import(site):
    pg, _ = ouvrir(site)
    ok = pg.evaluate(f"validerImport(lireCsv('{CSV_OK}'))")
    assert ok["erreurs"] == [] and len(ok["valeurs"]) == 6
    assert {"dossier": "DEMO-2002", "mois": "2026-03", "mesure": "LN_VENDUES", "valeur": 3000} in ok["valeurs"]
    assert any("supérieur aux chambres disponibles" in a["motif"] for a in ok["avertissements"])
    ko = pg.evaluate(f"validerImport(lireCsv('{CSV_KO}'))")
    motifs = " | ".join(f"{e['ligne']}:{e['motif']}" for e in ko["erreurs"])
    assert "2:« RES-999 » inconnu" in motifs and "3:« 2026-13 »" in motifs and "4:« -5 »" in motifs and "6:déjà fourni ligne 5" in motifs
    assert any(a["colonne"] == "Inconnue" for a in ko["avertissements"])
    assert pg.evaluate("validerImport([['a', 'b'], ['1', '2']]).erreurs[0].motif").startswith("en-tête")
    pg.close()


def test_import_par_l_ecran_tout_ou_rien(site, tmp_path):
    pg, erreurs = ouvrir(site)
    pg.evaluate("choisir('GROUPE'); allerA('import', 'externes')")
    mauvais, bon = tmp_path / "mauvais.csv", tmp_path / "bon.csv"
    mauvais.write_text(CSV_KO.replace("\\n", "\n"), encoding="utf-8")
    bon.write_text(CSV_OK.replace("\\n", "\n").replace("\\ufeff", ""), encoding="utf-8")
    avant = pg.evaluate("resultatFen(['DEMO-2001'], ['2026-03'], false)['TO-SEN'].affichage")
    pg.set_input_files("#imp-fichier", str(mauvais))
    pg.wait_for_selector(".imp-err")
    assert "Import refusé" in pg.inner_text("#contenu") and not pg.query_selector("#imp-ok")
    assert pg.evaluate("MESURES_IMP.length") == 0
    pg.click("#imp-annuler")
    pg.set_input_files("#imp-fichier", str(bon))
    pg.wait_for_function("etat.import && etat.import.nom === 'bon.csv'")
    assert pg.evaluate("etat.import.R.erreurs") == []
    pg.click("#imp-ok")
    pg.wait_for_function("MESURES_IMP.length === 6")
    apres = pg.evaluate("resultatFen(['DEMO-2001'], ['2026-03'], false)['TO-SEN'].affichage")
    assert avant != apres and apres == "0,0 %"
    assert "Les Terrasses du Port" in pg.inner_text("#contenu")
    pg.click("[data-imp-sup='DEMO-2001']")
    assert pg.evaluate("resultatFen(['DEMO-2001'], ['2026-03'], false)['TO-SEN'].affichage") == avant
    assert erreurs == []
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


def test_en_ligne_administrateur_importe_dans_la_base(site, tmp_path):
    pg, erreurs = demarrer_en_ligne(site, "administrateur")
    pg.evaluate("choisir('GROUPE'); allerA('tresorerie', 'tr_banques')")
    assert "Travaux" in pg.inner_text("#contenu")
    pg.evaluate("allerA('import', 'externes')")
    bon = tmp_path / "bon.csv"
    bon.write_text("\ufeff" + CSV_OK.replace("\\n", "\n").replace("\\ufeff", ""), encoding="utf-8")
    pg.set_input_files("#imp-fichier", str(bon))
    pg.wait_for_function("etat.import && etat.import.nom === 'bon.csv'")
    assert pg.evaluate("etat.import.R.erreurs") == []
    pg.click("#imp-ok")
    pg.wait_for_function("MESURES_IMP.length === 6")
    up = pg.evaluate("journalBase.filter(q => q.op === 'upsert' && q.table === 'mesures_importees')")
    assert up[0]["conflit"] == "dossier,mois,mesure" and len(up[0]["valeurs"]) == 6
    assert pg.evaluate("localStorage.getItem('zen-mesures')") is None
    assert erreurs == []
    pg.close()


def test_en_ligne_collaborateur_sans_import_ni_comptes_bancaires(site):
    pg, _ = demarrer_en_ligne(site, "collaborateur")
    pg.evaluate("choisir('GROUPE'); allerA('tresorerie', 'tr_banques')")
    assert pg.evaluate("etat.page") == "tr_position"
    assert "Comptes bancaires" not in pg.inner_text("#lat-nav")
    pg.evaluate("allerA('import', 'externes')")
    assert not pg.query_selector("#imp-fichier") and "Réservé aux administrateurs" in pg.inner_text("#contenu")
    pg.close()
