"""Lot 24 dans un vrai navigateur (données fictives) : comptabilité du siège et trésorerie prévisionnelle.

- CA et FEES calculés par la page = référence Python (zenitude/comptabilite/fees.py), toutes résidences et tous mois,
  avec règles de CA propres, versions datées, retour au groupe, montants bruts, rubriques désactivées ou sans règle ;
- détail des calculs : CA = écritures, FEES = formule ; montants au centime ;
- versions datées par l'écran : les mois antérieurs ne changent pas ; clôture figée, puis réouverture ;
- en ligne (base simulée) : tests/test_lot24_page_en_ligne.py ;
- trésorerie : prévisions mensuelles, point bas, virement proposé, virement marqué fait, plafond.
Ignorés si Playwright n'est pas installé.
"""
import copy
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
import generer_site  # noqa: E402
from zenitude.comptabilite import fees as f  # noqa: E402

RUBRIQUES = [dict(r, actif=True) for r in f.RUBRIQUES_DEPART] + [
    {"code": "FORMATION", "libelle": "Formation", "base": "CA", "base_rubrique": None, "ordre": 80, "actif": False},
    {"code": "LOYER_SIEGE", "libelle": "Loyer siège", "base": "CA", "base_rubrique": None, "ordre": 90, "actif": True}]
REGLES = f.REGLES_DEPART + [
    {"rubrique": "DROIT_MARQUE", "dossier": "*", "mois_effet": "2026-01", "mode": "taux", "valeur": "1.5"},
    {"rubrique": "MGT_FEES", "dossier": "*", "mois_effet": "2026-06", "mode": "taux", "valeur": "8.25"},
    {"rubrique": "MGT_FEES", "dossier": "DEMO-2001", "mois_effet": "2026-03", "mode": "taux", "valeur": "6"},
    {"rubrique": "MGT_FEES", "dossier": "DEMO-2001", "mois_effet": "2026-07", "mode": "groupe", "valeur": None},
    {"rubrique": "GERANCE", "dossier": "DEMO-2002", "mois_effet": "2025-12", "mode": "montant", "valeur": "1200.50"},
    {"rubrique": "COMPTA", "dossier": "DEMO-2004", "mois_effet": "2026-02", "mode": "taux", "valeur": "33.3333"},
    {"rubrique": "FORMATION", "dossier": "*", "mois_effet": "2025-01", "mode": "montant", "valeur": "500"}]
REGLES_CA = [{"dossier": "*", "inclus": ["7"], "exclus": ["79"]}, {"dossier": "DEMO-2003", "inclus": ["706"], "exclus": []}]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site24")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    donnees = generer_site.construire(str(demo))
    complet = dossier / "complet.html"
    generer_site.ecrire(str(complet), donnees)
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield {"nav": nav, "complet": complet, "donnees": donnees}
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


def regles_de_test(pg):
    pg.evaluate("(x) => { CP.rubriques = x[0]; CP.regles = x[1].map(cpNormRegle); CP.ca_regles = x[2]; }", [RUBRIQUES, REGLES, REGLES_CA])


def test_page_identique_a_la_reference_python(site):
    pg, erreurs = ouvrir(site)
    regles_de_test(pg)
    compta, mois = site["donnees"]["calcul"]["compta"], site["donnees"]["calcul"]["mois"]
    page = pg.evaluate("(ms) => { var o = {}; D.residences.forEach(function (r) { ms.forEach(function (m) { o[r.dossier + '|' + m] = calculerFees(r.dossier, m); }); }); return o; }", mois)
    n = 0
    for r in site["donnees"]["residences"]:
        d = r["dossier"]
        for m in mois:
            ca = f.ca_mois(compta.get(d, {}), m, f.regle_ca(REGLES_CA, d))
            attendu = json.loads(json.dumps(f.calculer(RUBRIQUES, REGLES, ca, d, m)))
            assert page[f"{d}|{m}"] == attendu, (d, m)
            n += 1 if ca is not None else 0
    assert n > 50  # des mois calculables, pas seulement des « non calculable »
    # cas couverts : CA propre (706), exclusion 79, versions datées, retour au groupe, montant brut, désactivée, sans règle
    x = page["DEMO-2001|2026-04"]
    assert {l["code"]: l["valeur"] for l in x["lignes"]}["MGT_FEES"] == "6" and "FORMATION" not in [l["code"] for l in x["lignes"]]
    assert {l["code"]: l["motif"] for l in x["lignes"]}["LOYER_SIEGE"] == "non paramétré"
    assert {l["code"]: l["valeur"] for l in page["DEMO-2001|2026-08"]["lignes"]}["MGT_FEES"] == "8.25"
    assert erreurs == []
    pg.close()


def test_pages_et_detail_des_calculs(site):
    pg, erreurs = ouvrir(site)
    regles_de_test(pg)
    pg.evaluate("allerA('comptabilite', 'cp_ca')")
    pg.wait_for_selector(".cp-tab")
    assert "Chiffre d’affaires" in pg.inner_text("#contenu h1") and "sauf 79" in pg.inner_text(".cp-tab")
    # CA d'une case = écritures du détail, contrôle exact, au centime
    pg.click(".cp-tab tbody tr:first-child td[data-x]")
    pg.wait_for_selector("#panneau.ouvert")
    assert "exactement" in pg.inner_text("#pan-corps") and "," in pg.inner_text(".pan-valeur")
    pg.evaluate("fermerExplication()")
    pg.evaluate("etat.cpMois = '2026-04'; allerA('comptabilite', 'cp_fees')")
    pg.wait_for_selector(".cp-fees")
    ca = pg.evaluate("caMois('DEMO-2002', '2026-04')")
    ligne = pg.locator(".cp-fees tbody tr", has_text="Le Belvédère")
    assert pg.evaluate("eurCt(caMois('DEMO-2002', '2026-04'))") in ligne.inner_text()
    assert "1 200,50 €" in ligne.inner_text()  # gérance en montant brut, au centime
    attendu_mf = f.appliquer_taux(ca, "8")
    assert pg.evaluate(f"eurCt({attendu_mf})") in ligne.inner_text()
    ligne.locator("td[data-x]").nth(2).click()  # management fees
    pg.wait_for_selector("#panneau.ouvert")
    corps = pg.inner_text("#panneau")
    assert "CA du mois × 8 %" in corps and "règle du groupe" in corps
    assert "Équilibrée" not in ligne.inner_text()  # gérance en montant : répartition différente des management fees
    assert erreurs == []
    pg.close()


def test_version_datee_cloture_et_reouverture(site):
    pg, erreurs = ouvrir(site, "DEMO-2006")
    page = lambda m: pg.evaluate(f"calculerFees('DEMO-2006', '{m}').lignes.find(function (l) {{ return l.code === 'MGT_FEES'; }}).montant")  # noqa: E731
    avant = {m: page(m) for m in ("2026-03", "2026-04", "2026-05")}
    # Clôture de mars par l'écran
    pg.evaluate("etat.cpMois = '2026-03'; allerA('comptabilite', 'cp_fees')")
    pg.click("[data-clore='DEMO-2006']")
    pg.wait_for_selector("[data-rouvrir='DEMO-2006']")
    assert pg.evaluate("CP.clotures.length") == 1
    contenu = pg.evaluate("CP.clotures[0].contenu")
    compta = json.loads(json.dumps(pg.evaluate("D.calcul.compta['DEMO-2006']")))
    assert contenu == json.loads(json.dumps(f.instantane([dict(r, actif=True) for r in f.RUBRIQUES_DEPART], f.REGLES_DEPART, [], compta, "DEMO-2006", "2026-03")))
    # Nouvelle version du groupe à partir de mars (10 %) : mars est clôturé, il ne bouge pas ; avril change
    pg.evaluate("etat.cpMois = '2026-03'; allerA('comptabilite', 'cp_parametrage')")
    pg.click("[data-cel='MGT_FEES|*']")
    pg.wait_for_selector("#modale-cp")
    pg.select_option("#cp-mode", "taux")
    pg.fill("#cp-val", "10")
    pg.fill("#cp-effet", "2026-04")
    pg.click("#cp-ok")
    pg.wait_for_selector("#modale-cp", state="detached")
    assert page("2026-03") == avant["2026-03"] and page("2026-04") != avant["2026-04"]
    assert pg.evaluate("feesDe('DEMO-2006', '2026-03').lignes.find(function (l) { return l.code === 'MGT_FEES'; }).montant") == avant["2026-03"]
    assert "Règle" in pg.inner_text("#cp-journal") and "10 %" in pg.inner_text("#cp-journal") and "Clôture" in pg.inner_text("#cp-journal")
    # Règle de CA propre : la colonne CA de la page CA l'indique
    pg.click("#cp-ca-go")
    pg.fill("#cp-inclus", "706, 708")
    pg.click("#cp-ok")
    pg.wait_for_function("CP.ca_regles.length === 1")
    assert pg.evaluate("regleCa('DEMO-2006').inclus") == ["706", "708"]
    # Réouverture : recalcul avec le CA et les règles du jour
    pg.evaluate("etat.cpMois = '2026-03'; allerA('comptabilite', 'cp_fees')")
    pg.click("[data-rouvrir='DEMO-2006']")
    pg.wait_for_selector("[data-clore='DEMO-2006']")
    assert pg.evaluate("CP.clotures.length") == 0
    # Mémorisé dans le navigateur (démonstration locale)
    pg.reload()
    pg.wait_for_selector("#rub-haut")
    assert pg.evaluate("CP.regles.length") == len(f.REGLES_DEPART) + 1 and pg.evaluate("CP.journal.length") >= 4
    assert erreurs == []
    pg.close()


def test_tresorerie_previsions_et_virements(site):
    pg, erreurs = ouvrir(site, "DEMO-2006")
    pg.evaluate("etat.tpRef = '2026-11-01'; etat.tpHorizon = '30'")
    pg.evaluate("allerA('tresorerie', 'tr_previsions')")
    pg.wait_for_selector("#tp-virements")
    sec = pg.evaluate("calculTreso({ dossiers: ['DEMO-2006'] }).residences[0].comptes.find(function (c) { return c.c === '5122'; })")
    assert sec["s0"] == pg.evaluate("soldeAu('DEMO-2006', '5122', '2026-11-01')")
    # Prévision mensuelle de décaissement sur le compte secondaire : 3 occurrences sur 90 jours
    pg.click("#tp-ajout")
    pg.select_option("#tp-c", "5122")
    pg.fill("#tp-lib", "Loyer du local (fictif)")
    pg.fill("#tp-mnt", "15000")
    pg.fill("#tp-date", "2026-11-05")
    pg.select_option("#tp-rec", "mensuelle")
    pg.click("#tp-ok")
    pg.wait_for_function("TP.previsions.length === 1")
    assert pg.evaluate("occurrences(TP.previsions[0], '2026-11-01', '2027-01-30')") == ["2026-11-05", "2026-12-05", "2027-01-05"]
    R = pg.evaluate("calculTreso({ dossiers: ['DEMO-2006'] }).residences[0]")
    c5122 = next(c for c in R["comptes"] if c["c"] == "5122")
    assert c5122["pr"]["dec"] == 1500000 and c5122["pr"]["bas"] == sec["s0"] - 1500000 and c5122["pr"]["dateBas"] == "2026-11-05"
    v = R["V"]["liste"]
    assert len(v) == 1 and v[0]["vers"] == "5122" and v[0]["de"] == "512" and v[0]["montant"] >= 1500000 - sec["s0"]
    assert "Loyer du local" in pg.inner_text("#tp-prev")
    # Marquer le virement fait : il compte comme mouvement en attente et n'est plus proposé
    pg.click("[data-fait='0']")
    pg.wait_for_function("TP.virements.length === 1")
    R2 = pg.evaluate("calculTreso({ dossiers: ['DEMO-2006'] }).residences[0]")
    assert R2["V"]["liste"] == [] and "Pas encore" in pg.inner_text("#tp-faits")
    # Plafond : sans la prévision ni le virement, l'excédent du secondaire au-dessus de 1 € remonte vers le principal
    pg.evaluate("TP.previsions[0].actif = false; TP.virements = []")
    pg.evaluate("BQP['DEMO-2006|5122'] = { libelle: '', role: 'secondaire', solde_min: 0, solde_max: 100 }; BQP['DEMO-2006|512'] = { libelle: '', role: 'principal', solde_min: null, solde_max: null }")
    R3 = pg.evaluate("calculTreso({ dossiers: ['DEMO-2006'] }).residences[0]")
    rem = [x for x in R3["V"]["liste"] if x["de"] == "5122" and x["vers"] == "512" and "plafond" in x["motif"]]
    assert len(rem) == 1 and rem[0]["montant"] == (sec["s0"] - 100) // 100 * 100
    pg.evaluate("TP.previsions[0].actif = true")
    # Détail des encaissements prévus
    pg.evaluate("majContenu()")
    pg.click(".tp-tab td[data-x*='\"dec\"'] >> nth=1")
    pg.wait_for_selector("#panneau.ouvert")
    assert "Loyer du local" in pg.inner_text("#pan-corps")
    assert erreurs == []
    pg.close()
