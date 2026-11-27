"""Lots 28 à 30 dans un vrai navigateur (données fictives, avec anomalies) : analyse des écarts.

- le moteur de la page (anCalculer) donne exactement le résultat de la référence Python (zenitude/analyse/ecarts.py)
  sur plusieurs périmètres, périodes et références ;
- les dix pages s'affichent sans erreur ; chaque montant cliquable s'explique ;
- suivi des écarts (statut, commentaire, historique, montant modifié) gardé dans le navigateur en démonstration ;
- paquet d'écarts pour Claude : fichiers, référence, empreinte ;
- vue ajustée, cohérence avec la paie après import des DSN, droits (lecture seule, collaborateur).
Ignorés si Playwright n'est pas installé.
"""
import csv
import hashlib
import io
import json
import pathlib
import sys
import zipfile

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE))
import donnees_lot28  # noqa: E402
import generer_site  # noqa: E402
from zenitude.analyse import analyser  # noqa: E402

PAGES = ["an_constats", "an_natures", "an_cascade", "an_volume", "an_fournisseurs", "an_anomalies", "an_coherence", "an_social",
         "an_benchmark", "an_parametres"]
DSN = sorted((RACINE / "interface" / "demo" / "dsn").glob("*.dsn"))


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site28")
    donnees = donnees_lot28.construire(dossier / "demo")
    page = dossier / "complet.html"
    generer_site.ecrire(str(page), donnees)
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as ex:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {ex}")
        yield {"nav": nav, "page": page, "donnees": donnees}
        nav.close()


def ouvrir(site, perimetre="GROUPE", garder=False):
    ctx = site["nav"].new_context(viewport={"width": 1500, "height": 1000}, accept_downloads=True)
    pg = ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda x: erreurs.append(str(x)))
    pg.goto(site["page"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' }))"
                + ("" if garder else "; localStorage.clear()"))
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.click(f"#ecran-choix [data-p='{perimetre}']")
    pg.wait_for_selector("#rub-haut")
    return pg, erreurs


def periode(pg, debut, n, ref="prec", vue="reel"):
    pg.evaluate(f"etat.vue = '{vue}'; etat.anRef = '{ref}'; etat.lo = MOIS.indexOf('{debut}'); etat.hi = etat.lo + {n}")


def egal(a, b, chemin=""):
    if isinstance(a, dict):
        assert set(a) == set(b), (chemin, set(a) ^ set(b))
        for k in a:
            egal(a[k], b[k], chemin + "." + k)
    elif isinstance(a, list):
        assert len(a) == len(b), (chemin, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            egal(x, y, f"{chemin}[{i}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)):
        assert abs(a - b) <= 1e-9 * max(1, abs(a)), (chemin, a, b)
    else:
        assert a == b, (chemin, a, b)


CAS = [("GROUPE", ["2026-09"], "prec"), ("GROUPE", ["2026-07", "2026-08", "2026-09"], "prec"), ("GROUPE", ["2026-10"], "n1"),
       ("GROUPE", ["2026-10", "2026-11"], "moy12"), ("ACT-SENIORS", ["2026-06", "2026-07"], "prec"), ("DEMO-2001", ["2026-09"], "moy12")]


def test_page_identique_a_la_reference_python(site):
    pg, erreurs = ouvrir(site)
    D = site["donnees"]
    for perim, mois, ref in CAS:
        ds = next(p["dossiers"] for p in D["perimetres"] if p["id"] == perim)
        js = json.loads(pg.evaluate("(a) => { var A = anCalculer(a[0], a[1], a[2], null, false); delete A._res; return JSON.stringify(A); }", [ds, mois, ref]))
        py = json.loads(json.dumps(analyser(D, ds, mois, ref)))
        assert py["constats"], (perim, mois, ref)
        for k in py:
            if k not in ("version", "seuils"):
                egal(py[k], js[k], f"{perim} {ref} {k}")
        egal(py["seuils"], js["seuils"])
    # Seuils modifiés : même résultat
    ds = next(p["dossiers"] for p in D["perimetres"] if p["id"] == "GROUPE")
    S = {"pct": 0.05, "montant": 50000, "sigma": 1.5, "ecriture": 2.0, "coherence": 0.05}
    js = json.loads(pg.evaluate("(a) => { var A = anCalculer(a[0], a[1], 'prec', a[2], false); return JSON.stringify(A.constats); }", [ds, ["2026-09"], S]))
    egal(json.loads(json.dumps(analyser(D, ds, ["2026-09"], "prec", S)["constats"])), js)
    assert not erreurs


def test_pages_et_detail_des_montants(site):
    for perim in ("GROUPE", "DEMO-2001"):
        pg, erreurs = ouvrir(site, perim)
        periode(pg, "2026-07", 3)
        menu = pg.evaluate("dessinerMenu(); Array.from(document.querySelectorAll('#lat-nav .lat-item')).map(b => b.dataset.section)")
        assert menu.index("analyse") == menu.index("tableaux") + 1
        for page in PAGES:
            pg.evaluate(f"allerA('analyse', '{page}')")
            assert pg.inner_text("#contenu").strip(), page
            ko = pg.evaluate("""() => { var ko = []; document.querySelectorAll('#contenu [data-x]').forEach(function (e) {
                var s = JSON.parse(e.dataset.x), R; try { R = EXPLIQUER[s.t](s); } catch (x) { ko.push(s.t + ' : ' + x.message); return; }
                if (!R || R.titre === 'Détail indisponible') ko.push(s.t); }); return ko; }""")
            assert not ko, (perim, page, ko[:3])
        assert not erreurs, erreurs
    # Un écart se clique et s'explique dans le panneau
    pg.evaluate("allerA('analyse', 'an_constats')")
    pg.click("#an-table [data-x]")
    pg.wait_for_selector("#panneau.ouvert")
    assert "Effet sur l’EBITDA" in pg.inner_text("#panneau")
    # La référence affichée = celle du moteur, détail compris (moyenne de 12 mois)
    periode(pg, "2026-10", 2, "moy12")
    pg.evaluate("allerA('analyse', 'an_natures')")
    r = pg.evaluate("(() => { var A = anAnalyse(perimetre('DEMO-2001')), n = A.natures.find(x => x.code === 'CA'); return [n.r, EXPLIQUER.anr({ c: 'CA', d: A.dispo, m: A.mois_ref, f: A.facteur }).valeur]; })()")
    assert r[1].replace("\u202f", " ").replace("\u00a0", " ") == pg.evaluate(f"eur({r[0]} / 100)")


def test_cascade_et_volume_affiches(site):
    pg, _ = ouvrir(site)
    periode(pg, "2026-07", 3)
    pg.evaluate("allerA('analyse', 'an_cascade')")
    A = pg.evaluate("(() => { var A = anAnalyse(perimetre('GROUPE')); return [A.cascade.ebitda_v - A.cascade.ebitda_r, A.cascade.etapes.reduce((s, e) => s + e[1], 0)]; })()")
    assert A[0] == A[1]
    assert pg.locator("#contenu svg rect[data-x]").count() == 11
    pg.evaluate("allerA('analyse', 'an_volume')")
    assert "Total des 7 résidences avec nuitées" in pg.inner_text("#contenu")


def test_suivi_des_ecarts(site):
    pg, erreurs = ouvrir(site)
    periode(pg, "2026-09", 1)
    pg.evaluate("allerA('analyse', 'an_constats')")
    cle = pg.get_attribute("#an-table tbody tr:first-child", "data-cle")
    pg.click(f"[data-an-suivi='{cle}']")
    pg.select_option("#an-mod-statut", "explique")
    pg.fill("#an-mod-com", "Hausse justifiée : nouveau contrat (fictif).")
    pg.click("#an-mod-ok")
    pg.wait_for_selector("#an-modale", state="detached")
    stock = json.loads(pg.evaluate("localStorage.getItem('zen-ecarts')"))
    assert stock["suivi"][0]["cle"] == cle and stock["suivi"][0]["statut"] == "explique" and stock["journal"][0]["commentaire"].startswith("Hausse")
    assert "Expliqué" in pg.inner_text("#an-table tbody tr:first-child")
    # Filtre par statut, recherche dans le commentaire
    pg.select_option("#an-f-statut", "explique")
    assert pg.locator("#an-table tbody tr").count() == 1
    pg.select_option("#an-f-statut", "")
    pg.fill("#an-f-q", "nouveau contrat"); pg.press("#an-f-q", "Enter"); pg.evaluate("el('an-f-q').dispatchEvent(new Event('change'))")
    assert pg.locator("#an-table tbody tr").count() == 1
    # Gardé après rechargement ; montant changé depuis le commentaire signalé
    pg2 = pg
    pg2.evaluate("sessionStorage.setItem('zen-perim', 'null')")
    pg2.reload()
    pg2.wait_for_selector("#ecran-choix.visible")
    pg2.click("#ecran-choix [data-p='GROUPE']")
    pg2.wait_for_selector("#rub-haut")
    periode(pg2, "2026-09", 1)
    pg2.evaluate("AN.suivi[0].montant = 1; AN.cache = {}; allerA('analyse', 'an_constats')")
    assert "montant modifié" in pg2.inner_text("#an-table")
    assert "Le montant a changé" in " ".join(pg2.evaluate(f"EXPLIQUER.anc({{ cle: {json.dumps(cle)} }}).notes"))
    assert not erreurs


def test_paquet_pour_claude(site):
    pg, erreurs = ouvrir(site)
    periode(pg, "2026-09", 1)
    pg.evaluate("allerA('analyse', 'an_constats')")
    n = pg.evaluate("anAnalyse(perimetre('GROUPE')).tous.length")
    with pg.expect_download() as tel:
        pg.click("#an-paquet")
    z = zipfile.ZipFile(io.BytesIO(pathlib.Path(tel.value.path()).read_bytes()))
    noms = z.namelist()
    assert noms[0] == "LISEZ-MOI.md" and {"ecarts.csv", "postes.csv", "cascade.csv", "volume_prix.csv", "fournisseurs.csv", "coherence.csv", "comparaison.csv"} <= set(noms)
    lignes = list(csv.reader(io.StringIO(z.read("ecarts.csv").decode())))
    assert len(lignes) == n + 1 and lignes[0][0] == "cle"
    donnees = [x for x in noms if x.endswith(".csv")]
    emp = hashlib.sha256(b"".join((x + "\n").encode() + z.read(x) for x in donnees)).hexdigest()
    lisez = z.read("LISEZ-MOI.md").decode()
    assert "LOCAL-000001" in lisez and emp in lisez
    journal = json.loads(pg.evaluate("localStorage.getItem('zen-paquets')"))
    assert journal[0]["niveau"] == "ecarts" and journal[0]["empreinte"] == emp
    assert not erreurs


def test_vue_ajustee(site):
    pg, _ = ouvrir(site, "DEMO-2001")
    r = pg.evaluate("""(() => {
      var a = anCalculer(['DEMO-2001'], ['2026-09'], 'prec', null, true).cascade.ebitda_v;
      AJ.liste.push({ id: 'AJ-901', cle: 'x', libelle: 'Provision (fictif)', compte: '6815', type: 'provision', portee: ['DEMO-2001'], termes: [{ t: 'fixe', montant: 1000 }], actif: true, du: '2026-09', au: '2026-09' });
      ajVider();
      var b = anCalculer(['DEMO-2001'], ['2026-09'], 'prec', null, true).cascade, c = anCalculer(['DEMO-2001'], ['2026-09'], 'prec', null, false).cascade;
      return [a, b.ebitda_v, c.ebitda_v]; })()""")
    assert r[0] == r[2] and r[1] == r[0]  # 6815 (dotation) est hors EBITDA
    r = pg.evaluate("""(() => {
      AJ.liste.push({ id: 'AJ-902', cle: 'y', libelle: 'Charge (fictif)', compte: '6156', type: 'provision', portee: ['DEMO-2001'], termes: [{ t: 'fixe', montant: 1000 }], actif: true, du: '2026-09', au: '2026-09' });
      ajVider();
      return [anCalculer(['DEMO-2001'], ['2026-09'], 'prec', null, true).cascade.ebitda_v, anCalculer(['DEMO-2001'], ['2026-09'], 'prec', null, false).cascade.ebitda_v]; })()""")
    assert r[0] == r[1] - 100000


def test_coherence_avec_la_paie(site):
    pg, erreurs = ouvrir(site)
    pg.evaluate("allerA('import', 'so_import')")
    pg.set_input_files("#so-fichiers", [str(f) for f in DSN])
    pg.wait_for_selector("#so-apercu")
    for s in pg.query_selector_all("[data-so-rat]"):
        siret = s.get_attribute("data-so-rat")
        pg.select_option(f"[data-so-rat='{siret}']", "DEMO-" + siret[5:9])
    pg.click("#so-enregistrer")
    pg.wait_for_selector("#so-journal")
    periode(pg, "2026-06", 1)
    pg.evaluate("allerA('analyse', 'an_social')")
    S = pg.evaluate("anAnalyse(perimetre('GROUPE')).social")
    assert len(S["lignes"]) == 8
    s1 = [c for c in S["constats"] if c["code"] == "S1"]
    assert any(c["dossier"] == "DEMO-2003" and c["mois"] == "2026-06" and c["valeur"] - c["reference"] == -123456 for c in s1)
    for x in S["lignes"]:
        if x["delta"] is not None:
            assert x["effectif"] + x["cout"] == x["delta"]
    assert "mois en écart" in pg.inner_text("#contenu")
    # Les écarts de paie rejoignent la liste à expliquer
    assert pg.evaluate("anAnalyse(perimetre('GROUPE')).tous.some(c => c.bloc === 'social')")
    assert not erreurs


def test_droits(site):
    pg, _ = ouvrir(site)
    periode(pg, "2026-09", 1)
    pg.evaluate("D.enLigne = { email: 'l@exemple.invalid', nom: 'L', role: 'lecture' }; allerA('analyse', 'an_constats')")
    assert pg.locator("[data-an-suivi]").count() == 0
    assert "an_social" not in pg.evaluate("sousVisibles('analyse').map(x => x[0])")
    pg.evaluate("D.lot28 = true; allerA('analyse', 'an_parametres')")
    assert pg.locator("#an-p-ok").count() == 0 and pg.is_disabled("#an-p-pct")
    pg.evaluate("D.enLigne.role = 'collaborateur'; allerA('analyse', 'an_constats')")
    assert pg.locator("[data-an-suivi]").count() > 0


def test_seuils_dans_la_page(site):
    pg, erreurs = ouvrir(site)
    periode(pg, "2026-09", 1)
    avant = pg.evaluate("anAnalyse(perimetre('GROUPE')).constats.length")
    pg.evaluate("allerA('analyse', 'an_parametres')")
    pg.fill("#an-p-montant", "100000")
    pg.click("#an-p-ok")
    pg.wait_for_function("document.getElementById('an-p-msg').textContent === 'Enregistré.'")
    assert json.loads(pg.evaluate("localStorage.getItem('zen-analyse-param')"))["seuils"]["montant"] == 10000000
    assert pg.evaluate("anAnalyse(perimetre('GROUPE')).constats.length") < avant
    pg.fill("#an-p-pct", "-1")
    pg.click("#an-p-ok")
    assert "positif" in pg.inner_text("#an-p-msg")
    assert not erreurs


def test_export_excel(site):
    pg, erreurs = ouvrir(site)
    periode(pg, "2026-09", 1)
    for page in ("an_constats", "an_natures"):
        pg.evaluate(f"allerA('analyse', '{page}')")
        with pg.expect_download() as tel:
            pg.click("#btn-xlsx")
        assert zipfile.is_zipfile(tel.value.path())
    assert not erreurs
