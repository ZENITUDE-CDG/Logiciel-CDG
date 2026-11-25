"""Lot 18b (décision 0012) : synchronisation pilotée depuis la page.

Sans réseau ni secret : une fausse base Supabase (requêtes REST simulées) et le faux serveur Pennylane du
lot 18. Vérifie le traitement d'une demande (statuts, résultat par résidence, résidences non connectées),
l'usage des paramètres d'import (période, brouillard), les échecs (la demande ne reste jamais « en cours »),
la période d'import dans le connecteur et les sommes du brouillard (jamais dans les journaux).
"""
import pathlib
import sys
from datetime import date

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE))
import publier_supabase as pub  # noqa: E402
from test_lot18_connecteur import AUJOURDHUI, ENTREES, FauxPennylane, client  # noqa: E402
from zenitude.connecteurs import pennylane as pl  # noqa: E402

BASE = "https://exemple.supabase.co"


class FausseBase:
    def __init__(self, demande=None, params=None, sans_migration=False):
        self.demandes = {demande["id"]: dict(demande)} if demande else {}
        self.params = params or []
        self.sans_migration = sans_migration
        self.historique = []
        self.publie = {}

    def __call__(self, methode, url, cle, corps=None, prefer=None):
        chemin = url.split("/rest/v1/")[1]
        self.historique.append((methode, chemin, corps))
        if methode == "GET" and chemin.startswith("residences"):
            return [{"id": "RES-00" + str(i), "dossier_pennylane": f"DEMO-200{i}", "fictif": True} for i in range(1, 9)] + \
                   [{"id": "RES-TEST", "dossier_pennylane": "PENNY-TEST", "fictif": True}]
        if methode == "GET" and chemin.startswith("parametres_import"):
            if self.sans_migration:
                raise pub.PublicationRefusee("Supabase a refusé GET parametres_import (code 404) : PGRST205")
            return self.params
        if methode == "GET" and chemin.startswith("lettrages_pennylane"):
            return []
        # Lot 19 : connexions Pennylane (jetons chiffrés) et clé publique
        if methode == "GET" and chemin.startswith("connexions_pennylane"):
            return list(getattr(self, "connexions", []))
        if methode == "PATCH" and chemin.startswith("connexions_pennylane"):
            self.maj_connexions = getattr(self, "maj_connexions", []) + [(chemin.split("dossier=eq.")[1], corps)]
            return None
        if methode == "GET" and chemin.startswith("cle_jetons"):
            return list(getattr(self, "cles", []))
        if chemin.startswith("pennylane_"):
            self.magasin = getattr(self, "magasin", []) + [(methode, chemin.split("?")[0])]
            return [] if methode == "GET" else None
        if methode == "POST" and chemin.startswith("lettrages_pennylane"):
            self.lettrages = getattr(self, "lettrages", []) + corps
            return None
        if methode == "GET" and chemin.startswith("synchronisations"):
            ident = int(chemin.split("id=eq.")[1].split("&")[0])
            return [self.demandes[ident]] if ident in self.demandes else []
        if methode == "PATCH" and chemin.startswith("synchronisations"):
            ident = int(chemin.split("id=eq.")[1])
            self.demandes[ident].update(corps)
            return None
        if methode == "POST":
            for ligne in corps:
                self.publie[ligne.get("residence_id") or ligne.get("id")] = ligne
            return None
        raise AssertionError(f"requête inattendue : {methode} {chemin}")

    def statuts(self, ident):
        return [c["statut"] for m, ch, c in self.historique if m == "PATCH" and f"id=eq.{ident}" in ch]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_FICTIF")
    monkeypatch.setenv("PENNYLANE_TOKEN_PILOTE", "jeton-fictif")
    monkeypatch.delenv("PENNYLANE_MODE", raising=False)
    monkeypatch.setattr(pub, "url_supabase", lambda: BASE)
    appels, regles = [], []
    vrai = pub.lire_pennylane
    monkeypatch.regles = regles

    def lire(jeton=None, mode="valides", periode=None, regle=None, **kw):
        appels.append({"mode": mode, "periode": periode})
        regles.append(regle)
        return vrai(client=client(), mode=mode, periode=periode, regle=regle)
    monkeypatch.setattr(pub, "lire_pennylane", lire)
    return monkeypatch, appels


DEMANDE = {"id": 7, "perimetre": "Groupe test", "dossiers": ["PENNY-TEST", "DEMO-2001"], "mois_debut": "2026-01",
           "mois_fin": "2026-03", "masquer_brouillard": True, "statut": "demandée"}


def test_demande_traitee(env, capsys):
    mp, appels = env
    base = FausseBase(DEMANDE)
    mp.setattr(pub, "requete", base)
    assert pub.main(["--demande", "7"]) == 0
    assert base.statuts(7) == ["en cours", "terminée"]
    assert appels == [{"mode": "valides", "periode": (date(2026, 1, 1), date(2026, 3, 31))}]
    res = base.demandes[7]["resultat"]
    assert res["PENNY-TEST"]["statut"] == "synchronisée" and res["PENNY-TEST"]["periode"] == ["2026-01-01", "2026-03-31"]
    assert res["DEMO-2001"] == {"statut": "non connectée", "motif": "aucun jeton Pennylane pour ce dossier"}
    # Période : seules les écritures de mars (achat F001) ; avril exclu et compté
    src = base.publie["RES-TEST"]["contenu"]["source"]
    assert src["periode"] == ["2026-01-01", "2026-03-31"] and src["mode"] == "valides"
    assert src["brouillard"] == {"lignes": 2, "masque": True, "charges": "50.00", "produits": "0.00"}
    sortie = capsys.readouterr().out
    assert "50.00" not in sortie and "filtre de dates appliqué par Pennylane : oui" in sortie
    assert "RES-001" in base.publie  # la démonstration est republiée avec


def test_brouillard_affiche_quand_il_est_repris(env):
    mp, appels = env
    base = FausseBase(dict(DEMANDE, masquer_brouillard=False, mois_debut=None, mois_fin=None))
    mp.setattr(pub, "requete", base)
    assert pub.main(["--demande", "7"]) == 0
    assert appels[0] == {"mode": "tous", "periode": None}
    assert base.publie["RES-TEST"]["contenu"]["source"]["brouillard"]["masque"] is False


def test_parametres_pour_la_publication_automatique(env):
    mp, appels = env
    base = FausseBase(params=[{"dossier": "PENNY-TEST", "mois_debut": "2026-02", "mois_fin": None,
                               "masquer_brouillard": False}])
    mp.setattr(pub, "requete", base)
    assert pub.main([]) == 0
    # Lot 22 : les mois enregistrés au lot 18b ne servent plus ; la règle N-1 + N s'applique (le mode reste lu)
    assert appels == [{"mode": "tous", "periode": None}] and mp.regles == ["n1_n"]
    mp.setenv("PENNYLANE_MODE", "valides")  # choix au lancement manuel : prime sur la base
    assert pub.main([]) == 0 and appels[-1]["mode"] == "valides"


def test_sans_migration_007(env, capsys):
    mp, appels = env
    mp.setattr(pub, "requete", FausseBase(sans_migration=True))
    assert pub.main([]) == 0
    assert appels == [{"mode": "valides", "periode": None}]
    assert "migration 007 non appliquée" in capsys.readouterr().out


def test_echec_pennylane(env):
    mp, _ = env

    def echec(**kw):
        raise pl.ErreurPennylane("réponse inattendue de Pennylane (code 503) sur /journals")
    mp.setattr(pub, "lire_pennylane", echec)
    base = FausseBase(DEMANDE)
    mp.setattr(pub, "requete", base)
    assert pub.main(["--demande", "7"]) == 1
    assert base.statuts(7) == ["en cours", "échec"] and "503" in base.demandes[7]["message"]
    assert not base.publie
    # Publication automatique (sans demande) : la démonstration est publiée seule
    base2 = FausseBase()
    mp.setattr(pub, "requete", base2)
    assert pub.main([]) == 0 and "RES-001" in base2.publie and "RES-TEST" not in base2.publie


def test_sans_jeton(env):
    mp, _ = env
    mp.delenv("PENNYLANE_TOKEN_PILOTE")
    base = FausseBase(DEMANDE)
    mp.setattr(pub, "requete", base)
    assert pub.main(["--demande", "7"]) == 1
    assert base.demandes[7]["statut"] == "échec" and "PENNYLANE_TOKEN_PILOTE" in base.demandes[7]["message"]
    # Demande sans le dossier de test : rien à lire, les résidences sont signalées non connectées
    base2 = FausseBase(dict(DEMANDE, dossiers=["DEMO-2003"]))
    mp.setattr(pub, "requete", base2)
    assert pub.main(["--demande", "7"]) == 0
    assert base2.demandes[7]["resultat"] == {"DEMO-2003": {"statut": "non connectée",
                                                           "motif": "aucun jeton Pennylane pour ce dossier"}}


def test_erreur_inattendue_ne_laisse_pas_en_cours(env):
    mp, _ = env
    base = FausseBase(DEMANDE)
    mp.setattr(pub, "requete", base)

    def boum(**kw):
        raise RuntimeError("panne fictive")
    mp.setattr(pub, "calculer", boum)
    with pytest.raises(RuntimeError):
        pub.main(["--demande", "7"])
    assert base.demandes[7]["statut"] == "échec" and "panne fictive" in base.demandes[7]["message"]


def test_demande_introuvable(env):
    mp, _ = env
    mp.setattr(pub, "requete", FausseBase())
    assert pub.main(["--demande", "99"]) == 1


def test_periode_dans_le_connecteur():
    lignes, _, r = pl.extraire(client(), "PENNY-TEST", "tous", depuis=date(2025, 10, 1), aujourdhui=AUJOURDHUI,
                               periode=(date(2026, 4, 1), date(2026, 4, 30)))
    assert {l["date"][:7] for l in lignes} == {"2026-04"}
    assert r["lignes_hors_periode"] == 0 and r["lecture"]["filtre_dates"]  # période demandée à Pennylane
    assert r["periode"] == ["2026-04-01", "2026-04-30"]
    assert "50.00" not in pl.texte_rapport(r)


def test_periode_de():
    assert pub.periode_de(None) is None
    assert pub.periode_de({"mois_debut": None, "mois_fin": None}) is None
    assert pub.periode_de({"mois_debut": "2026-02", "mois_fin": "2026-02"}) == (date(2026, 2, 1), date(2026, 2, 28))
    assert pub.periode_de({"mois_debut": None, "mois_fin": "2024-02"})[1] == date(2024, 2, 29)


def test_aucune_entree_inutilisee():
    assert len(ENTREES) == 6 and FauxPennylane().taille == 2
