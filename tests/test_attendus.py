"""Exécute les cas de tests/attendus.csv contre le validateur (lot 1)."""
import csv
import pathlib

import pytest

from zenitude.config import verifier

RACINE = pathlib.Path(__file__).parent
CAS = [c for c in csv.DictReader(open(RACINE / "attendus.csv", encoding="utf-8"), delimiter=";")
       if c["fichier"]]


@pytest.mark.parametrize("cas", CAS, ids=lambda c: c["identifiant"])
def test_cas(cas):
    rapport = verifier(RACINE / cas["fichier"])
    attendu = cas["attendu"]
    if attendu.startswith("REFUS:"):
        code = attendu.split(":")[1]
        assert code in rapport.codes_erreurs(), rapport.resume()
    elif attendu.startswith("ACCEPTE"):
        assert not rapport.erreurs, rapport.resume()
        if ":" in attendu:
            code = attendu.split(":")[1]
            assert code in rapport.codes_avertissements(), rapport.resume()
    else:
        pytest.fail(f"résultat attendu inconnu : {attendu}")
