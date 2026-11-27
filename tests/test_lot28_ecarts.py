"""Lots 28 à 30 - moteur d'analyse des écarts (zenitude/analyse/ecarts.py), sans navigateur.

Données : démonstration + anomalies fictives (tests/donnees_lot28.py)."""
import copy
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import donnees_lot28  # noqa: E402
from zenitude.analyse import CODES, analyser  # noqa: E402
from zenitude.analyse.ecarts import arr, mois_reference  # noqa: E402

TRIM = ["2026-07", "2026-08", "2026-09"]


@pytest.fixture(scope="module")
def D(tmp_path_factory):
    return donnees_lot28.construire(tmp_path_factory.mktemp("demo28"))


def tous(D):
    return [r["dossier"] for r in D["residences"]]


def test_references():
    assert mois_reference(["2026-01", "2026-02"], "n1") == (["2025-01", "2025-02"], 1.0)
    assert mois_reference(["2026-01", "2026-02"], "prec") == (["2025-11", "2025-12"], 1.0)
    m, f = mois_reference(["2026-10", "2026-11"], "moy12")
    assert m[0] == "2025-10" and m[-1] == "2026-09" and len(m) == 12 and f == 2 / 12
    with pytest.raises(ValueError):
        mois_reference(["2026-01"], "budget")
    assert arr(2.5) == 3 and arr(-2.5) == -3 and arr(-2.4) == -2


@pytest.mark.parametrize("ref,mois", [("prec", TRIM), ("n1", ["2026-10"]), ("moy12", ["2026-10", "2026-11"])])
def test_cascade_et_volume_prix_bouclent(D, ref, mois):
    A = analyser(D, tous(D), mois, ref)
    C = A["cascade"]
    assert A["dispo"], "aucune résidence comparable"
    assert sum(e[1] for e in C["etapes"]) == C["ebitda_v"] - C["ebitda_r"]
    assert sum(x[1] - x[2] for x in C["residences"]) == C["ebitda_v"] - C["ebitda_r"]
    for x in A["volprix"]:
        if x["volume"] is None:
            continue
        assert x["volume"] + x["prix"] == x["ca_v"] - x["ca_r"]
        assert x["ann_volume"] + x["panier"] == x["ann_v"] - x["ann_r"]
        if x["capacite"] is not None:
            assert x["capacite"] + x["occupation"] == x["volume"]
    for n in A["natures"]:
        assert n["ecart"] == n["v"] - n["r"]
        if n["variable"] and n["effet_activite"] is not None:
            assert n["effet_activite"] + n["effet_cout"] == n["ecart"]


def test_tous_les_ecarts_reperes_et_cles_uniques(D):
    A = analyser(D, tous(D), ["2026-09"], "prec")
    codes = {c["code"] for c in A["constats"]}
    assert {"N1", "V1", "F1", "F3", "F4", "A1", "A2", "A3", "A4", "R1", "B1", "K1"} <= codes
    cles = [c["cle"] for c in A["constats"]]
    assert len(cles) == len(set(cles))
    for c in A["constats"]:
        assert c["code"] in CODES and c["cle"].startswith(c["code"] + "|" + c["dossier"] + "|")
        assert c["cle"].endswith("|2026-09|2026-09|prec")
    imp = [abs(c["impact"] or 0) for c in A["constats"]]
    assert imp == sorted(imp, reverse=True)
    a2 = next(c for c in A["constats"] if c["code"] == "A2")
    assert a2["dossier"] == "DEMO-2001" and a2["valeur"] == 4800000 and a2["impact"] == -4800000
    a4 = next(c for c in A["constats"] if c["code"] == "A4")
    assert a4["reference"] == 200000 and a4["impact"] == -2200000
    f4 = next(c for c in A["constats"] if c["code"] == "F4")
    assert f4["objet"] == "FOU-MAINT|ZA4|ZA5" and f4["impact"] == -310000
    r1 = next(c for c in A["constats"] if c["code"] == "R1")
    assert r1["reference"] == 10000000 and r1["objet"] == "CA|2026-09"
    assert {c["objet"] for c in A["constats"] if c["code"] == "A3" and c["dossier"] == "DEMO-2001"} >= {"6237"}


def test_absence_n_est_jamais_zero(D):
    d = copy.deepcopy(D)
    d["calcul"]["couverts"]["DEMO-2002"] = [m for m in d["calcul"]["couverts"]["DEMO-2002"] if m != "2026-08"]
    A = analyser(d, tous(d), TRIM, "prec")
    assert ["DEMO-2002", "période"] in A["exclues"] and "DEMO-2002" not in A["dispo"]
    assert any(c["code"] == "A5" and c["dossier"] == "DEMO-2002" and c["mois"] == "2026-08" for c in A["constats"])
    assert not any(c["dossier"] == "DEMO-2002" and c["code"] in ("N1", "V1", "K1") for c in A["constats"])
    # Référence non couverte (N-1 avant le début de la comptabilité) : aucune résidence comparable
    A = analyser(D, tous(D), ["2026-04"], "n1")
    assert not A["dispo"] and all(x[1] == "référence" for x in A["exclues"])
    assert not A["natures"] and A["cascade"]["ebitda_v"] == 0
    # Nuitées manquantes (août 2026, Le Belvédère) : effets non calculables, jamais zéro
    belv = next(r["dossier"] for r in D["residences"] if r["nom"] == "Le Belvédère")
    x = next(v for v in analyser(D, [belv], TRIM, "prec")["volprix"])
    assert x["n_v"] is None and x["volume"] is None and x["prix"] is None


def test_moyenne_douze_mois(D):
    from zenitude.analyse.ecarts import Donnees
    A = analyser(D, ["DEMO-2001"], ["2026-10", "2026-11"], "moy12")
    douze = mois_reference(["2026-10"], "moy12")[0]
    P = Donnees(D).postes("DEMO-2001", douze)
    for n in A["natures"]:
        l = next(x for x in D["lignes_ebitda"] if x["code"] == n["code"])
        if l["regle"].get("prefixes") is not None:
            assert n["r"] == arr((P.get(n["code"]) or 0) * 2 / 12), n["code"]
    ca = next(x for x in A["natures"] if x["code"] == "CA")
    assert abs(ca["r"] - P["CA"] / 6) <= 20  # au plus un demi-centime d'arrondi par ligne de base


def test_seuils(D):
    A = analyser(D, tous(D), ["2026-09"], "prec", {"montant": 10 ** 12})
    assert all(c["code"] in ("A5", "A6", "A7", "F4") for c in A["constats"])  # doublons : sans seuil de montant
    B = analyser(D, tous(D), ["2026-09"], "prec", {"pct": 0.5})
    C = analyser(D, tous(D), ["2026-09"], "prec")
    assert len([c for c in B["constats"] if c["code"] == "N1"]) < len([c for c in C["constats"] if c["code"] == "N1"])


def test_comparaison_des_residences(D):
    A = analyser(D, tous(D), TRIM, "prec")
    rows = [x for x in A["benchmark"] if x["base"] == "ca" and x["code"] == "ASSUR"] or [x for x in A["benchmark"] if x["base"] == "ca"]
    for x in A["benchmark"]:
        assert 1 <= x["rang"] <= x["comparables"]
        assert x["potentiel"] >= 0 and (x["potentiel"] == 0) == (x["ratio"] <= x["mediane"] or x["potentiel"] == 0)
    assert rows
    assert analyser(D, ["DEMO-2001"], TRIM, "prec")["benchmark"] == []
