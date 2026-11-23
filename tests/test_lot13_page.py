"""Lot 13 : page en ligne (décision 0007), dans un vrai navigateur. Données fictives.

1. La page recompose, à partir des morceaux publiés dans la base, exactement les données du site ;
   avec une partie des résidences seulement, elle ne contient rien des autres.
2. Démarrage en ligne avec un client de base simulé : parc d'un collaborateur, droits affichés,
   ajustement enregistré dans la base (et non dans le navigateur).
(Le lissage par compte du lot 13 est remplacé par le lissage d'écritures du lot 14 : tests/test_lot14_page.py.)
Ignorés si Playwright n'est pas installé (pip install playwright && playwright install chromium).
"""
import json
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
import publier_supabase as pub  # noqa: E402
from zenitude.config import couverture  # noqa: E402
from zenitude.kpi.mesures import charger_exploitation  # noqa: E402

COMPARES = ("residences", "finance", "ecritures", "couverture", "imports", "tresorerie", "calcul", "plan", "journaux",
            "perimetres", "kpi", "lignes_ebitda", "lignes_sig", "cr_lignes", "mois", "periodes")

CLIENT_SIMULE = """
window.journalBase = [];
window.clientSimule = function (tables) {
  var prochain = 100;
  function executer(q) {
    journalBase.push(JSON.parse(JSON.stringify(q)));
    var lignes = tables[q.table] || (tables[q.table] = []);
    var garde = function (l) { return q.filtres.every(function (f) { return l[f[0]] === f[1]; }); };
    if (q.op === "select") { var r = lignes.filter(garde); return { data: q.unique ? (r[0] || null) : r, error: null }; }
    if (q.op === "insert") {
      var v = Object.assign({}, q.valeurs);
      if (q.table === "ajustements") Object.assign(v, { id: prochain++, cree_par: "collab@exemple.invalid", modifie_par: "collab@exemple.invalid" });
      lignes.push(v); return { data: [v], error: null };
    }
    if (q.op === "update") { var u = lignes.filter(garde); u.forEach(function (l) { Object.assign(l, q.valeurs); }); return { data: u, error: null }; }
    if (q.op === "delete") { var d = lignes.filter(garde); tables[q.table] = lignes.filter(function (l) { return !garde(l); }); return { data: d, error: null }; }
  }
  return { from: function (table) {
    var q = { table: table, op: "select", filtres: [], valeurs: null, unique: false };
    var api = {
      select: function () { return api; }, order: function () { return api; },
      eq: function (k, v) { q.filtres.push([k, v]); return api; },
      maybeSingle: function () { q.unique = true; return api; },
      insert: function (v) { q.op = "insert"; q.valeurs = v; return api; },
      update: function (v) { q.op = "update"; q.valeurs = v; return api; },
      delete: function () { q.op = "delete"; return api; },
      then: function (ok, ko) { return Promise.resolve().then(function () { return executer(q); }).then(ok, ko); }
    };
    return api;
  } };
};
"""


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site13")
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
    # Aller-retour JSON : exactement ce que la base renverrait.
    lignes = json.loads(json.dumps([{"residence_id": l["residence_id"], "contenu": l["contenu"]} for l in lignes]))
    with playwright.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield {"navigateur": navigateur, "complet": complet, "vide": vide, "donnees": donnees,
               "commun": json.loads(json.dumps(commune["contenu"])), "lignes": lignes}
        navigateur.close()


def ouvrir(site, page_html):
    pg = site["navigateur"].new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(page_html.as_uri())
    return pg, erreurs


def test_assemblage_identique_au_generateur(site):
    pg, erreurs = ouvrir(site, site["complet"])
    X = pg.evaluate("([c, l]) => assemblerDonnees(c, l, [], [], null)", [site["commun"], site["lignes"]])
    D = json.loads(json.dumps(site["donnees"]))
    for cle in COMPARES:
        assert X[cle] == D[cle], cle
    assert X["meta"]["nb_ecritures"] == D["meta"]["nb_ecritures"]
    assert X["meta"]["nb_mesures"] == D["meta"]["nb_mesures"]
    assert erreurs == []
    pg.close()


def test_assemblage_restreint_au_parc(site):
    pg, _ = ouvrir(site, site["complet"])
    seniors = [l for l in site["lignes"] if l["residence_id"] in ("RES-003", "RES-004", "RES-005")]
    groupes = [{"id": "GRP-SENIORS", "libelle": "Résidences seniors (fictif)"}]
    liens = [{"residence_id": r, "groupe_id": "GRP-SENIORS"} for r in ("RES-003", "RES-004", "RES-005", "RES-001")]
    X = pg.evaluate("([c, l, g, k]) => assemblerDonnees(c, l, g, k, { email: 'c@exemple.invalid', nom: 'C', role: 'collaborateur' })",
                    [site["commun"], seniors, groupes, liens])
    texte = json.dumps(X, ensure_ascii=False)
    for autre in ("DEMO-2001", "DEMO-2002", "DEMO-2006", "DEMO-2007", "DEMO-2008", "Les Terrasses du Port"):
        assert autre not in texte
    p = {x["id"]: x for x in X["perimetres"]}
    assert p["GROUPE"]["libelle"] == "Mon parc"
    assert sorted(p["GROUPE"]["dossiers"]) == ["DEMO-2003", "DEMO-2004", "DEMO-2005"]
    assert p["GRP-SEN-SUD"]["dossiers"] == ["DEMO-2004"]  # groupe de la configuration, limité au parc
    assert p["GRP-SENIORS"]["type"] == "groupe-cree" and p["GRP-SENIORS"]["dossiers"] == ["DEMO-2003", "DEMO-2004", "DEMO-2005"]
    assert X["enLigne"]["role"] == "collaborateur"
    pg.close()


def test_page_en_ligne_sans_donnees_ni_application(site):
    pg, erreurs = ouvrir(site, site["vide"])
    assert pg.evaluate("D") is None
    assert pg.evaluate("typeof tableauJS") == "undefined"
    assert "Page en ligne" in pg.inner_text("#ecran-demarrage")
    assert erreurs == []
    pg.close()


def test_demarrage_en_ligne_simule(site):
    pg, erreurs = ouvrir(site, site["vide"])
    pg.evaluate(CLIENT_SIMULE)
    seniors = [l for l in site["lignes"] if l["residence_id"] in ("RES-003", "RES-004", "RES-005")]
    tables = {
        "donnees_communes": [{"id": "SITE", "contenu": site["commun"]}],
        "donnees_residences": seniors,
        "groupes": [{"id": "GRP-SENIORS", "libelle": "Résidences seniors (fictif)"}],
        "residence_groupe": [{"residence_id": r, "groupe_id": "GRP-SENIORS"} for r in ("RES-003", "RES-004", "RES-005")],
        "ajustements": [
            {"id": 1, "portee_tous": True, "dossiers": [], "actif": True, "rev": 1, "cree_par": "admin@exemple.invalid",
             "contenu": {"type": "provision", "libelle": "5 % du CA", "compte": "65800000P", "mode": "regle",
                         "termes": [{"t": "pct", "taux": 5, "comptes": ["706"]}], "du": "", "au": ""}}],
        "comptes_simules": [{"numero": "65800000P", "libelle": "Provision fictive", "cree_par": "admin@exemple.invalid"}],
    }
    pg.evaluate("(t) => demarrerAvecClient(clientSimule(t), { email: 'collab@exemple.invalid', nom: 'Collab Fictif', role: 'collaborateur' })", tables)
    pg.wait_for_selector("#ecran-choix.visible")
    assert pg.evaluate("D.perimetres.find(p => p.id === 'GROUPE').libelle") == "Mon parc"
    assert pg.evaluate("D.residences.length") == 3
    assert pg.evaluate("AJ.liste.length") == 1 and pg.evaluate("AJ.liste[0].id") == "AJ-001"
    assert pg.evaluate("peutGerer(AJ.liste[0])") is False
    pg.evaluate("choisir('GROUPE'); allerA('ajustements', 'provisions')")
    assert pg.is_disabled(".aj-actif")
    # Nouvel ajustement « toutes les résidences » d'un collaborateur : enregistré sur les trois du parc.
    pg.click("#aj-nouveau")
    pg.fill("#f-libelle", "Redevance fictive")
    pg.fill("#f-compte", "65800000P")
    pg.fill(".t-taux", "2")
    pg.click("#f-ok")
    pg.wait_for_function("AJ.liste.length === 2")
    ins = pg.evaluate("journalBase.filter(q => q.op === 'insert' && q.table === 'ajustements')")
    assert len(ins) == 1
    v = ins[0]["valeurs"]
    assert v["portee_tous"] is False and sorted(v["dossiers"]) == ["DEMO-2003", "DEMO-2004", "DEMO-2005"]
    assert v["contenu"]["libelle"] == "Redevance fictive" and "portee" not in v["contenu"] and "id" not in v["contenu"]
    assert pg.evaluate("localStorage.getItem('zen-ajustements')") is None
    # Désactivation : mise à jour dans la base.
    pg.click(".aj-actif:not([disabled])")
    pg.wait_for_function("AJ.liste.some(a => !a.actif)")
    maj = pg.evaluate("journalBase.filter(q => q.op === 'update')")
    assert maj and maj[-1]["valeurs"] == {"actif": False} and maj[-1]["filtres"] == [["id", 100]]
    assert erreurs == []
    pg.close()
