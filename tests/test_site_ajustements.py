"""Lot 9 : calculateur d'ajustements de la page (décision 0002).

La page recalcule EBITDA, SIG et KPI pour des périodes libres et avec des ajustements. Ces tests
vérifient, dans un vrai navigateur, que sans ajustement elle donne exactement les chiffres du moteur
Python, et qu'un ajustement change les tableaux du montant attendu.
Ils sont ignorés si Playwright n'est pas installé (pip install playwright && playwright install chromium).
"""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402

PARITE = """
() => {
  var diffs = [], n = 0;
  D.perimetres.forEach(function (p) {
    [[D.lignes_ebitda, ["TAUX_EBITDA","EBITDA","CA_NET"], D.ebitda], [D.lignes_sig, ["TAUX_EBE","EBE","VENTES_PROD"], D.sig]].forEach(function (t) {
      var js = tableauJS(t[0], p.dossiers, D.mois, false, t[1]), py = t[2][p.id];
      function cmp(a, b, lab) {
        t[0].forEach(function (l) { n++;
          var x = a[l.code], y = b[l.code];
          var xs = x == null ? null : Math.round(x), ys = y == null ? null : Math.round(parseFloat(y) * 100);
          if (xs !== ys) diffs.push([p.id, lab, l.code, xs, ys]);
        });
      }
      D.mois.forEach(function (m) { cmp(js.mois[m], py.mois[m], m); });
      cmp(js.realise, py.realise, "realise"); cmp(js.total, py.total, "total");
    });
    var pers = D.periodes.map(function (x) { return [x.id, x.mois]; });
    if (p.type === "residence" && D.resultats[p.id + "|EXERCICE"]) {
      var r = residence(p.id), d0 = r.exercice[0].slice(0, 7), d1 = r.exercice[1].slice(0, 7);
      pers.push(["EXERCICE", MOIS.filter(function (m) { return m >= d0 && m <= d1; })]);
    }
    pers.forEach(function (q) {
      var js = resultatFen(p.dossiers, q[1], false), py = D.resultats[p.id + "|" + q[0]];
      D.kpi.forEach(function (k) { n++;
        var a = js[k.code], b = py[k.code];
        if (a.statut !== b.statut || a.affichage !== b.affichage || (a.motif || null) !== (b.motif || null)) diffs.push([p.id, q[0], k.code, a.affichage, b.affichage]);
      });
    });
  });
  return { n: n, diffs: diffs.slice(0, 10) };
}
"""

PROVISION = """
() => {
  AJ = { liste: [{ id: "AJ-001", actif: true, type: "provision", libelle: "5 % du CA", compte: "65800000P", mode: "regle", portee: "tous",
                   termes: [{ t: "pct", taux: 5, comptes: ["706", "708"] }], du: "", au: "", rev: 1 },
                 { id: "AJ-002", actif: true, type: "provision", libelle: "Donnée absente", compte: "63500001P", mode: "regle", portee: "tous",
                   termes: [{ t: "unit", montant: 1, mesure: "LN_VENDUES" }], du: "2026-08", au: "2026-08", rev: 1 }], comptes: [] };
  SOLDES = {}; RES_CACHE = {};
  var dos = perimetre("GROUPE").dossiers, V = VUES_FIN.ebitda, mois = ["2026-01", "2026-02", "2026-03"];
  var base = 0;
  dos.forEach(function (d) { mois.forEach(function (m) { var cs = COMPTA[d][m] || {};
    Object.keys(cs).forEach(function (c) { if (c.indexOf("706") === 0 || c.indexOf("708") === 0) base += cs[c]; }); }); });
  var r = tableauJS(V.lignes(), dos, mois, false, V.ratio), a = tableauJS(V.lignes(), dos, mois, true, V.ratio);
  var ao = tableauJS(V.lignes(), dos, ["2026-08"], true, V.ratio);
  return { ecart: a.total.AUTRES - r.total.AUTRES, attendu: base * 0.05, ca_identique: a.total.CA_NET === r.total.CA_NET,
           ebitda_baisse: r.total.EBITDA - a.total.EBITDA, nc_aout: ao.total.TAXES === NC };
}
"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site9")
    generer_demo.main(str(dossier / "demo"))
    sortie = dossier / "index.html"
    generer_site.main(str(sortie), str(dossier / "demo"))
    with playwright.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        pg = navigateur.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        pg.goto(sortie.as_uri())
        yield pg, erreurs
        navigateur.close()


def test_page_egale_au_moteur_sans_ajustement(page):
    pg, erreurs = page
    r = pg.evaluate(PARITE)
    assert r["n"] > 10000
    assert r["diffs"] == []
    assert erreurs == []


def test_provision_en_pourcentage_et_donnee_externe_absente(page):
    pg, _ = page
    r = pg.evaluate(PROVISION)
    # arrondi au centime par résidence et par mois : l'écart tolère quelques centimes
    assert abs(r["ecart"] - r["attendu"]) <= 30
    assert r["ca_identique"] is True
    assert abs(r["ebitda_baisse"] - r["ecart"]) < 1
    # donnée externe absente (août 2026) : non calculable, jamais zéro
    assert r["nc_aout"] is True
