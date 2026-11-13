"""Lot 6 : moteur de KPI (six premiers indicateurs) et vue groupe. Données fictives."""
import csv
import json
import pathlib
import subprocess
import sys
from decimal import Decimal

import pytest

from zenitude import kpi
from zenitude.config.versions import Depot
from zenitude.kpi.mesures import liste_mois

RACINE = pathlib.Path(__file__).parent
FIX = RACINE / "fixtures"
ECRITURES = FIX / "ecritures_synthetiques.csv"
EXERCICES = FIX / "exercices.csv"
MESURES = FIX / "mesures_exploitation.csv"
CONFIG = FIX / "config_kpi_lot6.xlsx"
V1 = FIX / "config_complete_v1.xlsx"
SIX = {"TO-SEN", "PRIX-MOYEN", "REVPAR", "REVPAC", "DMS", "CAPTAGE-PDJ"}


def _applique(depot, classeur):
    vid = depot.deposer(classeur, "alice")
    depot.approuver(vid, "bob")
    depot.appliquer(vid, "bob")
    return vid


@pytest.fixture
def depot(tmp_path):
    d = Depot(str(tmp_path / "store"))
    _applique(d, CONFIG)
    return d


def _par_code(res):
    return {k["code"]: k for k in res["kpi"]}


# --- calcul de contrôle, indépendant du moteur ----------------------------------------
def _exploitation(dossiers, mois):
    tot = {}
    with open(MESURES, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["dossier"] in dossiers and r["mois"] in mois:
                tot[r["mesure"]] = tot.get(r["mesure"], Decimal("0")) + Decimal(r["valeur"])
    return tot


def _ca(dossiers, mois):
    heb = serv = Decimal("0")
    with open(ECRITURES, encoding="utf-8") as f:
        for e in csv.DictReader(f, delimiter=";"):
            if e["dossier"] in dossiers and e["date"][:7] in mois:
                d, k = Decimal(e["debit"] or 0), Decimal(e["credit"] or 0)
                if e["compte"] == "706":
                    heb += k - d
                elif e["compte"] == "708":
                    serv += k - d
    return heb, serv


def _attendus(dossiers, mois):
    x = _exploitation(dossiers, mois)
    heb, serv = _ca(dossiers, mois)
    return {
        "TO-SEN": x["LN_VENDUES"] / x["LN_DISPONIBLES"],
        "PRIX-MOYEN": heb / x["LN_VENDUES"],
        "REVPAR": heb / x["LN_DISPONIBLES"],
        "REVPAC": (heb + serv) / x["NUITEES_CLIENTS"],
        "DMS": x["LN_VENDUES"] / x["NB_SEJOURS"],
        "CAPTAGE-PDJ": x["COUVERTS_PDJ"] / x["NUITEES_CLIENTS"],
    }


def _copie_mesures(tmp_path, modifier):
    with open(MESURES, encoding="utf-8") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    lignes = [l for l in (modifier(dict(l)) for l in lignes) if l is not None]
    chemin = tmp_path / "mesures.csv"
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dossier", "mois", "mesure", "valeur", "source"], delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    return chemin


# --- tests ---------------------------------------------------------------------------
def test_calcul_normal_egal_au_calcul_independant(depot):
    res = kpi.calculer_dossier(depot, "PENNY-1001", ECRITURES, EXERCICES, MESURES)
    k = _par_code(res)
    assert SIX <= set(k)
    attendus = _attendus({"PENNY-1001"}, liste_mois("2026-01", "2026-12"))
    for code, v in attendus.items():
        assert k[code]["statut"] == "calculé", code
        assert Decimal(k[code]["valeur"]) == v, code


def test_exercice_decale_et_court_sans_annualisation(depot):
    res = kpi.calculer_dossier(depot, "PENNY-1002", ECRITURES, EXERCICES, MESURES)
    assert (res["periode"]["du"], res["periode"]["au"]) == ("2025-04", "2026-03")
    res3 = kpi.calculer_dossier(depot, "PENNY-1003", ECRITURES, EXERCICES, MESURES)
    assert res3["periode"]["nb_mois"] == 9
    attendus = _attendus({"PENNY-1003"}, liste_mois("2026-03", "2026-11"))
    assert Decimal(_par_code(res3)["REVPAR"]["valeur"]) == attendus["REVPAR"]


def test_denominateur_zero_non_calculable(depot, tmp_path):
    def zero(l):
        if l["dossier"] == "PENNY-1001" and l["mesure"] == "LN_DISPONIBLES":
            l["valeur"] = "0"
        return l
    res = kpi.calculer_dossier(depot, "PENNY-1001", ECRITURES, EXERCICES, _copie_mesures(tmp_path, zero))
    k = _par_code(res)
    for code in ("TO-SEN", "REVPAR"):
        assert k[code]["statut"] == "non calculable"
        assert k[code]["valeur"] is None
        assert "dénominateur nul" in k[code]["motif"]
    assert k["PRIX-MOYEN"]["statut"] == "calculé"


def test_donnee_manquante_jamais_zero(depot, tmp_path):
    def retire(l):
        if l["dossier"] == "PENNY-1001" and l["mesure"] == "LN_VENDUES" and l["mois"] == "2026-03":
            return None
        return l
    res = kpi.calculer_dossier(depot, "PENNY-1001", ECRITURES, EXERCICES, _copie_mesures(tmp_path, retire))
    k = _par_code(res)
    for code in ("TO-SEN", "PRIX-MOYEN", "DMS"):
        assert k[code]["statut"] == "non calculable"
        assert "donnée manquante : LN_VENDUES" in k[code]["motif"]
        assert "PENNY-1001" in k[code]["motif"] and "mars 2026" in k[code]["motif"]
    # Les KPI qui n'utilisent pas la mesure absente restent calculés
    assert k["REVPAR"]["statut"] == "calculé"
    assert k["CAPTAGE-PDJ"]["statut"] == "calculé"


def test_valeur_vide_est_une_absence(depot, tmp_path):
    def vide(l):
        if l["dossier"] == "PENNY-1001" and l["mesure"] == "NB_SEJOURS" and l["mois"] == "2026-06":
            l["valeur"] = ""
        return l
    res = kpi.calculer_dossier(depot, "PENNY-1001", ECRITURES, EXERCICES, _copie_mesures(tmp_path, vide))
    assert "juin 2026" in _par_code(res)["DMS"]["motif"]


def test_mois_sans_ecriture_rend_les_kpi_comptables_non_calculables(depot):
    # PENNY-1003 n'a pas d'écriture en décembre 2026 (exercice clos fin novembre)
    res = kpi.calculer_dossier(depot, "PENNY-1003", ECRITURES, EXERCICES, MESURES, "2026-11", "2026-12")
    k = _par_code(res)
    assert k["REVPAR"]["statut"] == "non calculable"
    assert "CA_HEBERGEMENT" in k["REVPAR"]["motif"] and "décembre 2026" in k["REVPAR"]["motif"]


def test_vue_groupe_ratio_de_sommes_et_non_moyenne_de_ratios(depot):
    mois = liste_mois("2026-01", "2026-03")
    res = kpi.calculer_groupe(depot, ECRITURES, MESURES, "2026-01", "2026-03",
                              dossiers=["PENNY-1001", "PENNY-1002"])
    k = _par_code(res)
    attendus = _attendus({"PENNY-1001", "PENNY-1002"}, mois)
    for code, v in attendus.items():
        assert Decimal(k[code]["valeur"]) == v, code
    # Contrôle : la moyenne des deux taux individuels est différente du ratio groupe
    t1 = _attendus({"PENNY-1001"}, mois)["TO-SEN"]
    t2 = _attendus({"PENNY-1002"}, mois)["TO-SEN"]
    assert Decimal(k["TO-SEN"]["valeur"]) != (t1 + t2) / 2


def test_vue_groupe_par_activite_seniors(depot):
    res = kpi.calculer_groupe(depot, ECRITURES, MESURES, "2026-01", "2026-03", activite="Seniors")
    assert res["dossiers"] == ["PENNY-1002"]


def test_vue_groupe_membre_incomplet_non_calculable(depot, tmp_path):
    def retire(l):
        if l["dossier"] == "PENNY-1002" and l["mesure"] == "LN_DISPONIBLES" and l["mois"] == "2026-02":
            return None
        return l
    res = kpi.calculer_groupe(depot, ECRITURES, _copie_mesures(tmp_path, retire), "2026-01", "2026-03",
                              dossiers=["PENNY-1001", "PENNY-1002"])
    to = _par_code(res)["TO-SEN"]
    assert to["statut"] == "non calculable" and "PENNY-1002" in to["motif"]


def test_vue_groupe_exige_une_periode(depot):
    with pytest.raises(kpi.RefusCalcul):
        kpi.calculer_groupe(depot, ECRITURES, MESURES, None, None, dossiers=["PENNY-1001"])


def test_compte_non_classe_bloque_les_kpi_comptables(tmp_path):
    # La v2 laisse le compte 625 sans rubrique : les mesures comptables ne sont pas fiables (P1)
    d = Depot(str(tmp_path / "store"))
    v2 = tmp_path / "v2_kpi.xlsx"
    subprocess.run([sys.executable, str(RACINE / "generer_config_kpi.py"),
                    str(FIX / "config_complete_v2.xlsx"), str(v2)], check=True, capture_output=True)
    _applique(d, v2)
    k = _par_code(kpi.calculer_dossier(d, "PENNY-1001", ECRITURES, EXERCICES, MESURES))
    assert k["PRIX-MOYEN"]["statut"] == "non calculable" and "625" in k["PRIX-MOYEN"]["motif"]
    assert k["TO-SEN"]["statut"] == "calculé"


def test_seuls_les_kpi_actifs_sont_calcules(depot):
    codes = {k["code"] for k in kpi.calculer_dossier(depot, "PENNY-1001", ECRITURES, EXERCICES, MESURES)["kpi"]}
    assert "RESULTAT-EXP" not in codes   # brouillon dans la configuration
    assert "OCC-HOT" in codes


def test_sans_version_appliquee_refus(tmp_path):
    with pytest.raises(kpi.RefusCalcul):
        kpi.calculer_dossier(Depot(str(tmp_path / "vide")), "PENNY-1001", ECRITURES, EXERCICES, MESURES)


def test_trace_version_de_configuration(depot):
    res = kpi.calculer_dossier(depot, "PENNY-1001", ECRITURES, EXERCICES, MESURES)
    assert res["version_config"] == "v1" and len(res["empreinte_config"]) == 64


def test_ligne_de_commande(depot):
    out = subprocess.run([sys.executable, "-m", "zenitude.kpi", "calcul", depot.dossier, "PENNY-1001",
                          str(ECRITURES), str(EXERCICES), str(MESURES), "--json"],
                         capture_output=True, text=True, cwd=RACINE.parent, check=True)
    assert SIX <= {k["code"] for k in json.loads(out.stdout)["kpi"]}
