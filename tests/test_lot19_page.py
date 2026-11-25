"""Lot 19 dans un vrai navigateur (données fictives, base et fonction serveur simulées).

1. Dépôt du consolidé KPI (onglet « Données KPI ») : rattachement des résidences par le code Mews, périmètre,
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

ENTETES = ["Résidence (nom Mews)", "Nom court", "Segment", "Région", "RM", "Regroupement", "Année", "Mois n°", "Mois", "Source",
           "Statut", "Détail", "Comparable N-1", "Comparable N-2", "Comparable réf.", "Jours", "Lots hôtelier", "Lots seniors",
           "Lots seniors occupés", "CA total résidence HT", "CA total hôtelier HT", "CA hébergement hôtelier HT",
           "CA hébergement seniors HT", "Nb PDJ", "CA HT PDJ", "CA HT RESTO", "CA HT SPA", "CA SAP", "CA Restauration seniors",
           "Clients présents", "Nb de réservations", "Capacité hôtelière (lots × jours)", "Chambres vendues hôtelières",
           "Nuitées seniors", "Capacité seniors", "Nuitées totales", "Capacité totale", "TO hôtelier", "PM", "RevPar", "RevPac",
           "DMS", "Captage PDJ", "TO seniors", "TO résidence"]


def ligne(nom, mois, segment="RT", region="Sud Est", rm="RM Fictif", statut="Complet", detail=None, **val):
    """Ligne fictive cohérente : quantités de base et ratios du fichier calculés comme l'outil KPI."""
    v = {"Jours": 31, "Lots hôtelier": 50, "CA total résidence HT": 60000.0, "CA total hôtelier HT": 60000.0,
         "CA hébergement hôtelier HT": 50000.0, "Nb PDJ": 300, "CA HT PDJ": 3000.0, "CA HT RESTO": 0, "Clients présents": 1500,
         "Nb de réservations": 400, "Capacité hôtelière (lots × jours)": 1550, "Chambres vendues hôtelières": 1000,
         "Nuitées seniors": 0, "Capacité seniors": 0, "Nuitées totales": 1000, "Capacité totale": 1550}
    v.update({k.replace("_", " "): x for k, x in val.items()})
    r = lambda a, b: (v[a] / v[b]) if v.get(b) else None  # noqa: E731
    v.update({"TO hôtelier": r("Chambres vendues hôtelières", "Capacité hôtelière (lots × jours)"),
              "PM": r("CA hébergement hôtelier HT", "Chambres vendues hôtelières"),
              "RevPar": r("CA hébergement hôtelier HT", "Capacité hôtelière (lots × jours)"),
              "RevPac": r("CA total hôtelier HT", "Clients présents"), "DMS": r("Chambres vendues hôtelières", "Nb de réservations"),
              "Captage PDJ": r("Nb PDJ", "Clients présents"), "TO résidence": r("Nuitées totales", "Capacité totale")})
    v.update({"Résidence (nom Mews)": nom, "Segment": segment, "Région": region, "RM": rm, "Année": int(mois[:4]),
              "Mois n°": int(mois[5:]), "Mois": mois + "-01", "Source": "Import Mews", "Statut": statut, "Détail": detail})
    return [v.get(h) for h in ENTETES]


def fichier():
    L = [ENTETES,
         ligne("RES-001 - Les Terrasses du Port (fictif)", "2026-09"),
         ligne("RES-001 - Les Terrasses du Port (fictif)", "2026-10", statut="Estimé", detail="clients repris de septembre 2026"),
         ligne("RES-002 - Le Belvédère (fictif)", "2026-10", region="Nord", rm="RM Deux"),
         ligne("ABCZS- Résidence fictive", "2026-10", region="Nord", rm="RM Deux"),
         ligne("ZZZ - Hors du logiciel (fictif)", "2026-10"),
         [None] * len(ENTETES)]
    # Valeurs particulières : avoir (CA négatif importé), quantité négative (écartée), ratio du fichier faux (signalé)
    i = ENTETES.index
    L[1][i("CA HT RESTO")] = -125.5
    L[3][i("Clients présents")] = -4
    L[2][i("TO hôtelier")] = 0.99
    return L


def deposer(pg, perim, L=None):
    pg.evaluate(f"choisir('{perim}'); allerA('import', 'externes')")
    pg.wait_for_selector("#imp-csv")
    pg.evaluate("(L) => { etat.import = { nom: 'Consolide_KPI_2026.xlsx', feuille: 'Données KPI', lignes: L, R: validerConsolide(L, perimetre(etat.perim)) }; majContenu(); }",
                L or fichier())
    pg.wait_for_selector("#cons-resultat")


TABLES = {"residences": [{"id": "RES-00" + str(i), "dossier_pennylane": f"DEMO-200{i}", "code_mews": None} for i in range(1, 9)] +
          [{"id": "RES-TEST", "dossier_pennylane": "PENNY-TEST", "code_mews": None}],
          "mesures_importees": [{"dossier": "DEMO-2001", "mois": "2026-09", "mesure": "NUITEES_CLIENTS", "valeur": 1499}],
          "kpi_mois": [], "depots_kpi": [], "connexions_pennylane": [], "cle_jetons": []}


def tables(**autres):
    import copy
    t = copy.deepcopy(TABLES)
    t.update(autres)
    return t


def test_apercu_du_consolide_sur_le_groupe(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    deposer(pg, "GROUPE")
    R = pg.evaluate("etat.import.R")
    assert R["erreurs"] == []
    assert sorted(R["parRes"]) == ["DEMO-2001", "DEMO-2002"]
    assert [x["code"] for x in R["nonRattachees"]] == ["ABCZS", "ZZZ"]
    # RES-001 : 2 mois ; une valeur déjà importée et modifiée (1499 -> 1500 clients), le reste nouveau
    assert R["parRes"]["DEMO-2001"]["modifiees"] == 1 and R["modifiees"] == 1
    vals = {(v["dossier"], v["mois"], v["mesure"]): v["valeur"] for v in R["valeurs"]}
    assert vals[("DEMO-2001", "2026-09", "CA_MEWS_RESTO")] == -125.5          # avoir importé
    assert ("DEMO-2002", "2026-10", "NUITEES_CLIENTS") not in vals            # quantité négative écartée
    assert vals[("DEMO-2001", "2026-10", "LN_VENDUES")] == 1000 and vals[("DEMO-2001", "2026-10", "LN_DISPONIBLES")] == 1550
    assert [(x["colonne"], x["motif"]) for x in R["ecartees"]] == [("Clients présents", "quantité négative")]
    # Ratios : seul le TO hôtelier faux est signalé ; les ratios dépendant des clients écartés ne sont pas comparés
    assert [(x["d"], x["colonne"]) for x in R["controles"]] == [("DEMO-2001", "TO hôtelier")]
    assert not any(k[2] in ("TO_HOTELIER", "REVPAR") for k in vals)           # aucun ratio importé
    assert {(s["dossier"], s["mois"], s["statut"]) for s in R["statuts"]} == {
        ("DEMO-2001", "2026-09", "Complet"), ("DEMO-2001", "2026-10", "Estimé"), ("DEMO-2002", "2026-10", "Complet")}
    assert {g["libelle"]: g["dossiers"] for g in R["groupes"]} == {
        "Segment RT": ["DEMO-2001", "DEMO-2002"], "Région Sud Est": ["DEMO-2001"], "Région Nord": ["DEMO-2002"],
        "RM RM Fictif": ["DEMO-2001"], "RM RM Deux": ["DEMO-2002"]}
    texte = pg.inner_text("#cons-resultat")
    assert "non rattachées (2)" in texte and "Valeurs écartées (1)" in texte and "Ratios à vérifier (1)" in texte
    assert "Groupes du fichier" in texte and "à créer" in texte
    assert erreurs == []
    pg.close()


def test_import_puis_redepot_sans_changement(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    deposer(pg, "GROUPE")
    n = pg.evaluate("etat.import.R.valeurs.length")
    pg.click("#cons-ok")
    pg.wait_for_function("!document.getElementById('cons-resultat')")
    assert "Consolidé importé" in pg.inner_text("#ext-message")
    T = pg.evaluate("tablesTest")
    assert len(T["mesures_importees"]) == n + 0  # la valeur modifiée remplace l'ancienne (même clé)
    assert {(x["dossier"], x["mois"], x["statut"], x["fichier"]) for x in T["kpi_mois"]} == {
        ("DEMO-2001", "2026-09", "Complet", "Consolide_KPI_2026.xlsx"), ("DEMO-2001", "2026-10", "Estimé", "Consolide_KPI_2026.xlsx"),
        ("DEMO-2002", "2026-10", "Complet", "Consolide_KPI_2026.xlsx")}
    assert T["depots_kpi"][0]["residences"] == 2 and T["depots_kpi"][0]["modifiees"] == 1 and T["depots_kpi"][0]["ecartees"] == 1
    # Suivi des mois et historique
    pg.evaluate("etat.lo = MOIS.indexOf('2026-09'); etat.hi = MOIS.indexOf('2026-10') + 1; majContenu();")
    suivi = pg.inner_text("#ext-suivi")
    assert "Les Terrasses du Port" in suivi and "✔" in suivi and "~" in suivi
    assert "Consolide_KPI_2026.xlsx" in pg.inner_text("#ext-depots")
    # Détail des calculs : le mois estimé est signalé
    note = pg.evaluate("EXPLIQUER.mes({ k: 'NUITEES_CLIENTS', d: ['DEMO-2001'], m: ['2026-10'], a: false })")
    assert any("Estimé" in x for x in note.get("notes", [])) and note["parts"][0]["val"] == "1 500"
    # Deuxième dépôt du même fichier : rien de nouveau
    deposer(pg, "GROUPE")
    R = pg.evaluate("etat.import.R")
    assert R["nouvelles"] == 0 and R["modifiees"] == 0 and R["statuts"] == []
    assert "Rien de nouveau" in pg.inner_text("#cons-resultat") and pg.query_selector("#cons-ok") is None
    assert erreurs == []
    pg.close()


def test_perimetre_d_une_residence(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    deposer(pg, "DEMO-2002")
    R = pg.evaluate("etat.import.R")
    assert list(R["parRes"]) == ["DEMO-2002"] and R["horsPerimetre"] == 2
    assert {v["dossier"] for v in R["valeurs"]} == {"DEMO-2002"}
    assert "hors du périmètre" in pg.inner_text("#cons-resultat")
    pg.close()


def test_rattachement_depuis_l_apercu(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    deposer(pg, "GROUPE")
    pg.select_option("[data-cons-rat='0']", "DEMO-2003")  # ABCZS -> Les Tilleuls
    pg.click("#cons-rat-ok")
    pg.wait_for_function("etat.import && etat.import.R.nonRattachees.length === 1")
    assert pg.evaluate("tablesTest.residences.find(r => r.id === 'RES-003').code_mews") == "ABCZS"
    R = pg.evaluate("etat.import.R")
    assert "DEMO-2003" in R["parRes"] and [x["code"] for x in R["nonRattachees"]] == ["ZZZ"]
    assert erreurs == []
    pg.close()


def test_groupes_du_fichier(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables(groupes=[{"id": "GR-RM-ANCIEN", "libelle": "RM Ancien"}],
                                                       residence_groupe=[{"residence_id": "RES-001", "groupe_id": "GR-RM-ANCIEN"},
                                                                         {"residence_id": "RES-001", "groupe_id": "GRP-SENIORS"}]))
    pg.evaluate("window.rechargements = 0; RECHARGER = function () { rechargements++; }; true")
    deposer(pg, "GROUPE")
    pg.click("#cons-groupes-ok")
    pg.wait_for_function("rechargements === 1")
    T = pg.evaluate("tablesTest")
    ids = {g["id"] for g in T["groupes"]}
    assert {"GR-SEG-RT", "GR-REG-SUD-EST", "GR-REG-NORD", "GR-RM-RM-FICTIF", "GR-RM-RM-DEUX"} <= ids
    liens = {(l["residence_id"], l["groupe_id"]) for l in T["residence_groupe"]}
    assert ("RES-001", "GR-RM-RM-FICTIF") in liens and ("RES-002", "GR-REG-NORD") in liens
    assert ("RES-001", "GR-RM-ANCIEN") not in liens        # ancien RM de la résidence retiré
    assert ("RES-001", "GRP-SENIORS") in liens             # groupe créé à la main : jamais touché
    assert erreurs == []
    pg.close()


def test_structure_refusee(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    L = fichier()
    L[0] = [("Période" if h == "Mois" else h) for h in L[0]]
    for l in L[1:6]:
        l[ENTETES.index("Année")] = None
    deposer(pg, "GROUPE", L)
    assert "Dépôt refusé" in pg.inner_text("#cons-resultat") and pg.query_selector("#cons-ok") is None
    doublon = fichier()
    doublon.insert(2, list(doublon[1]))
    deposer(pg, "GROUPE", doublon)
    assert "déjà fourni ligne 2" in pg.inner_text("#cons-resultat")
    assert pg.evaluate("estConsolide([[ 'Code résidence', 'Mois (AAAA-MM)' ]])") is False
    pg.close()


# ------------------------------------------------------------------------------------------- connexions

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
