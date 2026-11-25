"""Lot 18b dans un vrai navigateur (données fictives) : page Import comptable avec le dossier Pennylane de
test, période d'import, masquage du brouillard, synchronisation d'une résidence ou d'un groupe par la
fonction serveur (simulée), suivi de la demande, droits (collaborateur) et page hors ligne.
Ignorés si Playwright n'est pas installé."""
import json
import pathlib
import sys
from datetime import date

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "tests"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402
import publier_supabase as pub  # noqa: E402
from test_lot13_page import CLIENT_SIMULE  # noqa: E402
from test_lot18_connecteur import client  # noqa: E402

# Fonction serveur simulée : enregistre les appels ; réponse choisie par le test.
FONCTION_SIMULEE = """
window.appelsFonction = [];
window.reponseFonction = { data: { id: 42, statut: 'demandée' }, error: null };
window.avecFonction = function (c) {
  c.functions = { invoke: function (nom, o) { appelsFonction.push({ nom: nom, body: JSON.parse(JSON.stringify(o.body)) });
    return Promise.resolve(window.reponseFonction); } };
  return c;
};
true;
"""


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site18b")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    py = pub.lire_pennylane(str(demo), client=client(), mode="valides", periode=(date(2026, 1, 1), date(2026, 4, 30)))
    commun, par = pub.calculer(str(demo), pennylane=py)
    par["PENNY-TEST"]["source"].update({"periode": py[2]["periode"], "brouillard": py[2]["brouillard"]})
    base = [{"id": c["residence"]["code"], "dossier_pennylane": d, "fictif": True} for d, c in par.items()]
    commune, lignes, _ = pub.lignes_a_publier(commun, par, base)
    lignes = json.loads(json.dumps([{"residence_id": l["residence_id"], "contenu": l["contenu"]} for l in lignes]))
    donnees = generer_site.construire(str(demo))
    complet, vide = dossier / "complet.html", dossier / "en_ligne.html"
    generer_site.ecrire(str(complet), donnees)
    generer_site.ecrire(str(vide), None)
    with playwright.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield {"nav": nav, "complet": complet, "vide": vide, "commun": json.loads(json.dumps(commune["contenu"])),
               "lignes": lignes}
        nav.close()


def demarrer(site, role="administrateur", tables_en_plus=None, sans_migration=False):
    pg = site["nav"].new_page(viewport={"width": 1500, "height": 1000})
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(site["vide"].as_uri())
    pg.evaluate(CLIENT_SIMULE + FONCTION_SIMULEE)
    tables = {"donnees_communes": [{"id": "SITE", "contenu": site["commun"]}], "donnees_residences": site["lignes"],
              "groupes": [], "residence_groupe": [], "ajustements": [], "comptes_simules": []}
    if not sans_migration:
        tables.update({"parametres_import": [{"dossier": "PENNY-TEST", "mois_debut": "2026-01", "mois_fin": "2026-04",
                                              "masquer_brouillard": True}], "synchronisations": []})
    tables.update(tables_en_plus or {})
    pg.evaluate("(a) => { window.tablesTest = a[0]; return demarrerAvecClient(avecFonction(clientSimule(a[0])), "
                "{ email: 'admin@exemple.invalid', nom: 'Admin Fictif', role: a[1] }); }", [tables, role])
    pg.wait_for_selector("#ecran-choix.visible")
    return pg, erreurs


def aller(pg, perim):
    pg.evaluate(f"choisir('{perim}'); allerA('import', 'pennylane')")
    pg.wait_for_selector("#imp-synchro")


def test_residence_connectee(site):
    pg, erreurs = demarrer(site)
    aller(pg, "PENNY-TEST")
    texte = pg.inner_text("#contenu")
    assert "Connexion Pennylane active (lecture seule)" in texte and "Écritures validées seulement" in texte
    assert "Exercice précédent complet (N-1)" in pg.inner_text("#imp-periode")  # lot 22 : règle à la place des dates
    assert pg.get_attribute("#imp-brouillard", "aria-pressed") == "true"
    assert "2 ligne(s) en brouillard" in texte and "charges 50 €" in texte and "masquées" in texte
    assert "Analytique" not in texte and "Balances mensuelles" not in texte  # options retirées
    assert erreurs == []
    pg.close()


def test_synchroniser_une_residence_et_suivre(site):
    pg, erreurs = demarrer(site)
    aller(pg, "PENNY-TEST")
    pg.click("#imp-brouillard")
    pg.click("#imp-synchro")
    pg.wait_for_function("appelsFonction.length === 1")
    appel = pg.evaluate("appelsFonction[0]")
    assert appel == {"nom": "lancer-synchro", "body": {"dossiers": ["PENNY-TEST"], "perimetre": "Dossier Pennylane de test",
                                                        "mois_debut": None, "mois_fin": None, "masquer_brouillard": False}}
    pg.wait_for_selector("#imp-historique")
    assert "Synchronisation n° 42 lancée" in pg.inner_text("#imp-message")
    assert "demandée" in pg.inner_text("#imp-historique")
    # La base passe la demande à « terminée » : le suivi l'affiche et propose de recharger
    pg.evaluate("window.rechargements = 0; RECHARGER = function () { rechargements++; }; true")
    pg.evaluate("SYNC_DELAI = 50; tablesTest.synchronisations = [{ id: 42, statut: 'terminée', demandee_le: '2026-11-24T10:00:00Z', "
                "demandee_par: 'admin@exemple.invalid', perimetre: 'Dossier Pennylane de test', dossiers: ['PENNY-TEST'], "
                "mois_debut: null, mois_fin: null, masquer_brouillard: false, "
                "resultat: { 'PENNY-TEST': { statut: 'synchronisée', lignes_reprises: 6 } } }]; suivreSynchro();")
    pg.wait_for_selector("#imp-recharger")
    assert "6 lignes" in pg.inner_text("#imp-historique")
    pg.wait_for_function("rechargements === 1")  # lot 18c : chiffres rechargés automatiquement
    # Les réglages restent affichés
    pg.evaluate("majContenu()")
    assert pg.get_attribute("#imp-brouillard", "aria-pressed") == "false" and "N-1 + N" in pg.inner_text("#imp-historique")
    assert erreurs == []
    pg.close()


def test_synchroniser_un_groupe(site):
    pg, erreurs = demarrer(site)
    aller(pg, "GROUPE")
    assert pg.inner_text("#imp-synchro") == "Synchroniser les 9 résidences"
    texte = pg.inner_text("#contenu")
    assert "1 résidence(s) sur 9 connectée(s)" in texte and texte.count("non connectée") >= 8
    pg.click("#imp-synchro")
    pg.wait_for_function("appelsFonction.length === 1")
    body = pg.evaluate("appelsFonction[0].body")
    assert sorted(body["dossiers"]) == sorted([f"DEMO-200{i}" for i in range(1, 9)] + ["PENNY-TEST"])
    assert body["perimetre"] == "Groupe Zenitude"
    assert erreurs == []
    pg.close()


def test_refus_de_la_fonction(site):
    pg, erreurs = demarrer(site)
    pg.evaluate("reponseFonction = { data: null, error: { message: 'Edge Function returned a non-2xx status code', "
                "context: { json: function () { return Promise.resolve({ erreur: 'une synchronisation est déjà en cours (n° 41)' }); } } } }")
    aller(pg, "PENNY-TEST")
    pg.click("#imp-synchro")
    pg.wait_for_function("document.getElementById('imp-message').innerText.indexOf('non lancée') >= 0")
    assert "déjà en cours (n° 41)" in pg.inner_text("#imp-message")
    assert pg.is_enabled("#imp-synchro")
    assert erreurs == []
    pg.close()


def test_collaborateur_sans_synchronisation(site):
    pg, erreurs = demarrer(site, role="collaborateur")
    aller(pg, "PENNY-TEST")
    assert pg.is_disabled("#imp-synchro") and pg.is_disabled("#imp-brouillard")
    assert pg.query_selector("#imp-historique") is None
    assert erreurs == []
    pg.close()


def test_sans_migration_007(site):
    pg, erreurs = demarrer(site, sans_migration=True)
    aller(pg, "PENNY-TEST")
    assert "Aucune synchronisation lancée" in pg.inner_text("#imp-historique")
    assert erreurs == []
    pg.close()


def test_page_hors_ligne(site):
    pg = site["nav"].new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); localStorage.clear()")
    pg.reload()
    pg.wait_for_selector("#ecran-choix.visible")
    pg.evaluate("choisir('DEMO-2001'); allerA('import', 'pennylane')")
    assert pg.is_disabled("#imp-synchro")
    assert "Résidence non connectée à Pennylane" in pg.inner_text("#contenu")
    assert erreurs == []
    pg.close()


def test_heures_de_paris(site):
    pg, erreurs = demarrer(site)
    assert pg.evaluate("dateHeure('2026-11-24T14:08:00+00:00')") == "24/11/2026 15:08"
    assert pg.evaluate("dateHeure('2026-11-24T13:57:00')") == "24/11/2026 14:57"  # sans fuseau : heure universelle
    assert pg.evaluate("dateHeure('2026-07-01T10:00:00Z')") == "01/07/2026 12:00"  # heure d'été
    assert pg.evaluate("dateHeure('2026-11-24')") == "24/11/2026"
    assert erreurs == []
    pg.close()


def test_retour_sur_la_page_apres_rechargement(site):
    pg = site["nav"].new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(site["complet"].as_uri())
    pg.evaluate("sessionStorage.setItem('zen-utilisateur', JSON.stringify({ mail: 'demo@exemple.invalid', nom: 'Démo', ini: 'D' })); "
                "sessionStorage.setItem('zen-perim', JSON.stringify('DEMO-2001')); "
                "sessionStorage.setItem('zen-apres-recharge', JSON.stringify(['import', 'pennylane']))")
    pg.reload()
    pg.wait_for_selector("#imp-synchro")
    assert pg.evaluate("etat.page") == "pennylane" and pg.evaluate("sessionStorage.getItem('zen-apres-recharge')") is None
    assert erreurs == []
    pg.close()
