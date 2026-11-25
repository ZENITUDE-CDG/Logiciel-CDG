"""Lot 22 (décision 0016) : période d'import = exercice N-1 complet + exercice N jusqu'à sa fin (écritures anticipées
comprises), calculée par dossier d'après ses exercices Pennylane. Données fictives, faux serveur Pennylane."""
import copy
import pathlib
import sys
from datetime import date

import pytest

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE / "interface"))
import publier_supabase as pub  # noqa: E402
from test_lot18_connecteur import ENTREES, LIGNES, LETTRAGE, FauxPennylane, _ligne  # noqa: E402,F401
from zenitude.connecteurs import pennylane as pl  # noqa: E402


def ex(*couples):
    return [(date.fromisoformat(a), date.fromisoformat(b)) for a, b in couples]


def test_regle_exercices_civils_decales_et_premier_exercice():
    civils = ex(("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31"), ("2026-01-01", "2026-12-31"))
    p, e = pl.periode_regle(civils, date(2026, 11, 25))
    assert p == (date(2025, 1, 1), date(2026, 12, 31)) and e == {"N-1": ["2025-01-01", "2025-12-31"], "N": ["2026-01-01", "2026-12-31"]}
    decales = ex(("2024-10-01", "2025-09-30"), ("2025-10-01", "2026-09-30"), ("2026-10-01", "2027-09-30"))
    assert pl.periode_regle(decales, date(2026, 11, 25))[0] == (date(2025, 10, 1), date(2027, 9, 30))
    # Exercice de neuf mois avant N : repris tel quel (jamais supposé de douze mois)
    court = ex(("2025-04-01", "2025-12-31"), ("2026-01-01", "2026-12-31"))
    assert pl.periode_regle(court, date(2026, 6, 1))[0] == (date(2025, 4, 1), date(2026, 12, 31))
    # Premier exercice du dossier : N seul
    p, e = pl.periode_regle(ex(("2026-01-01", "2026-12-31")), date(2026, 11, 25))
    assert p == (date(2026, 1, 1), date(2026, 12, 31)) and e["N-1"] is None
    # Exercice N pas encore ouvert dans Pennylane : le plus récent commencé fait office de N
    assert pl.periode_regle(civils, date(2027, 2, 1))[0] == (date(2025, 1, 1), date(2026, 12, 31))


def serveur():
    s = FauxPennylane()
    d = s.donnees
    d["/fiscal_years"] = [{"id": 0, "start": "2024-01-01", "finish": "2024-12-31", "status": "closed"}] + d["/fiscal_years"]
    # Une écriture de N-2 (hors période) et une écriture passée d'avance en décembre 2026 (anticipée)
    d["/ledger_entries"] = copy.deepcopy(d["/ledger_entries"]) + [
        {"id": 7, "date": "2024-06-01", "piece_number": "F-OLD", "label": "N-2 fictive", "status": "validated", "journal_id": 1},
        {"id": 8, "date": "2026-12-15", "piece_number": "F-AV", "label": "Abonnement fictif d'avance", "status": "validated", "journal_id": 1}]
    d["/ledger_entry_lines"] = copy.deepcopy(d["/ledger_entry_lines"]) + [
        _ligne(71, 7, "2024-06-01", 1, "6064000", debit="5.00"), _ligne(72, 7, "2024-06-01", 1, "4010001", credit="5.00"),
        _ligne(81, 8, "2026-12-15", 1, "6132000", debit="30.00"), _ligne(82, 8, "2026-12-15", 1, "4010001", credit="30.00")]
    return s


def lire(s, **kw):
    c = pl.Client("jeton-fictif", ouvrir=s, dormir=lambda x: None)
    return pl.extraire(c, "PENNY-TEST", "tous", aujourdhui=date(2026, 11, 25), **kw)


def test_extraction_avec_la_regle():
    lignes, _, r = lire(serveur(), regle=pl.REGLE_N1_N)
    assert r["regle"] == "n1_n" and r["periode"] == ["2025-01-01", "2026-12-31"]
    assert r["exercices_importes"] == {"N-1": ["2025-01-01", "2025-12-31"], "N": ["2026-01-01", "2026-12-31"]}
    dates = {x["date"] for x in lignes}
    assert "2025-03-01" in dates and "2026-12-15" in dates and "2024-06-01" not in dates  # N-1 oui, N-2 non
    assert r["anticipees"] == {"lignes": 2, "mois": ["2026-12"]}
    texte = pl.texte_rapport(r)
    assert "exercice N-1 2025-01-01 au 2025-12-31" in texte and "Écritures anticipées" in texte
    assert "30.00" not in texte  # aucun montant dans les journaux
    with pytest.raises(pl.ErreurPennylane):
        lire(serveur(), regle="autre")


def test_periode_explicite_prime_sur_la_regle():
    _, _, r = lire(serveur(), regle=pl.REGLE_N1_N, periode=(date(2026, 3, 1), date(2026, 3, 31)))
    assert r["periode"] == ["2026-03-01", "2026-03-31"] and "regle" not in r


def test_nouvel_exercice_relecture_complete():
    """Lecture par modifications refusée si la période de la règle dépasse celle déjà lue (exercice suivant ouvert)."""
    s = serveur()
    magasin = {"lignes": {}, "entrees": {}, "bornes": ["2025-01-01", "2025-12-31"], "taille_page": 100,
               "increment_depuis": "2026-11-20T00:00:00Z"}
    _, _, r = lire(s, regle=pl.REGLE_N1_N, magasin=magasin)
    assert "nouvel exercice" in r.get("lecture_motif", "")


def test_magasin_prepare_avec_les_bornes_deja_lues():
    """Sans période explicite, la règle n'empêche pas la lecture par modifications (lot 18d)."""
    from datetime import datetime, timezone
    m = {"bornes": ["2025-01-01", "2026-12-31"], "derniere_lecture": "2026-11-24T10:00:00+00:00",
         "derniere_complete": "2026-11-23T10:00:00+00:00", "lignes": {}, "entrees": {}}
    prep = pub.preparer_magasin(m, date(2025, 1, 1), date(2026, 12, 31), datetime(2026, 11, 25, tzinfo=timezone.utc))
    assert prep.get("increment_depuis")


def test_resultat_et_source_publies():
    r = {"lignes_reprises": 10, "lignes_lues": 12, "brouillard": None, "periode": ["2025-01-01", "2026-12-31"], "mode": "tous",
         "anticipees": {"lignes": 2, "mois": ["2026-12"]}}
    out = pub._resultat_demande({"dossiers": ["PENNY-TEST"]}, {"PENNY-TEST": {}}, (None, None, r))
    assert out["PENNY-TEST"]["anticipees"] == 2 and out["PENNY-TEST"]["periode"] == ["2025-01-01", "2026-12-31"]
