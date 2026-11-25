"""Lot 19 dans un vrai navigateur (données fictives, base et fonction serveur simulées).
(Lot 21 : le dépôt du consolidé KPI est retiré ; ses tests aussi. Restent les connexions Pennylane.)

1. Dépôt du consolidé KPI (retiré au lot 21) (onglet « Données KPI ») : rattachement des résidences par le code Mews, périmètre,
   valeurs nouvelles / modifiées / identiques, valeurs écartées, ratios contrôlés, statuts des mois, rattachement
   depuis l'aperçu, groupes du fichier, historique des dépôts, détail des calculs.
2. Connexions Pennylane : clé créée dans le navigateur, jeton chiffré avant l'envoi (relu par Python avec la clé
   privée affichée), test lancé, états et alertes, réservé aux administrateurs.
Ignorés si Playwright n'est pas installé.
"""
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")
pytest.importorskip("cryptography")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
from test_lot18b_page import aller, demarrer, site  # noqa: E402,F401
from zenitude.connecteurs import jetons  # noqa: E402

TABLES = {"residences": [{"id": "RES-00" + str(i), "dossier_pennylane": f"DEMO-200{i}", "code_mews": None} for i in range(1, 9)] +
          [{"id": "RES-TEST", "dossier_pennylane": "PENNY-TEST", "code_mews": None}],
          "mesures_importees": [], "kpi_mois": [], "depots_kpi": [], "connexions_pennylane": [], "cle_jetons": []}


def tables(**autres):
    import copy
    t = copy.deepcopy(TABLES)
    t.update(autres)
    return t


def aller_import(pg, perim="PENNY-TEST"):
    aller(pg, perim)
    pg.wait_for_selector("#cx-bloc")


def test_cle_puis_jeton_chiffre_dans_le_navigateur(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    aller_import(pg)
    assert "Aucune clé de chiffrement" in pg.inner_text("#cx-bloc")
    pg.click("#cx-cle-creer")
    pg.wait_for_selector("#cx-pem")
    pem = pg.input_value("#cx-pem")
    assert pem.startswith("-----BEGIN PRIVATE KEY-----") and pg.is_disabled("#cx-cle-enregistrer")
    pg.check("#cx-cle-ok")
    pg.click("#cx-cle-enregistrer")
    pg.wait_for_selector("#cx-fenetre", state="detached")
    cle = pg.evaluate("tablesTest.cle_jetons[0]")
    cp = jetons.charger_cle_privee(pem)
    assert cle["empreinte"] == jetons.empreinte_publique(cp) == jetons.empreinte_spki_b64(cle["cle_publique"])
    assert "PRIVATE" not in str(pg.evaluate("tablesTest"))  # la clé privée n'est enregistrée nulle part
    # Jeton mal copié : refusé avant tout envoi
    pg.click("[data-cx-saisir='PENNY-TEST']")
    pg.fill("#cx-jeton", "abc def")
    pg.click("#cx-enregistrer")
    assert "ni espace" in pg.inner_text("#cx-erreur") and pg.evaluate("tablesTest.connexions_pennylane.length") == 0
    jeton = "fictif_JETON_pennylane_0123456789_abcdWXYZ"
    pg.fill("#cx-jeton", jeton)
    pg.select_option("#cx-duree", "6")
    pg.click("#cx-enregistrer")
    pg.wait_for_function("appelsFonction.length === 1")
    assert pg.evaluate("appelsFonction[0]") == {"nom": "lancer-synchro", "body": {"type": "test", "dossiers": ["PENNY-TEST"],
                                                                                    "perimetre": "Dossier Pennylane de test"}}
    c = pg.evaluate("tablesTest.connexions_pennylane[0]")
    assert c["dossier"] == "PENNY-TEST" and c["fin_jeton"] == "WXYZ" and c["duree"] == "6" and c["empreinte_cle"] == cle["empreinte"]
    assert jeton not in str(pg.evaluate("tablesTest")) and jeton not in str(pg.evaluate("journalBase"))
    assert jetons.dechiffrer(c["jeton_chiffre"], cp) == jeton  # chiffré par WebCrypto, relu par Python
    assert pg.evaluate("document.getElementById('cx-jeton')") is None  # champ fermé
    # Fin du test côté GitHub : relecture des connexions, sans recharger toute la page
    pg.evaluate("window.rechargements = 0; RECHARGER = function () { rechargements++; }; true")
    pg.evaluate("SYNC_DELAI = 50; tablesTest.synchronisations = [{ id: 42, type: 'test', statut: 'terminée', demandee_le: '2026-11-25T10:00:00Z', "
                "dossiers: ['PENNY-TEST'], resultat: { 'PENNY-TEST': { statut: 'connectée', motif: null, societe: 'SAS FICTIVE' } } }]; "
                "tablesTest.connexions_pennylane[0].etat = 'connectee'; tablesTest.connexions_pennylane[0].societe_nom = 'SAS FICTIVE'; "
                "tablesTest.connexions_pennylane[0].societe_id = '172916'; suivreSynchro();")
    pg.wait_for_function("document.getElementById('cx-bloc').innerText.indexOf('SAS FICTIVE') >= 0")
    assert "Test des jetons n° 42 terminé" in pg.inner_text("#imp-message") and "test des jetons" in pg.inner_text("#imp-historique")
    assert pg.evaluate("rechargements") == 0
    assert erreurs == []
    pg.close()


def test_etats_et_alertes(site):
    from datetime import date, timedelta
    bientot = (date.today() + timedelta(days=10)).isoformat()
    cx = [{"dossier": "DEMO-2001", "etat": "connectee", "empreinte_cle": "a" * 64, "expire_le": bientot, "societe_nom": "SOC 1", "societe_id": "1", "fin_jeton": "AAAA"},
          {"dossier": "DEMO-2002", "etat": "refusee", "empreinte_cle": "a" * 64, "motif": "jeton refusé par Pennylane", "fin_jeton": "BBBB"},
          {"dossier": "DEMO-2003", "etat": "connectee", "empreinte_cle": "b" * 64, "fin_jeton": "CCCC"}]
    pg, erreurs = demarrer(site, tables_en_plus=tables(connexions_pennylane=cx, cle_jetons=[{"id": 1, "cle_publique": "x", "empreinte": "a" * 64,
                                                                                            "creee_par": "admin@exemple.invalid", "creee_le": "2026-11-25T09:00:00Z"}]))
    aller_import(pg, "GROUPE")
    texte = pg.inner_text("#cx-bloc")
    assert "expire dans 10 j" in texte and "1 jeton(s) expirent dans les 30 jours" in texte
    assert "à ressaisir (clé remplacée)" in texte and "jeton refusé par Pennylane" in texte and "…AAAA" in texte
    assert "Tester les 3 jeton(s)" in texte
    pg.click("[data-cx-retirer='DEMO-2002']")
    pg.wait_for_function("tablesTest.connexions_pennylane.length === 2")
    assert erreurs == []
    pg.close()


def test_connexions_reservees_aux_administrateurs(site):
    pg, erreurs = demarrer(site, role="collaborateur", tables_en_plus=tables())
    aller(pg, "PENNY-TEST")
    assert pg.query_selector("#cx-bloc") is None
    pg.close()


def test_migration_011_absente(site):
    pg, erreurs = demarrer(site, tables_en_plus={"connexions_pennylane": None})
    pg.evaluate("D.connexions = null")
    aller_import(pg)
    assert "Migration 011 non appliquée" in pg.inner_text("#cx-bloc")
    assert erreurs == []
    pg.close()
