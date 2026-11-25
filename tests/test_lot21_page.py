"""Lot 21 dans un vrai navigateur (données fictives, base simulée) : allègement des pages d'import.

- arrivée sur Import comptable après la connexion, pour un groupe comme pour une résidence ;
- historiques (synchronisations, dépôts, journal du catalogue) : 5 dernières lignes, puis « Voir plus » ;
- Données externes : seul le modèle du catalogue se dépose (consolidé et ancien modèle refusés, anciens blocs retirés) ;
- Paramètres KPI : modèle Mixte, ancienne configuration du moteur et colonne du consolidé retirées.
Ignorés si Playwright n'est pas installé.
"""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
from test_lot18b_page import demarrer, site  # noqa: E402,F401
from test_lot20_page import tables  # noqa: E402


def synchros(n):
    return [{"id": i, "type": "synchro", "statut": "terminée", "demandee_le": f"2026-11-{10 + i:02d}T10:00:00Z", "demandee_par": "admin@exemple.invalid",
             "perimetre": "Dossier Pennylane de test", "dossiers": ["PENNY-TEST"], "mois_debut": "2026-01", "mois_fin": "2026-10",
             "masquer_brouillard": True, "resultat": {"PENNY-TEST": {"statut": "synchronisée", "lignes_reprises": 100 + i}}} for i in range(1, n + 1)]


@pytest.mark.parametrize("perim", ["GROUPE", "DEMO-2003"])
def test_arrivee_sur_import_comptable(site, perim):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    pg.click(f"#ecran-choix [data-p='{perim}']")
    pg.wait_for_selector("#imp-synchro")
    assert pg.evaluate("etat.section + '/' + etat.page") == "import/pennylane"
    assert "Import comptable" in pg.inner_text("#contenu h1")
    assert erreurs == []
    pg.close()


def test_historique_des_synchronisations_cinq_puis_tout(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables(synchronisations=synchros(8)))
    pg.evaluate("choisir('PENNY-TEST'); allerA('import', 'pennylane')")
    pg.wait_for_selector("#imp-historique")
    lignes = lambda: pg.evaluate("document.querySelectorAll('#imp-historique tbody tr').length")  # noqa: E731
    assert lignes() == 5 and "108 lignes" in pg.inner_text("#imp-historique") and "103 lignes" not in pg.inner_text("#imp-historique")
    pg.click("#imp-historique [data-voir-plus]")
    pg.wait_for_function("document.querySelectorAll('#imp-historique tbody tr').length === 8")
    assert "Réduire" in pg.inner_text("#imp-historique")
    pg.click("#imp-historique [data-voir-plus]")
    pg.wait_for_function("document.querySelectorAll('#imp-historique tbody tr').length === 5")
    assert erreurs == []
    pg.close()


def test_donnees_externes_seul_le_modele_du_catalogue(site):
    depots = [{"id": i, "fichier": f"Modele_{i}.xlsx", "perimetre": "Groupe", "residences": 2, "mois": 2, "nouvelles": i, "modifiees": 0,
               "ecartees": 0, "depose_par": "admin@exemple.invalid", "depose_le": f"2026-11-{10 + i:02d}T10:00:00Z"} for i in range(1, 8)]
    pg, erreurs = demarrer(site, tables_en_plus=tables(depots_kpi=depots))
    pg.evaluate("choisir('GROUPE'); allerA('import', 'externes')")
    pg.wait_for_selector("#mod-bloc")
    texte = pg.inner_text("#contenu")
    for absent in ("consolidé", "Modèle CSV", "Mesures d’exploitation disponibles", "Suivi des mois importés"):
        assert absent not in texte, absent
    assert pg.query_selector("#mod-export") and pg.query_selector("#imp-fichier") and pg.query_selector("#imp-csv") is None
    # Historique des dépôts : 5 puis tout
    assert pg.evaluate("document.querySelectorAll('#ext-depots tbody tr').length") == 5
    pg.click("#ext-depots [data-voir-plus]")
    pg.wait_for_function("document.querySelectorAll('#ext-depots tbody tr').length === 7")
    # Un consolidé KPI déposé est refusé : seul le modèle du catalogue est accepté (lecteur Excel simulé)
    pg.evaluate("""window.XLSX = { read: function () { return { SheetNames: ['Données KPI'], Sheets: { 'Données KPI': [['Résidence (nom Mews)', 'Mois'], ['RES-001 - X', '2026-10-01']] } }; },
      utils: { sheet_to_json: function (s) { return s; } } }; true""")
    pg.set_input_files("#imp-fichier", files=[{"name": "Consolide_KPI_2026.xlsx", "mimeType": "application/octet-stream", "buffer": b"fictif"}])
    pg.wait_for_selector("#cons-resultat")
    assert "Dépôt refusé" in pg.inner_text("#cons-resultat") and "fichier non reconnu" in pg.inner_text("#cons-resultat")
    assert pg.query_selector("#cons-ok") is None
    pg.click("#imp-annuler")
    pg.wait_for_selector("#cons-resultat", state="detached")
    assert erreurs == []
    pg.close()


def test_parametres_kpi_mixte_journal_et_nettoyage(site):
    journal = [{"id": i, "code": "TO_HOT", "action": "modification", "avant": {"seuil": None}, "apres": {"seuil": 0.5 + i / 100},
                "par": "admin@exemple.invalid", "le": f"2026-11-{10 + i:02d}T10:00:00Z"} for i in range(9, 0, -1)]
    pg, erreurs = demarrer(site, tables_en_plus=tables(kpi_journal=journal))
    pg.evaluate("choisir('GROUPE'); allerA('import', 'parametres')")
    pg.wait_for_selector("#cat-modeles")
    texte = pg.inner_text("#contenu")
    assert "Mixte (plusieurs activités)" in pg.inner_text("#cat-modeles")
    assert "Configuration du moteur de calcul" not in texte and "Colonne du consolidé" not in texte
    assert pg.evaluate("document.querySelectorAll('#cat-journal tbody tr').length") == 5
    pg.click("#cat-journal [data-voir-plus]")
    pg.wait_for_function("document.querySelectorAll('#cat-journal tbody tr').length === 9")
    # La résidence mixte de démonstration reçoit le modèle Mixte proposé
    assert pg.evaluate("modelePropose('DEMO-2008')") == "MIXTE"
    pg.click("[data-cat-modif='TO_SEN']")
    assert pg.evaluate("document.querySelector(\"input[name='cat-modele'][value='MIXTE']\").checked") is True
    assert pg.query_selector("#cat-colonne") is None
    assert erreurs == []
    pg.close()
