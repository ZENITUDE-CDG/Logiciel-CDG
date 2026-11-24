"""Lot 18 : connecteur Pennylane (lecture seule) et publication du dossier de test (décision 0011).

Aucun réseau, aucun secret : un faux serveur Pennylane renvoie des réponses JSON synthétiques,
marquées « fictif ». Vérifie la pagination, la reprise sur 429, la limite de débit, la correspondance
des champs, le filtre par statut, la liste blanche, le lettrage, le rapport sans montant, et que la
publication ajoute RES-TEST sans changer les huit résidences de démonstration.
"""
import json
import pathlib
import sys
import urllib.parse
from datetime import date

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE))
import generer_demo  # noqa: E402
import publier_supabase as pub  # noqa: E402
import source_pennylane  # noqa: E402
from zenitude.connecteurs import pennylane as pl  # noqa: E402

BASE = pl.BASE
AUJOURDHUI = date(2026, 11, 24)


def _ligne(i, entree, jour, journal, compte, debit="0.0", credit="0.0", libelle="Ligne fictive", lettre=False):
    return {"id": i, "date": jour, "journal": {"id": journal, "url": "x"}, "label": libelle,
            "ledger_account": {"id": 900 + i, "number": compte, "url": "x"},
            "ledger_entry": {"id": entree}, "debit": debit, "credit": credit,
            "lettered_ledger_entry_lines": {"url": f"{BASE}/ledger_entry_lines/{i}/lettered_ledger_entry_lines"}
            if lettre else None, "created_at": "x", "updated_at": "x"}


ENTREES = [
    {"id": 1, "date": "2026-03-10", "piece_number": "F001", "invoice_number": None, "label": "Achat fictif",
     "status": "validated", "journal_id": 1},
    {"id": 2, "date": "2026-03-12", "piece_number": "F002", "label": "Honoraires fictifs", "status": "draft",
     "journal_id": 1},
    {"id": 3, "date": "2026-04-01", "piece_number": "V001", "label": "Vente fictive", "status": "etrange",
     "journal_id": 2},
    {"id": 4, "date": "2026-04-02", "piece_number": None, "invoice_number": None, "label": "Vente sans pièce",
     "status": "validated", "journal_id": 2},
    {"id": 5, "date": "2025-03-01", "piece_number": "F000", "label": "Ancienne", "status": "validated",
     "journal_id": 1},
    {"id": 6, "date": "2026-04-15", "piece_number": "R001", "label": "Règlement fictif", "status": "validated",
     "journal_id": 3},
]
LIGNES = [
    _ligne(11, 1, "2026-03-10", 1, "6064000", debit="100.00", lettre=False),
    _ligne(12, 1, "2026-03-10", 1, "4010001", credit="100.00", lettre=True),
    _ligne(21, 2, "2026-03-12", 1, "6226000", debit="50.00"),
    _ligne(22, 2, "2026-03-12", 1, "4010002", credit="50.00", lettre=True),
    _ligne(31, 3, "2026-04-01", 2, "4110001", debit="200.00", lettre=True),
    _ligne(32, 3, "2026-04-01", 2, "7060000", credit="200.00"),
    _ligne(41, 4, "2026-04-02", 2, "4110001", debit="80.00"),
    _ligne(42, 4, "2026-04-02", 2, "7061000", credit="80.00"),
    _ligne(51, 5, "2025-03-01", 1, "6064000", debit="10.00"),
    _ligne(52, 5, "2025-03-01", 1, "4010001", credit="10.00"),
    _ligne(61, 6, "2026-04-15", 3, "4010001", debit="100.00", lettre=True),
    _ligne(62, 6, "2026-04-15", 3, "5120000", credit="100.00"),
]
# Groupes de lettrage : la facture fournisseur (ligne 12) et son règlement (ligne 61) ; lignes 22 et 31 non lettrées
LETTRAGE = {12: [12, 61], 61: [12, 61], 22: [], 31: []}


class FauxPennylane:
    """Faux serveur : pagination par deux éléments, un 429 au premier appel des journaux."""

    def __init__(self, entrees=ENTREES, lignes=LIGNES, taille=2):
        self.donnees = {
            "/fiscal_years": [{"id": 1, "start": "2025-01-01", "finish": "2025-12-31", "status": "closed"},
                              {"id": 2, "start": "2026-01-01", "finish": "2026-12-31", "status": "open"}],
            "/journals": [{"id": 1, "code": "HA", "label": "Achats", "type": "purchase"},
                          {"id": 2, "code": "VT", "label": "Ventes", "type": "sale"},
                          {"id": 3, "code": "BQ", "label": "Banque", "type": "bank"}],
            "/ledger_accounts": [{"id": 1, "number": "4010001", "type": "supplier"},
                                 {"id": 2, "number": "6064000", "type": "general"}],
            "/ledger_entries": entrees,
            "/ledger_entry_lines": lignes,
        }
        self.taille = taille
        self.appels = []
        self.deja_429 = False

    def __call__(self, url, entetes):
        assert entetes["Authorization"] == "Bearer jeton-fictif"
        self.appels.append(url)
        parts = urllib.parse.urlsplit(url)
        chemin = parts.path.replace("/api/external/v2", "")
        q = dict(urllib.parse.parse_qsl(parts.query))
        if chemin == "/journals" and not self.deja_429:
            self.deja_429 = True
            return 429, {"Retry-After": "1"}, ""
        if chemin.endswith("/lettered_ledger_entry_lines"):
            i = int(chemin.split("/")[2])
            return 200, {}, json.dumps({"items": [{"id": x} for x in LETTRAGE.get(i, [])],
                                        "has_more": False, "next_cursor": None})
        items = self.donnees[chemin]
        debut = int(q.get("cursor") or 0)
        page = items[debut:debut + self.taille]
        suite = debut + self.taille < len(items)
        return 200, {}, json.dumps({"items": page, "has_more": suite,
                                    "next_cursor": str(debut + self.taille) if suite else None})


def client(serveur=None):
    return pl.Client("jeton-fictif", ouvrir=serveur or FauxPennylane(), dormir=lambda s: None)


def extraire(mode="valides", depuis=date(2025, 10, 1), serveur=None):
    return pl.extraire(client(serveur), "PENNY-TEST", mode, depuis=depuis, aujourdhui=AUJOURDHUI)


def test_correspondance_des_champs():
    lignes, exercice, rapport = extraire("valides")
    par = {(l["piece"], l["compte"]): l for l in lignes}
    assert set(par) == {("F001", "6064000"), ("F001", "4010001"), ("PL4", "4110001"), ("PL4", "7061000"),
                        ("R001", "4010001"), ("R001", "5120000")}
    achat = par[("F001", "6064000")]
    assert achat == {"dossier": "PENNY-TEST", "exercice": "2026-01-01/2026-12-31", "date": "2026-03-10",
                     "journal": "HA", "piece": "F001", "compte": "6064000", "libelle": "Ligne fictive",
                     "debit": "100.00", "credit": "", "tiers": "", "lettrage": "", "echeance": ""}
    assert par[("F001", "4010001")]["tiers"] == "4010001"
    assert par[("F001", "4010001")]["lettrage"] == par[("R001", "4010001")]["lettrage"] == "L12"
    assert par[("PL4", "4110001")]["lettrage"] == ""  # pas de lien de lettrage : vide, jamais inventé
    assert all(l["echeance"] == "" for l in lignes)
    assert list(lignes[0]) == pl.COLONNES_ECRITURES
    assert exercice == {"dossier": "PENNY-TEST", "debut": "2026-01-01", "fin": "2026-12-31", "duree_mois": "12"}
    assert rapport["equilibre"] is True


def test_filtre_par_statut():
    lignes, _, rapport = extraire("valides")
    assert rapport["lignes_ecartees"] == {"draft": 2, "etrange": 2}
    assert rapport["statuts_inconnus"] == ["etrange"]
    assert rapport["statuts"]["etrange"]["traitement"].startswith("inconnu")
    tous, _, r2 = extraire("tous")
    assert len(tous) == len(lignes) + 4 and r2["lignes_ecartees"] == {}
    with pytest.raises(pl.ErreurPennylane, match="mode inconnu"):
        extraire("brouillard")


def test_ecritures_anterieures_comptees_non_reprises():
    _, _, rapport = extraire("valides")
    assert rapport["lignes_anterieures"] == 2
    lignes, _, r = extraire("valides", depuis=None)
    assert r["lignes_anterieures"] == 0 and any(l["date"] == "2025-03-01" for l in lignes)


def test_exercice_reel_retenu():
    exos = [(date(2025, 10, 1), date(2026, 6, 30)), (date(2026, 7, 1), date(2027, 6, 30))]
    assert pl.choisir_exercice(exos, AUJOURDHUI) == exos[1]
    assert pl._duree_mois(date(2025, 10, 1), date(2026, 6, 30)) == 9  # exercice de neuf mois : neuf mois


def test_liste_blanche():
    with pytest.raises(pl.ErreurPennylane, match="liste blanche"):
        pl.extraire(client(), "DEMO-2001", "valides")


def test_adresse_hors_api_refusee():
    with pytest.raises(pl.ErreurPennylane, match="hors de l'API"):
        client().get_url("https://exemple.invalid/vol-du-jeton")


def test_pagination_et_reprise_sur_429():
    serveur = FauxPennylane()
    lignes, _, rapport = extraire("tous", serveur=serveur)
    assert rapport["lignes_lues"] == len(LIGNES)
    assert sum("/journals" in u for u in serveur.appels) == 3  # 429, puis deux pages
    assert any("cursor=" in u for u in serveur.appels)


def test_limite_de_debit():
    temps = [0.0]
    attentes = []

    def dormir(s):
        attentes.append(s)
        temps[0] += s

    c = pl.Client("jeton-fictif", ouvrir=lambda u, h: (200, {}, "{}"), dormir=dormir, horloge=lambda: temps[0])
    for _ in range(60):
        c.get("/journals")
    assert len(attentes) >= 2 and all(0 < a <= pl.FENETRE_SECONDES + 0.1 for a in attentes)


def test_erreurs_lisibles_sans_contenu():
    secret = "CONTENU-QUI-NE-DOIT-PAS-SORTIR"
    c = pl.Client("jeton-fictif", ouvrir=lambda u, h: (500, {}, secret), dormir=lambda s: None)
    with pytest.raises(pl.ErreurPennylane) as e:
        c.get("/journals")
    assert secret not in str(e.value) and "500" in str(e.value)
    c = pl.Client("jeton-fictif", ouvrir=lambda u, h: (401, {}, ""), dormir=lambda s: None)
    with pytest.raises(pl.ErreurPennylane, match="401"):
        c.get("/journals")


def test_rapport_sans_montant_ni_libelle():
    _, _, rapport = extraire("tous")
    texte = pl.texte_rapport(rapport)
    for interdit in ("100.00", "200.00", "Ligne fictive", "Achat fictif", "jeton-fictif"):
        assert interdit not in texte
    assert "Statuts des écritures" in texte and "équilibrées" in texte


# ---------------------------------------------------------------------------- publication

@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo18")
    generer_demo.main(str(d))
    return str(d)


@pytest.fixture(scope="module")
def avec_et_sans(demo):
    donnees = pub.lire_pennylane(demo, client=client(), mode="tous")
    return pub.calculer(demo, pennylane=donnees), pub.calculer(demo)


def test_residence_de_test_publiee(avec_et_sans):
    (commun, par), _ = avec_et_sans
    assert "PENNY-TEST" in par
    c = par["PENNY-TEST"]
    assert c["residence"]["code"] == "RES-TEST" and c["nb_ecritures"] == 10
    assert c["source"]["mode"] == "tous" and c["source"]["libelle_mode"] == "Écritures validées et brouillard"
    assert c["source"]["comptes_provisoires"] == ["622"]  # 6226000 : seul compte de charge non couvert
    assert c["finance"]["statut"] == "publié"


def test_residences_de_demonstration_inchangees(avec_et_sans):
    (_, par), (_, par_demo) = avec_et_sans
    assert sorted(par) == sorted(list(par_demo) + ["PENNY-TEST"])
    for d, contenu in par_demo.items():
        avec = json.loads(json.dumps(par[d]))
        sans = json.loads(json.dumps(contenu))
        for x in (avec, sans):
            x["finance"].pop("publication", None)
        assert avec == sans, d


def test_partie_commune_sans_donnee_du_dossier_de_test(avec_et_sans):
    (commun, _), _ = avec_et_sans
    texte = json.dumps(commun, ensure_ascii=False)
    assert "PENNY-TEST" not in texte and "Dossier Pennylane de test" not in texte and "RES-TEST" not in texte


def test_garde_fous_de_publication(avec_et_sans):
    (commun, par), _ = avec_et_sans
    base = [{"id": c["residence"]["code"], "dossier_pennylane": d, "fictif": True} for d, c in par.items()]
    commune, lignes, avert = pub.lignes_a_publier(commun, par, base)
    assert "RES-TEST" in [l["residence_id"] for l in lignes] and avert == []
    for b in base:
        if b["id"] == "RES-TEST":
            b["fictif"] = False
    with pytest.raises(pub.PublicationRefusee, match="réelles"):
        pub.lignes_a_publier(commun, par, base)


def test_classement_provisoire_ne_touche_pas_les_comptes_couverts():
    nouvelles = source_pennylane.classement_provisoire({"6064000", "6226000", "6228000", "7580000", "4010001"},
                                                       ["606", "706"])
    assert [(r["Préfixe ou plage de comptes"], r["Agrégat de base"]) for r in nouvelles] == \
        [("622", "PL_CHARGES"), ("758", "CA_SERVICES")]


def test_assemblage_hors_du_depot(demo, tmp_path):
    lignes, exercice, _ = extraire("tous")
    avant = sorted(p.name for p in pathlib.Path(demo).iterdir())
    source_pennylane.assembler(demo, str(tmp_path / "s"), lignes, exercice)
    assert sorted(p.name for p in pathlib.Path(demo).iterdir()) == avant
    assert (tmp_path / "s" / "configuration.xlsx").exists()


def test_lecture_obligatoire_ou_facultative(monkeypatch, capsys):
    monkeypatch.delenv("PENNYLANE_TOKEN_PILOTE", raising=False)
    assert pub._avec_pennylane(["--pennylane"]) == (None, 1)
    assert pub._avec_pennylane([]) == (None, 0)
    monkeypatch.setenv("PENNYLANE_TOKEN_PILOTE", "jeton-fictif")

    def echec(**kw):
        raise pl.ErreurPennylane("réponse inattendue de Pennylane (code 503) sur /journals")
    monkeypatch.setattr(pub, "lire_pennylane", echec)
    assert pub._avec_pennylane(["--pennylane"]) == (None, 1)
    assert pub._avec_pennylane([]) == (None, 0)
    assert "publication sans lui" in capsys.readouterr().out


def test_installation_contient_la_residence_de_test():
    texte = (RACINE / "scripts" / "installation_supabase.sql").read_text(encoding="utf-8")
    assert "'RES-TEST', 'Dossier Pennylane de test', 'PENNY-TEST', true" in texte
    assert "RES-TEST" not in (RACINE / "scripts" / "donnees_test.sql").read_text(encoding="utf-8")
