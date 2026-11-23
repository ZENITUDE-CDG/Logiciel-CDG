"""Lot 14, dans un vrai navigateur (données fictives) :
1. Détail des calculs : chaque montant cliquable ouvre un détail dont la valeur est celle affichée ; les écritures
   redonnent les montants du moteur (comptes, compte de résultat publié, trésorerie, créances et dettes).
2. Lissage de postes : écriture répartie sur l'exercice suivant, total conservé, lissage d'une écriture modifiée
   signalé et non appliqué ; enregistrement dans la base en ligne (base simulée).
3. Compte ouvert par l'adresse e-mail en bas à gauche ; logo des autres pages vers le choix des résidences.
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
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
import publier_supabase as pub  # noqa: E402
from test_lot13_page import CLIENT_SIMULE  # noqa: E402
from zenitude.config import couverture  # noqa: E402
from zenitude.kpi.mesures import charger_exploitation  # noqa: E402


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site14")
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
        yield {"nav": nav, "complet": complet, "vide": vide, "commun": json.loads(json.dumps(commune["contenu"])), "lignes": lignes}
        nav.close()


def ouvrir(site, page, connecte=True):
    pg = site["nav"].new_page(viewport={"width": 1500, "height": 1000})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(page.as_uri())
    if connecte and page == site["complet"]:
        pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
        pg.reload()
        pg.wait_for_selector("#ecran-choix.visible")
    return pg, erreurs


VERIFIER = """
(perim) => {
  choisir(perim);
  var out = { n: 0, ecarts: [], controles: [], indispo: [] };
  Object.keys(SOUS).forEach(function (s) { SOUS[s].forEach(function (x) {
    allerA(s, x[0]);
    document.querySelectorAll('#contenu [data-x]').forEach(function (e) {
      var spec = JSON.parse(e.getAttribute('data-x')); ouvrirExplication(spec, true); var R = DERNIERE_EXPLICATION; out.n++;
      if (R.titre === 'Détail indisponible') out.indispo.push([x[0], spec, R.notes]);
      if (R.controle && !R.controle.ok) out.controles.push([x[0], spec, R.controle.texte]);
      if (/^(TD|SPAN|STRONG)$/.test(e.tagName)) { var t = e.innerText.trim(); if (t !== R.valeur && !(t === 'n.c.' && R.valeur === 'non calculable')) out.ecarts.push([x[0], spec, t, R.valeur]); }
    });
  }); });
  return out;
}
"""


@pytest.mark.parametrize("perim", ["GROUPE", "DEMO-2002", "DEMO-2006"])
def test_tout_montant_cliquable_redonne_sa_valeur(site, perim):
    pg, erreurs = ouvrir(site, site["complet"])
    r = pg.evaluate(VERIFIER, perim)
    assert r["n"] > 150
    assert r["indispo"] == [] and r["controles"] == [] and r["ecarts"] == []
    assert erreurs == []
    pg.close()


def test_ecritures_redonnent_les_soldes_du_moteur(site):
    pg, _ = ouvrir(site, site["complet"])
    r = pg.evaluate("""() => { var ecarts = 0, n = 0;
      Object.keys(COMPTA).forEach(function (d) { Object.keys(COMPTA[d]).forEach(function (m) { Object.keys(COMPTA[d][m]).forEach(function (c) { n++;
        var s = ((ECR[d] || {})[m] || {})[c] || []; if (s.reduce(function (t, r) { return t + r[6]; }, 0) !== COMPTA[d][m][c]) ecarts++; }); }); });
      return { n: n, ecarts: ecarts }; }""")
    assert r["n"] > 1000 and r["ecarts"] == 0
    pg.close()


def test_compte_de_resultat_publie_rapproche_poste_par_poste(site):
    pg, _ = ouvrir(site, site["complet"])
    r = pg.evaluate("""() => { var ko = [], n = 0;
      D.finance.filter(function (f) { return f.statut === 'publié'; }).forEach(function (f) {
        D.cr_lignes.filter(function (l) { return l.sens === 'produit' || l.sens === 'charge'; }).forEach(function (l) {
          var R = EXPLIQUER.cr({ t: 'cr', d: [f.dossier], c: l.code }); n++; if (R.controle && !R.controle.ok) ko.push([f.dossier, l.code]); });
        ['CA_HEBERGEMENT', 'CA_SERVICES', 'PL_CHARGES'].forEach(function (k) { var R = EXPLIQUER.pub({ t: 'pub', d: f.dossier, k: k }); n++; if (!R.controle.ok) ko.push([f.dossier, k]); });
      }); return { n: n, ko: ko }; }""")
    assert r["n"] > 100 and r["ko"] == []
    pg.close()


def test_tresorerie_creances_dettes_rapprochees(site):
    pg, _ = ouvrir(site, site["complet"])
    r = pg.evaluate("""() => { var ko = [], n = 0, A = D.meta.dernier_mois_importe, ms = TR.mois.filter(function (m) { return m <= A; });
      D.residences.forEach(function (x) { var d = [x.dossier];
        ['solde', 'enc', 'dec'].forEach(function (k) { var R = EXPLIQUER.tr({ t: 'tr', k: k, d: d, m: ms, A: A }); n++; if (!R.controle.ok) ko.push([x.dossier, k]); });
        ['creances', 'dettes'].forEach(function (cle) { if (!TR.dossiers[x.dossier][cle]) return;
          ['30', '60', 'piece'].forEach(function (mode) { ['fact', 'enc', 'ouv', 'echu', 'nonechu', 't0', 't1', 't2', 't3', 't4', 't5', 'an'].forEach(function (k) {
            var R = EXPLIQUER.tt({ t: 'tt', cle: cle, k: k, d: d, m: ms, A: A, mode: mode }); n++; if (R.controle && !R.controle.ok) ko.push([x.dossier, cle, mode, k, R.controle.texte]); }); }); });
      }); return { n: n, ko: ko }; }""")
    assert r["n"] > 300 and r["ko"] == []
    pg.close()


def test_detail_d_une_ligne_ebitda_jusqu_aux_ecritures(site):
    pg, _ = ouvrir(site, site["complet"])
    pg.evaluate("choisir('DEMO-2001'); allerA('tableaux', 'synthese')")
    pg.click("xpath=//table[contains(@class,'fin')]//tr[td[1][normalize-space()='EBITDA']]/td[@data-x][1]")
    pg.wait_for_selector("#panneau.ouvert")
    assert "EBITDA" in pg.inner_text("#pan-titre")
    pg.click(".pan-parts tr.cliquable")          # première ligne du calcul (EBITDAR), puis marge, CA... jusqu'à un compte
    while not pg.query_selector(".pan-ecr"):
        pg.click(".pan-parts tr.cliquable")
    assert pg.inner_text("#pan-titre").startswith("Compte ")
    assert pg.query_selector_all(".pan-ecr tbody tr")
    pg.click("#pan-retour")
    pg.keyboard.press("Escape")
    assert not pg.query_selector("#panneau.ouvert")
    pg.close()


LISSER = """
() => {
  var d = "DEMO-2001", r = D.ecritures[d].find(function (x) { return x[4] === "635" && x[1].slice(0, 7) === "2026-09"; });
  LIS = { liste: [nouveauLissage(d, r, "2025-10", "2027-09")] }; ajVider();
  var reel = soldes(d, false).v, aj = soldes(d, true).v, tot = function (S) { return MOIS.reduce(function (s, m) { return s + (S[m]["635"] || 0); }, 0); };
  var parts = MOIS.filter(function (m) { return m >= "2025-10" && m <= "2027-09"; }).map(function (m) { return (aj[m]["635"] || 0) - (reel[m]["635"] || 0) + (m === "2026-09" ? r[6] : 0); });
  var E1 = EXPLIQUER.cpt({ t: "cpt", c: "635", d: [d], m: MOIS.filter(function (m) { return m >= "2026-10" && m <= "2027-09"; }), a: true });
  // Écriture modifiée à la publication suivante : lissage signalé, non appliqué
  LIS.liste[0].montant += 1; ajVider();
  var modifie = { etat: lisEtat(LIS.liste[0]), actifs: lisActifs(d).length, total: tot(soldes(d, true).v) === tot(reel) };
  return { conserve: tot(aj) === tot(reel), n: parts.length, somme: parts.reduce(function (s, x) { return s + x; }, 0), montant: r[6],
           ecart: Math.max.apply(null, parts) - Math.min.apply(null, parts), e1: E1.parts.map(function (p) { return p.lib; }), modifie: modifie };
}
"""


def test_lissage_sur_l_exercice_suivant(site):
    pg, erreurs = ouvrir(site, site["complet"])
    r = pg.evaluate(LISSER)
    assert r["conserve"] is True
    assert r["n"] == 24 and r["somme"] == r["montant"] and r["ecart"] <= 1
    assert any(p.startswith("Lissage de l’écriture") for p in r["e1"])
    assert r["modifie"]["etat"]["ok"] is False and "modifiée" in r["modifie"]["etat"]["motif"]
    assert r["modifie"]["actifs"] == 0 and r["modifie"]["total"] is True
    assert erreurs == []
    pg.close()


def test_lissage_par_l_ecran(site):
    pg, erreurs = ouvrir(site, site["complet"])
    pg.evaluate("choisir('DEMO-2001'); allerA('ajustements', 'lissage')")
    pg.click("[data-lis-ouvrir='635']")
    pg.click("[data-lis-ecr]")
    pg.select_option("#lis-au", "2027-09")
    pg.click("#lis-ok")
    assert pg.evaluate("LIS.liste.length") == 1 and pg.evaluate("LIS.liste[0].au") == "2027-09"
    assert json.loads(pg.evaluate("localStorage.getItem('zen-lissages')"))["liste"][0]["du"] == "2025-10"
    assert "1 écriture(s) lissée(s) active(s)" in pg.inner_text("#contenu")
    pg.click("#lis-tout")
    assert pg.evaluate("LIS.liste.length") == 12
    pg.click("#lis-fermer")
    pg.click("[data-lis-actif='635']")           # désactive tous les lissages du compte
    assert pg.evaluate("lisActifs('DEMO-2001').length") == 0
    assert erreurs == []
    pg.close()


def test_lissage_enregistre_dans_la_base(site):
    pg, erreurs = ouvrir(site, site["vide"], connecte=False)
    pg.evaluate(CLIENT_SIMULE)
    tables = {"donnees_communes": [{"id": "SITE", "contenu": site["commun"]}], "donnees_residences": site["lignes"][:2],
              "groupes": [], "residence_groupe": [], "ajustements": [], "comptes_simules": [], "lissages": []}
    pg.evaluate("(t) => demarrerAvecClient(clientSimule(t), { email: 'collab@exemple.invalid', nom: 'Collab', role: 'collaborateur' })", tables)
    pg.wait_for_selector("#ecran-choix.visible")
    pg.evaluate("choisir('DEMO-2001'); allerA('ajustements', 'lissage')")
    pg.click("[data-lis-ouvrir='635']")
    pg.click("[data-lis-ecr]")
    pg.click("#lis-ok")
    pg.wait_for_function("LIS.liste.length === 1")
    ins = pg.evaluate("journalBase.filter(q => q.op === 'insert' && q.table === 'lissages')")
    v = ins[0]["valeurs"]
    assert v["dossier"] == "DEMO-2001" and v["compte"] == "635" and v["du"] == "2025-10" and v["au"] == "2026-09"
    assert isinstance(v["montant"], int) and len(v["date_ecriture"]) == 10
    assert pg.evaluate("localStorage.getItem('zen-lissages')") is None
    assert erreurs == []
    pg.close()


def test_compte_et_logo(site):
    pg, _ = ouvrir(site, site["complet"])
    pg.evaluate("choisir('GROUPE')")
    assert pg.get_attribute("#lien-compte", "href") == "espace.html"
    assert pg.is_visible("#lien-compte .u-mail")
    pg.evaluate("allerA('residence', 'residence')")
    pg.click("#btn-zenitude")
    assert pg.is_visible("#ecran-choix")
    pg.close()
    pg = site["nav"].new_page()
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); sessionStorage.setItem('zen-perim', JSON.stringify('GROUPE'))")
    pg.goto(site["complet"].as_uri() + "#choix")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.close()


def test_logo_et_compte_des_autres_pages():
    js = (RACINE / "app" / "zenitude.js").read_text(encoding="utf-8")
    assert 'href: "index.html#choix"' in js and 'texte: "Mon compte"' in js
    assert "Mon espace" not in (RACINE / "app" / "garde.js").read_text(encoding="utf-8").split("Lot 14")[0]
