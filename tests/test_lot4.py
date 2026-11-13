"""Lot 4 : dépôt, approbation, application, retour arrière (V-1 à V-4 et règles de refus)."""
import hashlib
import json
import pathlib
import shutil

import pytest

from zenitude.config import publication
from zenitude.config.versions import Depot, RefusAction, RefusDepot

RACINE = pathlib.Path(__file__).parent
FIX = RACINE / "fixtures"
MODELE = RACINE.parent / "config_modele" / "Zenitude_Configuration_modele.xlsx"
COMPLETE_V1 = FIX / "config_complete_v1.xlsx"
COMPLETE_V2 = FIX / "config_complete_v2.xlsx"
DONNEES = FIX / "ecritures_synthetiques.csv"
EXERCICES = FIX / "exercices.csv"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


@pytest.fixture
def depot(tmp_path):
    return Depot(str(tmp_path / "store"))


def _statut(depot, vid):
    return next(v for v in depot.statut()["versions"] if v["id"] == vid)["statut"]


def test_depot_refuse_un_classeur_invalide(depot):
    with pytest.raises(RefusDepot):
        depot.deposer(FIX / "T-B13-a.xlsx", "auteur")


def test_depot_refuse_un_doublon(depot):
    depot.deposer(MODELE, "auteur")
    with pytest.raises(RefusDepot):
        depot.deposer(MODELE, "auteur")


def test_auteur_ne_peut_pas_approuver_sa_version(depot):
    vid = depot.deposer(MODELE, "alice")
    with pytest.raises(RefusAction):
        depot.approuver(vid, "alice")


def test_pas_d_application_sans_approbation(depot):
    vid = depot.deposer(MODELE, "alice")
    with pytest.raises(RefusAction):
        depot.appliquer(vid, "alice")


def test_approbation_unique_par_personne(depot):
    vid = depot.deposer(MODELE, "alice")
    depot.approuver(vid, "bob")
    with pytest.raises(RefusAction):
        depot.approuver(vid, "bob")


def test_application_puis_retour_arriere(depot, tmp_path):
    donnees_avant = sha(DONNEES)
    v1 = depot.deposer(COMPLETE_V1, "alice")
    depot.approuver(v1, "bob")
    depot.appliquer(v1, "bob")
    pid, _ = publication.publier(depot, DONNEES, EXERCICES, "PENNY-1001", "alice")
    v2 = depot.deposer(COMPLETE_V2, "alice")
    depot.approuver(v2, "bob")
    depot.appliquer(v2, "bob")
    assert depot.statut()["courante"] == v2
    assert _statut(depot, v1) == "remplacée"

    depot.revenir(v1, "bob")

    st = depot.statut()
    assert st["courante"] == v1
    assert _statut(depot, v2) == "remplacée"
    # V-1 : la publication garde la version utilisée à sa création
    pub = next(p for p in st["publications"] if p["id"] == pid)
    assert pub["version_config"] == v1
    assert publication.verifier_instantane(depot, pid)
    # V-2 : aucune donnée modifiée
    assert sha(DONNEES) == donnees_avant
    assert st["journal"][-1]["action"] == "retour arrière"


def test_retour_vers_version_courante_refuse(depot):
    v1 = depot.deposer(MODELE, "alice")
    depot.approuver(v1, "bob")
    depot.appliquer(v1, "bob")
    with pytest.raises(RefusAction):
        depot.revenir(v1, "bob")


def test_retour_vers_version_jamais_appliquee_refuse(depot):
    v1 = depot.deposer(MODELE, "alice")
    v2 = depot.deposer(FIX / "T-W5.xlsx", "alice")
    depot.approuver(v1, "bob")
    depot.appliquer(v1, "bob")
    with pytest.raises(RefusAction):
        depot.revenir(v2, "bob")


def test_publication_impossible_sans_version_appliquee(depot):
    depot.deposer(MODELE, "alice")
    with pytest.raises(RefusAction):
        publication.publier(depot, DONNEES, EXERCICES, "PENNY-1001", "alice")


def test_fichier_modifie_apres_depot_refuse_a_l_application(depot, tmp_path):
    v1 = depot.deposer(MODELE, "alice")
    depot.approuver(v1, "bob")
    copie = depot.fichiers + f"/{depot.statut()['versions'][0]['empreinte']}.xlsx"
    with open(copie, "ab") as f:
        f.write(b"x")
    with pytest.raises(RefusAction):
        depot.appliquer(v1, "bob")


def test_journal_trace_chaque_action(depot):
    v1 = depot.deposer(MODELE, "alice")
    depot.approuver(v1, "bob")
    depot.appliquer(v1, "bob")
    actions = [j["action"] for j in depot.statut()["journal"]]
    assert actions == ["dépôt", "approbation", "application"]
