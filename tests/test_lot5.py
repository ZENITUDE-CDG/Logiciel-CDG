"""Lot 5 : publication du compte de résultat, contrôle P1 branché, instantanés figés."""
import csv
import pathlib
from decimal import Decimal

import pytest

from zenitude.config import publication
from zenitude.config.versions import Depot, RefusAction

RACINE = pathlib.Path(__file__).parent
FIX = RACINE / "fixtures"
ECRITURES = FIX / "ecritures_synthetiques.csv"
EXERCICES = FIX / "exercices.csv"
MODELE = RACINE.parent / "config_modele" / "Zenitude_Configuration_modele.xlsx"
V1 = FIX / "config_complete_v1.xlsx"
V2 = FIX / "config_complete_v2.xlsx"


def _lignes():
    with open(ECRITURES, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _independant(dossier, debut, fin):
    """Calcul de contrôle, indépendant du moteur : CA par compte et charges de classe 6."""
    ca_heb = ca_serv = charges = Decimal("0")
    for e in _lignes():
        if e["dossier"] != dossier:
            continue
        d, k = Decimal(e["debit"] or 0), Decimal(e["credit"] or 0)
        if e["compte"] == "706":
            ca_heb += k - d
        elif e["compte"] == "708":
            ca_serv += k - d
        elif e["compte"][:1] == "6":
            charges += d - k
    return ca_heb, ca_serv, charges


def _applique(depot, classeur, auteur="alice"):
    vid = depot.deposer(classeur, auteur)
    depot.approuver(vid, "bob")
    depot.appliquer(vid, "bob")
    return vid


@pytest.fixture
def depot(tmp_path):
    return Depot(str(tmp_path / "store"))


def test_publication_resultat_egal_au_calcul_independant(depot):
    _applique(depot, V1)
    pid, inst = publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")
    ca_heb, ca_serv, charges = _independant("PENNY-1001", None, None)
    r = inst["resultat"]
    assert Decimal(r["CA_HEBERGEMENT"]) == ca_heb.quantize(Decimal("0.01"))
    assert Decimal(r["CA_SERVICES"]) == ca_serv.quantize(Decimal("0.01"))
    assert Decimal(r["PL_CHARGES"]) == charges.quantize(Decimal("0.01"))
    assert Decimal(r["RESULTAT"]) == (ca_heb + ca_serv - charges).quantize(Decimal("0.01"))


def test_publication_refusee_sans_version_appliquee(depot):
    with pytest.raises(RefusAction):
        publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")


def test_p1_bloque_avec_le_modele_incomplet(depot):
    _applique(depot, MODELE)
    with pytest.raises(publication.PublicationBloquee) as e:
        publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")
    assert "6161" in e.value.non_classes and "606" in e.value.non_classes
    assert any(j["action"] == "publication refusée" for j in depot.statut()["journal"])


def test_exercice_court_sans_annualisation(depot):
    _applique(depot, V1)
    _, inst = publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1003", "carol")
    assert inst["exercice"]["duree_mois"] == 9
    ca_heb, _, _ = _independant("PENNY-1003", None, None)
    assert Decimal(inst["resultat"]["CA_HEBERGEMENT"]) == ca_heb.quantize(Decimal("0.01"))


def test_changement_de_version_bloque_puis_retour_restaure(depot):
    v1 = _applique(depot, V1)
    pid1, _ = publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")
    v2 = depot.deposer(V2, "alice")
    depot.approuver(v2, "bob")
    depot.appliquer(v2, "bob")
    # Sous v2, le compte 625 n'est plus classé : la publication est refusée
    with pytest.raises(publication.PublicationBloquee) as e:
        publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")
    assert "625" in e.value.non_classes
    # La publication antérieure reste intacte et reproductible
    assert publication.verifier_instantane(depot, pid1)
    depot.revenir(v1, "bob")
    pid2, inst2 = publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")
    assert inst2["version_config"] == v1


def test_instantane_detecte_une_modification(depot):
    _applique(depot, V1)
    pid, _ = publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1001", "carol")
    assert publication.verifier_instantane(depot, pid)
    import os
    chemin = os.path.join(depot.dossier, "publications", f"{pid}.json")
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(" ")
    assert not publication.verifier_instantane(depot, pid)


def test_version_et_donnees_enregistrees(depot):
    v1 = _applique(depot, V1)
    _, inst = publication.publier(depot, ECRITURES, EXERCICES, "PENNY-1002", "carol")
    assert inst["version_config"] == v1
    assert len(inst["empreinte_donnees"]) == 64
    assert inst["rubriques_utilisees"]
