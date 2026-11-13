"""Tests du lot 2 : aperçu des impacts et rapport exportable."""
import json
import pathlib

from openpyxl import load_workbook

from zenitude.config import impact, rapport, verifier

RACINE = pathlib.Path(__file__).parent
MODELE = RACINE.parent / "config_modele" / "Zenitude_Configuration_modele.xlsx"
FIX = RACINE / "fixtures"


def _variante(tmp_path, nom, modifier):
    wb = load_workbook(MODELE)
    modifier(wb)
    chemin = tmp_path / nom
    wb.save(chemin)
    return chemin


def test_identique_aucun_changement():
    res = impact.comparer(MODELE, MODELE)
    assert res["changements"] == []
    assert res["ancienne_version_valide"] and res["nouvelle_version_valide"]


def test_ajout_scenario():
    res = impact.comparer(MODELE, FIX / "T-W5.xlsx")
    assert res["resume"]["Scenarios"]["ajout"] == 1
    assert res["nouvelle_version_valide"]


def test_modification_seuil():
    # Le modèle contient déjà OCC-HOT : on compare avec une variante qui vide l'indicateur
    res = impact.comparer(MODELE, FIX / "T-B27-a.xlsx")
    modifs = [c for c in res["changements"] if c["type"] == "modification"]
    assert any(c["onglet"] == "Seuils" and "KPI ou rubrique surveillé" in c["champs"] for c in modifs)


def test_nouvelle_version_refusee_est_signalee():
    res = impact.comparer(MODELE, FIX / "T-B12-a.xlsx")
    assert not res["nouvelle_version_valide"]
    assert any("B12" in e for e in res["erreurs_nouvelle_version"])


def test_ajout_kpi_sans_utilisation_donne_avertissement_mais_reste_valide():
    res = impact.comparer(MODELE, FIX / "T-W1.xlsx")
    assert res["resume"]["KPI"]["ajout"] == 1
    assert res["nouvelle_version_valide"]


def test_retrait_quand_la_cle_change(tmp_path):
    # Changer la date d'effet d'un KPI le fait apparaître comme retrait + ajout (règle datée)
    def f(wb):
        ws = wb["KPI"]
        ws.cell(6, 13).value = "2026-03-01"  # Date d'effet de RESULTAT-EXP
    chemin = _variante(tmp_path, "kpi_date.xlsx", f)
    res = impact.comparer(MODELE, chemin)
    assert res["resume"]["KPI"]["retrait"] == 1
    assert res["resume"]["KPI"]["ajout"] == 1


def test_archivage_detecte(tmp_path):
    def f(wb):
        wb["KPI"].cell(6, 11).value = "archivé"  # Statut de RESULTAT-EXP
    chemin = _variante(tmp_path, "archive.xlsx", f)
    res = impact.comparer(MODELE, chemin)
    assert res["resume"]["KPI"]["modification"] == 1
    assert res["resume"]["KPI"]["archivage"] == 1


def test_affichage_garde_la_casse_d_origine():
    res = impact.comparer(MODELE, FIX / "T-W5.xlsx")
    ajout = [c for c in res["changements"] if c["type"] == "ajout"][0]
    assert ajout["cle"]["Scénario"] == "Référence"


def test_rapport_json_et_markdown():
    r = verifier(FIX / "T-B13-a.xlsx")
    d = json.loads(rapport.vers_json(r))
    assert d["verdict"] == "refusé"
    assert any(e["code"] == "B13" for e in d["erreurs"])
    md = rapport.vers_markdown(r)
    assert "| B13 |" in md and "Empreinte SHA-256" in md
