"""Lot 11 : compte de résultat du PCG (système de base, ANC 2022-06) et trésorerie.

Calcul comptable : jeux d'écritures construits à la main, résultats attendus calculés à part.
Page : parité entre ce que la page affiche (agrégats sommés dans le navigateur) et le moteur Python.
Les tests de page sont ignorés si Playwright ou Chromium sont absents.
"""
import csv
import pathlib
import sys
from datetime import date
from decimal import Decimal

import pytest

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
from zenitude.comptes import pcg, tresorerie  # noqa: E402

DEBUT, FIN = date(2026, 1, 1), date(2026, 12, 31)


def ec(dossier, d, journal, compte, debit="", credit="", tiers="", lettrage="", echeance=""):
    return {"dossier": dossier, "exercice": "", "date": d, "journal": journal, "piece": "X", "compte": compte,
            "libelle": "", "debit": str(debit), "credit": str(credit), "tiers": tiers, "lettrage": lettrage,
            "echeance": echeance}


# ---------------------------------------------------------------- compte de résultat PCG

# Tableau de passage indicatif de l'article 821-2 (IR4) du règlement ANC 2022-06 : compte -> poste
PASSAGE = [
    ("707", "V_MARCH"), ("7097", "V_MARCH"), ("701", "PROD_VENDUE"), ("704", "PROD_VENDUE"), ("706", "PROD_VENDUE"),
    ("7091", "PROD_VENDUE"), ("7096", "PROD_VENDUE"), ("71", "PROD_STOCK"), ("72", "PROD_IMMO"), ("74", "SUBV"),
    ("781", "REPR_EXPL"), ("757", "CESS_PROD"), ("758", "AUT_PROD"), ("751", "AUT_PROD"),
    ("607", "A_MARCH"), ("6097", "A_MARCH"), ("6037", "VAR_MARCH"), ("601", "A_MP"), ("602", "A_MP"),
    ("6091", "A_MP"), ("6031", "VAR_MP"), ("6032", "VAR_MP"), ("604", "A_EXT"), ("605", "A_EXT"), ("606", "A_EXT"),
    ("6132", "A_EXT"), ("6122", "A_EXT"), ("619", "A_EXT"), ("625", "A_EXT"), ("629", "A_EXT"), ("635", "TAXES"),
    ("641", "SAL"), ("645", "COTIS"), ("647", "COTIS"), ("6811", "DOT_AMORT"), ("6816", "DOT_DEPR_IMMO"),
    ("6817", "DOT_DEPR_AC"), ("6815", "DOT_PROV"), ("657", "VC_CESS"), ("658", "AUT_CH"), ("655", "QP_PERTE"),
    ("755", "QP_BEN"), ("761", "PF_PART"), ("762", "PF_VM"), ("764", "PF_VM"), ("763", "PF_INT"), ("765", "PF_INT"),
    ("786", "PF_REPR"), ("766", "PF_CHG"), ("7671", "PF_CESS_IMMO"), ("7672", "PF_CESS_IMMO"),
    ("7673", "PF_CESS_VMP"), ("7674", "PF_CESS_VMP"), ("686", "CF_DOT"), ("661", "CF_INT"), ("664", "CF_INT"),
    ("665", "CF_INT"), ("666", "CF_CHG"), ("6671", "CF_VC"), ("6672", "CF_VC"), ("6673", "CF_CESS_VMP"),
    ("6674", "CF_CESS_VMP"), ("77", "PX"), ("787", "PX"), ("671", "CX"), ("687", "CX"), ("691", "PARTICIP"),
    ("695", "IS"), ("696", "IS"), ("6981", "IS"), ("6989", "IS"), ("699", "IS"),
]
# Comptes supprimés par ANC 2022-06 (transferts de charges) ou non repris au tableau de passage
NON_CLASSES = ["791", "796", "797", "643", "644", "603", "609", "681", "697", "768"]


@pytest.mark.parametrize("compte,poste", PASSAGE)
def test_tableau_de_passage_du_reglement(compte, poste):
    assert pcg.ligne_du_compte(compte) == poste


@pytest.mark.parametrize("compte", NON_CLASSES)
def test_compte_hors_tableau_de_passage_non_classe(compte):
    assert pcg.ligne_du_compte(compte) is None


def _jeu_complet():
    """Un mouvement par compte du tableau de passage, montants distincts ; produits au crédit, charges au débit
    (sauf les comptes à solde inverse : 7097, 619, 629, 6989, 699, 7091, 7096)."""
    inverse = {"7097", "619", "629", "6989", "699", "7091", "7096"}
    lignes, attendu_resultat = [], Decimal("0")
    for i, (compte, _) in enumerate(PASSAGE, start=1):
        montant = Decimal(100 + i * 7)
        produit = compte[0] == "7"
        sens_normal = (produit and compte not in inverse) or (not produit and compte in inverse)
        if sens_normal and produit or (not produit and compte in inverse):
            credit, debit = montant, ""
        elif produit:
            credit, debit = "", montant
        else:
            credit, debit = "", montant
        lignes.append(ec("D1", "2026-06-15", "OD", compte, debit=debit, credit=credit))
        attendu_resultat += (Decimal(credit or 0) - Decimal(debit or 0))
    return lignes, attendu_resultat


def test_resultat_egal_au_calcul_independant_et_totaux_coherents():
    lignes, attendu = _jeu_complet()
    r = pcg.calculer(lignes, ["D1"], DEBUT, FIN)
    assert r["statut"] == "calculé" and r["non_classes"] == []
    L = {k: Decimal(v) for k, v in r["lignes"].items()}
    assert L["RESULTAT"] == attendu
    assert L["RESULTAT"] == L["TOT_PROD"] - L["TOT_CH"]
    assert L["RESULTAT"] == L["R_COURANT"] + L["R_EXC"] - L["PARTICIP"] - L["IS"]
    assert L["R_COURANT"] == L["R_EXPL"] + L["QP_BEN"] - L["QP_PERTE"] + L["R_FIN"]
    assert L["CA_NET"] == L["V_MARCH"] + L["PROD_VENDUE"]
    # un compte à solde inverse vient en déduction de son poste (7097 sur les ventes de marchandises)
    montant_707 = next(Decimal(100 + i * 7) for i, (c, _) in enumerate(PASSAGE, 1) if c == "707")
    montant_7097 = next(Decimal(100 + i * 7) for i, (c, _) in enumerate(PASSAGE, 1) if c == "7097")
    assert L["V_MARCH"] == montant_707 - montant_7097


def test_memos_credit_bail_ne_modifient_pas_les_postes():
    base = [ec("D1", "2026-03-01", "HA", "6122", debit="400"), ec("D1", "2026-03-01", "HA", "6125", debit="250"),
            ec("D1", "2026-03-01", "HA", "613", debit="100"), ec("D1", "2026-03-01", "VT", "706", credit="2000")]
    L = {k: Decimal(v) for k, v in pcg.calculer(base, ["D1"], DEBUT, FIN)["lignes"].items()}
    assert L["M_CB_MOB"] == 400 and L["M_CB_IMMO"] == 250
    assert L["A_EXT"] == 750  # 6122 + 6125 + 613, une seule fois


def test_compte_non_classe_bloque_le_compte_de_resultat():
    r = pcg.calculer([ec("D1", "2026-03-01", "OD", "791", credit="500"), ec("D1", "2026-03-01", "VT", "706", credit="100")],
                     ["D1"], DEBUT, FIN)
    assert r["statut"] == "bloqué" and r["non_classes"] == ["791"] and "791" in r["motif"]


def test_aucune_ecriture_n_est_pas_zero():
    r = pcg.calculer([ec("D2", "2026-03-01", "VT", "706", credit="100")], ["D1"], DEBUT, FIN)
    assert r["statut"] == "non calculable" and r["lignes"] == {}


def test_exercice_borne_et_aucune_annualisation():
    lignes = [ec("D1", "2025-12-31", "VT", "706", credit="999"), ec("D1", "2026-01-31", "VT", "706", credit="100"),
              ec("D1", "2026-09-30", "VT", "706", credit="50"), ec("D1", "2026-10-01", "VT", "706", credit="999")]
    r = pcg.calculer(lignes, ["D1"], date(2026, 1, 1), date(2026, 9, 30))  # exercice de neuf mois
    assert Decimal(r["lignes"]["CA_NET"]) == 150


def test_additivite_entre_dossiers_de_meme_exercice():
    lignes = [ec("D1", "2026-03-01", "VT", "706", credit="100"), ec("D1", "2026-03-01", "HA", "641", debit="30"),
              ec("D2", "2026-03-01", "VT", "706", credit="40"), ec("D2", "2026-03-01", "HA", "661", debit="10")]
    a, b, ab = (pcg.calculer(lignes, d, DEBUT, FIN)["lignes"] for d in (["D1"], ["D2"], ["D1", "D2"]))
    assert all(Decimal(ab[k]) == Decimal(a[k]) + Decimal(b[k]) for k in ab)


def test_exercice_precedent_non_disponible():
    r = pcg.calculer([ec("D1", "2026-03-01", "VT", "706", credit="100")], ["D1"], DEBUT, FIN)
    assert r["precedent"] is None and "N-1" in r["motif_precedent"]


def test_les_comptes_de_la_demo_sont_tous_classes():
    with open(RACINE / "interface" / "demo" / "ecritures.csv", encoding="utf-8") as f:
        comptes = {r["compte"] for r in csv.DictReader(f, delimiter=";") if r["compte"][0] in "67"}
    assert comptes and [c for c in comptes if pcg.ligne_du_compte(c) is None] == []


# ---------------------------------------------------------------- trésorerie : cas construits à la main

MOIS = ["2026-01", "2026-02", "2026-03"]


def _creances():
    return [
        ec("D1", "2025-10-01", "AN", "411", debit="700", tiers="CLI9", echeance="2025-09-20"),  # à-nouveau ouvert
        ec("D1", "2026-01-10", "VT", "411", debit="1000", tiers="CLI1", lettrage="L1", echeance="2026-02-09"),
        ec("D1", "2026-02-05", "BQ", "411", credit="1000", tiers="CLI1", lettrage="L1"),       # soldée en février
        ec("D1", "2026-01-20", "VT", "411", debit="500", tiers="CLI1", lettrage="L2", echeance="2026-02-15"),
        ec("D1", "2026-03-15", "BQ", "411", credit="500", tiers="CLI1", lettrage="L2"),        # réglée après fin février
        ec("D1", "2026-01-25", "VT", "411", debit="300", tiers="CLI2", echeance="2026-02-24"),  # jamais lettrée
        ec("D1", "2026-02-01", "VT", "411", debit="200", tiers="CLI2", lettrage="L4"),          # échéance inconnue
        ec("D1", "2026-02-20", "BQ", "411", credit="100", tiers="CLI2", lettrage="L4"),        # lettrage partiel
        ec("D1", "2026-02-10", "BQ", "411", credit="50", tiers="CLI2"),                        # avoir / acompte non affecté
    ]


def test_creances_arrete_fin_fevrier_delai_30_jours():
    r = tresorerie.calculer_dossier(_creances(), "D1", MOIS)["creances"]["2026-02"]
    assert r["hist"]["2026-01"] == [180000, 100000]      # facturé 1800, soldé au 28/02 : 1000
    assert r["hist"]["2026-02"] == [20000, 0]            # lettrage partiel : pièce ouverte pour 200
    assert r["an"] == [70000, 0, 70000]
    # modes : [non échu, 1-30, 31-60, 61-90, plus de 90, inconnue]
    # L2 (20/01 + 30 = 19/02) et la pièce de 300 (25/01 + 30 = 24/02) en retard de 1 à 30 jours ; 200 non échu ;
    # l'à-nouveau (01/10 + 30 = 31/10) à plus de 90 jours
    assert r["ouvert"]["30"] == [20000, 80000, 0, 0, 70000, 0]
    assert r["credits_non_affectes"] == 5000


def test_creances_echeance_de_la_piece_et_echeance_inconnue():
    r = tresorerie.calculer_dossier(_creances(), "D1", MOIS)["creances"]["2026-02"]
    # L2 : échéance 15/02 (13 jours) ; 300 : 24/02 (4 jours) ; 200 sans échéance : inconnue, jamais « non échu »
    assert r["ouvert"]["piece"] == [0, 80000, 0, 0, 70000, 20000]


def test_creance_reglee_apres_l_arrete_devient_soldee_a_la_date_du_reglement():
    r = tresorerie.calculer_dossier(_creances(), "D1", MOIS)["creances"]["2026-03"]
    assert r["hist"]["2026-01"] == [180000, 150000]      # L2 est soldée le 15/03
    # reste ouvert : 300 (retard de 35 jours au 31/03), 200 (03/03, 28 jours), à-nouveau
    assert r["ouvert"]["30"] == [0, 20000, 30000, 0, 70000, 0]


def test_le_total_ouvert_ne_depend_pas_du_mode_d_echeance():
    r = tresorerie.calculer_dossier(_creances(), "D1", MOIS)["creances"]["2026-02"]
    assert len({sum(v) for v in r["ouvert"].values()}) == 1


def test_dettes_symetriques():
    lignes = [ec("D1", "2026-01-05", "HA", "401", credit="800", tiers="F1", lettrage="A", echeance="2026-02-04"),
              ec("D1", "2026-02-20", "BQ", "401", debit="800", tiers="F1", lettrage="A"),
              ec("D1", "2026-01-15", "HA", "401", credit="300", tiers="F2", echeance="2026-02-14")]
    r = tresorerie.calculer_dossier(lignes, "D1", MOIS)["dettes"]["2026-02"]
    assert r["hist"]["2026-01"] == [110000, 80000]
    assert r["ouvert"]["30"] == [0, 30000, 0, 0, 0, 0]  # 15/01 + 30 = 14/02, retard de 14 jours au 28/02


def test_sans_aucun_lettrage_creances_et_dettes_non_calculables():
    lignes = [ec("D1", "2026-01-10", "VT", "411", debit="100", tiers="C"), ec("D1", "2026-01-10", "HA", "401", credit="50", tiers="F")]
    r = tresorerie.calculer_dossier(lignes, "D1", MOIS)
    assert r["lettrage"] is False and r["creances"] is None and r["dettes"] is None


def test_position_de_tresorerie():
    lignes = [ec("D1", "2025-10-01", "AN", "512", debit="5000"), ec("D1", "2026-02-05", "BQ", "512", debit="1000"),
              ec("D1", "2026-03-02", "BQ", "512", credit="200"), ec("D1", "2026-03-02", "BQ", "519", credit="300")]
    pos = tresorerie.calculer_dossier(lignes, "D1", MOIS)["position"]
    assert pos["2026-01"] == [500000, 0, 0]               # à-nouveau : ni encaissement ni décaissement
    assert pos["2026-02"] == [600000, 100000, 0]
    assert pos["2026-03"] == [550000, 0, 50000]           # 512 et concours bancaire 519 inclus


def test_dossier_sans_compte_de_disponibilites():
    r = tresorerie.calculer_dossier([ec("D1", "2026-01-10", "VT", "706", credit="1")], "D1", MOIS)
    assert r["position"] is None


# ---------------------------------------------------------------- jeu de démonstration et site

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    demo = tmp_path_factory.mktemp("demo")
    generer_demo.main(str(demo))
    sortie = tmp_path_factory.mktemp("site") / "index.html"
    generer_site.main(str(sortie), str(demo))
    return {"donnees": generer_site.construire(str(demo)), "page": sortie, "demo": demo}


def test_demo_ecritures_equilibrees_avec_les_colonnes_de_tresorerie(site):
    with open(site["demo"] / "ecritures.csv", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    assert {"tiers", "lettrage", "echeance"} <= set(lignes[0])
    bal = {}
    for e in lignes:
        bal[(e["dossier"], e["piece"])] = bal.get((e["dossier"], e["piece"]), Decimal(0)) + Decimal(e["debit"] or 0) - Decimal(e["credit"] or 0)
    assert all(v == 0 for v in bal.values())  # toutes les pièces sont équilibrées


def test_resultat_pcg_egal_au_resultat_publie_pour_chaque_residence(site):
    publies = [f for f in site["donnees"]["finance"] if f["statut"] == "publié"]
    assert len(publies) == 8
    for f in publies:
        cr = f["compte_resultat"]
        assert cr["statut"] == "calculé"
        assert cr["lignes"]["RESULTAT"] == f["resultat"]["RESULTAT"]
        assert cr["rapprochement"]["ecart"] == "0.00"


def test_ouvert_de_la_demo_egal_a_un_calcul_independant(site):
    """Pièces ouvertes au 31/10/2026 recalculées directement dans le CSV, sans passer par le moteur."""
    with open(site["demo"] / "ecritures.csv", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    arrete = "2026-10-31"
    for compte, cle, sens in (("411", "creances", "debit"), ("401", "dettes", "credit")):
        for d, res in site["donnees"]["tresorerie"]["dossiers"].items():
            mine = [e for e in lignes if e["dossier"] == d and e["compte"] == compte and e["date"] <= arrete]
            groupes = {}
            for e in mine:
                if e["lettrage"]:
                    g = groupes.setdefault((e["tiers"], e["lettrage"]), [Decimal(0), ""])
                    g[0] += Decimal(e["debit"] or 0) - Decimal(e["credit"] or 0)
                    g[1] = max(g[1], e["date"])
            ouvert = Decimal(0)
            for e in mine:
                if not e[sens]:
                    continue
                g = groupes.get((e["tiers"], e["lettrage"])) if e["lettrage"] else None
                if not (g and g[0] == 0 and g[1] <= arrete):
                    ouvert += Decimal(e[sens])
            assert sum(res[cle][arrete[:7]]["ouvert"]["30"]) == int(ouvert * 100), (d, cle)


def test_dossier_sans_echeance_exportee_donne_echeance_inconnue(site):
    r = site["donnees"]["tresorerie"]["dossiers"]["DEMO-2008"]["creances"]["2026-10"]["ouvert"]
    assert r["piece"][5] > 0 and r["piece"][5] == sum(r["piece"])
    autre = site["donnees"]["tresorerie"]["dossiers"]["DEMO-2001"]["creances"]["2026-10"]["ouvert"]["piece"]
    assert autre[5] == 0


@pytest.fixture(scope="module")
def navigateur(site):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium indisponible : {e}")
        pg = nav.new_page(viewport={"width": 1500, "height": 1000})
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        pg.goto(site["page"].as_uri())
        yield pg, erreurs
        nav.close()


def _aller(pg, perim, section, page, lo=None, hi=None, delai=None):
    pg.evaluate("""([perim, section, page, lo, hi, delai]) => {
      etat.utilisateur = {mail: 'x'}; etat.perim = perim; etat.section = section; etat.page = page;
      if (lo !== null) { etat.lo = lo; etat.hi = hi; }
      if (delai) etat.delai = delai;
      montrer('ecran-app'); rendre(); }""", [perim, section, page, lo, hi, delai])


def _entier(texte):
    chiffres = "".join(c for c in texte if c.isdigit() or c == "-" or c == "−").replace("−", "-")
    return int(chiffres)


@pytest.mark.parametrize("cle,page", [("creances", "tr_creances"), ("dettes", "tr_dettes")])
@pytest.mark.parametrize("delai", ["30", "piece"])
def test_page_tiers_egale_au_moteur_sur_le_groupe(site, navigateur, cle, page, delai):
    pg, erreurs = navigateur
    n = len(site["donnees"]["calcul"]["mois"])
    _aller(pg, "GROUPE", "tresorerie", page, 0, n, delai)
    cartes = pg.locator(".ruban .indic .val").all_inner_texts()
    treso = site["donnees"]["tresorerie"]["dossiers"]
    A = site["donnees"]["meta"]["dernier_mois_importe"]
    ouv = sum(sum(t[cle][A]["ouvert"][delai]) for t in treso.values())
    fact = sum(v[0] for t in treso.values() for m, v in t[cle][A]["hist"].items())
    enc = sum(v[1] for t in treso.values() for m, v in t[cle][A]["hist"].items())
    assert _entier(cartes[0]) == round(fact / 100)
    assert _entier(cartes[1]) == round(enc / 100)
    assert _entier(cartes[3]) == round(ouv / 100)
    assert cartes[2].replace("\u202f", " ").replace("\xa0", " ") == f"{enc / fact * 100:.1f}".replace(".", ",") + " %"
    assert erreurs == []


def test_page_position_egale_au_moteur_sur_le_groupe(site, navigateur):
    pg, erreurs = navigateur
    n = len(site["donnees"]["calcul"]["mois"])
    _aller(pg, "GROUPE", "tresorerie", "tr_position", 0, n)
    cartes = pg.locator(".ruban .indic .val").all_inner_texts()
    treso = site["donnees"]["tresorerie"]["dossiers"]
    A = site["donnees"]["meta"]["dernier_mois_importe"]
    assert _entier(cartes[0]) == round(sum(t["position"][A][0] for t in treso.values()) / 100)
    assert _entier(cartes[1]) == round(sum(v[1] for t in treso.values() for v in t["position"].values()) / 100)
    assert _entier(cartes[2]) == round(sum(v[2] for t in treso.values() for v in t["position"].values()) / 100)
    assert erreurs == []


def test_le_lettrage_absent_rend_la_page_non_calculable(site, navigateur):
    pg, _ = navigateur
    _aller(pg, "DEMO-2006", "tresorerie", "tr_creances", 0, 13)
    pg.evaluate("() => { D.tresorerie.dossiers['DEMO-2006'].creances = null; majContenu(); }")
    texte = pg.locator("#contenu").inner_text()
    assert "Non calculable" in texte and "Lettrage absent" in texte
    assert pg.locator(".ruban").count() == 0  # aucun chiffre affiché à la place


def test_page_cumul_du_compte_de_resultat_egale_la_somme_des_publications(site, navigateur):
    pg, erreurs = navigateur
    _aller(pg, "GROUPE", "tableaux", "resultat")
    pg.evaluate("() => { etat.crTous = true; majContenu(); }")
    d = site["donnees"]
    cle = pg.evaluate("() => etat.crSel")
    assert cle.startswith("cumul|")
    debut, fin = cle[len("cumul|"):].split("/")
    attendu = sum(Decimal(f["compte_resultat"]["lignes"]["RESULTAT"]) for f in d["finance"]
                  if f["statut"] == "publié" and f["exercice"]["debut"] == debut and f["exercice"]["fin"] == fin)
    texte = pg.locator(".fin.cr tr.n0").last.locator("td").nth(1).inner_text()
    assert _entier(texte) == round(attendu)
    assert "Rapprochement" in pg.locator("#contenu").inner_text()
    assert erreurs == []


def test_exercices_decales_jamais_additionnes(site, navigateur):
    pg, _ = navigateur
    _aller(pg, "GROUPE", "tableaux", "resultat")
    options = pg.evaluate("() => optionsCR(perimetre('GROUPE')).filter(o => o.cumul).map(o => o.fs.map(f => cleExercice(f)))")
    assert len(options) == 2
    assert all(len(set(o)) == 1 for o in options)  # chaque cumul ne mélange qu'un seul exercice
