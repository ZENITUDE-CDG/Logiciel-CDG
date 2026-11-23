"""Lot 15 (décision 0009), moteur et fichiers : virements internes, comptes bancaires, FRNG / BFR / TN,
tableau EBITDA du modèle de gestion du groupe, modèle d'import des KPI. Données fictives."""
import pathlib
import sys
from decimal import Decimal

import pytest
from openpyxl import load_workbook

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
from zenitude.comptes import tresorerie  # noqa: E402
from zenitude.config import couverture  # noqa: E402


def ec(d, date, journal, piece, compte, debit="", credit=""):
    return {"dossier": d, "exercice": "", "date": date, "journal": journal, "piece": piece, "compte": compte,
            "libelle": "", "debit": str(debit), "credit": str(credit), "tiers": "", "lettrage": "", "echeance": ""}


def test_virement_interne_ni_encaissement_ni_decaissement():
    lignes = [ec("D", "2026-01-01", "AN", "AN1", "512", debit=1000), ec("D", "2026-01-01", "AN", "AN1", "106", credit=1000),
              ec("D", "2026-01-05", "BQ", "VI1", "5122", debit=300), ec("D", "2026-01-05", "BQ", "VI1", "512", credit=300),
              ec("D", "2026-01-10", "BQ", "BQ1", "5122", credit=100), ec("D", "2026-01-10", "BQ", "BQ1", "401", debit=100)]
    r = tresorerie.calculer_dossier(lignes, "D", ["2026-01"])
    assert r["position"]["2026-01"] == [90000, 0, 10000]
    assert r["banques"]["512"]["2026-01"] == [70000, 0, 0, 0, 30000]
    assert r["banques"]["5122"]["2026-01"] == [20000, 0, 10000, 30000, 0]
    assert tresorerie.pieces_internes(lignes, "D") == {"VI1"}


def test_piece_non_equilibree_ou_a_un_seul_compte_n_est_pas_un_virement():
    lignes = [ec("D", "2026-01-05", "BQ", "X", "512", debit=300), ec("D", "2026-01-05", "BQ", "X", "512", credit=300),
              ec("D", "2026-01-06", "BQ", "Y", "512", debit=300), ec("D", "2026-01-06", "BQ", "Y", "5122", credit=200)]
    assert tresorerie.pieces_internes(lignes, "D") == set()


def test_bilan_synthetique():
    lignes = [ec("D", "2026-01-01", "AN", "A", "101", credit=1000), ec("D", "2026-01-01", "AN", "A", "2154", debit=600),
              ec("D", "2026-01-01", "AN", "A", "512", debit=400),
              ec("D", "2026-01-15", "VT", "V", "411", debit=240), ec("D", "2026-01-15", "VT", "V", "706", credit=200),
              ec("D", "2026-01-15", "VT", "V", "44571", credit=40),
              ec("D", "2026-01-20", "HA", "H", "606", debit=50), ec("D", "2026-01-20", "HA", "H", "401", credit=50),
              ec("D", "2026-01-31", "OD", "O", "5186", debit=0), ec("D", "2026-01-31", "BQ", "B", "519", credit=500),
              ec("D", "2026-01-31", "BQ", "B", "512", debit=500)]
    b = tresorerie.bilan(lignes, "D", ["2026-01"])["2026-01"]
    assert b["capitaux"] == 100000 and b["resultat"] == 15000 and b["ressources"] == 115000
    assert b["emplois"] == 60000 and b["frng"] == 55000
    assert b["creances"] == 24000 and b["dettes"] == 9000 and b["bfr"] == 15000
    assert b["disponibilites"] == 90000 and b["concours"] == 50000 and b["tn"] == 40000
    assert b["ecart"] == 0


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo15")
    generer_demo.main(str(d))
    return {"dossier": d, "ecritures": couverture.charger_ecritures(str(d / "ecritures.csv")),
            "donnees": generer_site.construire(str(d))}


def test_demo_deux_comptes_bancaires_et_virements(demo):
    T = demo["donnees"]["tresorerie"]
    for d, x in T["dossiers"].items():
        assert set(x["banques"]) == {"512", "5122"}, d
        for m in T["mois"]:
            assert sum(b[m][0] for b in x["banques"].values()) == x["position"][m][0]
            assert sum(b[m][1] for b in x["banques"].values()) == x["position"][m][1]
            assert sum(b[m][3] for b in x["banques"].values()) == sum(b[m][4] for b in x["banques"].values())
    assert any(T["dossiers"][d]["banques"]["5122"][T["mois"][-1]][0] < 0 for d in T["dossiers"])  # un découvert à combler


def test_frng_egal_bfr_plus_tn_partout(demo):
    T = demo["donnees"]["tresorerie"]
    for d, x in T["dossiers"].items():
        for m, b in x["bilan"].items():
            assert b["ecart"] == 0 and b["frng"] == b["bfr"] + b["tn"], (d, m)
            assert b["tn"] == x["position"][m][0], (d, m)


def test_regles_d_affectation_ebitda():
    L = generer_site.LIGNES_EBITDA
    f = generer_site._ligne_du_compte
    assert f("60320003", L) == "PROD_ENT"                       # compte exact avant le préfixe 6032
    assert f("60320099", L) == "PETITES"
    assert f("61350010", L, "LOCATION MAT.TRANSPORT") == "LOC_VEH"  # mot-clé du libellé
    assert f("61350010", L) == "LOC_AUT"                         # sans libellé : préfixe
    assert f("64110000", L, "SALAIRES MENAGE") == "MEN_SAL"
    assert f("70611000", L, "HEBERGEMENT - SENIOR") == "LG_SEN"
    assert f("70611000", L) == "CT_SEJ"
    assert f("75800000", L) == "DIVERS" and f("79100000", L) == "TRANSF"
    assert f("74000000", L) == "H_SUBV" and f("69500000", L) == "H_IS"
    codes = [l[0] for l in L]
    assert len(codes) == len(set(codes))
    for code, _, regle, sens, _ in L:
        if isinstance(regle, tuple):
            assert all(c in codes[:codes.index(code)] for c in regle[1:] if c not in "+-"), code


def test_resultat_net_du_tableau_egal_au_resultat_comptable(demo):
    D, E = demo["donnees"], demo["ecritures"]
    assert D["ebitda"]["GROUPE"]["non_classes"] == []
    for r in D["residences"]:
        d = r["dossier"]
        attendu = -sum(Decimal(e["debit"] or 0) - Decimal(e["credit"] or 0) for e in E
                       if e["dossier"] == d and e["compte"][:1] in "67" and e["date"][:4] == "2026")
        assert Decimal(D["ebitda"][d]["total"]["RN"]) == attendu, d


def test_modele_d_import(tmp_path):
    import generer_modele_import as gm
    sortie = tmp_path / "modele.xlsx"
    gm.main(str(sortie))
    wb = load_workbook(sortie)
    assert wb.sheetnames == ["Saisie", "Exemple", "Mode d'emploi", "Résidences"]
    assert [c.value for c in wb["Saisie"][1]] == gm.ENTETES
    assert wb["Saisie"]["A2"].value is None                      # onglet de saisie vide
    depot = load_workbook(RACINE / "modeles" / "Zenitude_Import_KPI_modele.xlsx")
    assert [c.value for c in depot["Saisie"][1]] == gm.ENTETES, "modèle à régénérer : python interface/generer_modele_import.py"
    catalogue = {"LN_VENDUES", "LN_DISPONIBLES", "NB_SEJOURS", "NUITEES_CLIENTS", "COUVERTS_PDJ"}
    assert {k["code"] for k in generer_site.IMPORT_KPI} <= catalogue
