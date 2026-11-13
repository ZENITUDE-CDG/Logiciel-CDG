"""Lot 3 : écritures synthétiques PCG, équilibre, exercices et contrôle P1 (comptes non classés)."""
import csv
import pathlib

from zenitude.config import couverture

RACINE = pathlib.Path(__file__).parent
FIX = RACINE / "fixtures"
MODELE = RACINE.parent / "config_modele" / "Zenitude_Configuration_modele.xlsx"
PCG = RACINE.parent / "config_modele" / "pcg_reference.csv"

ECRITURES = couverture.charger_ecritures(FIX / "ecritures_synthetiques.csv")
EXERCICES = couverture.charger_exercices(FIX / "exercices.csv")
RUBRIQUES = couverture.charger_rubriques(MODELE)


def _pcg():
    with open(PCG, encoding="utf-8") as f:
        return {r["compte"]: r for r in csv.DictReader(
            (l for l in f if not l.startswith("#")), delimiter=";")}


def _somme(lignes, champ):
    return sum(float(l[champ]) for l in lignes if l[champ])


def test_chaque_dossier_est_equilibre():
    for dossier in EXERCICES:
        lignes = [e for e in ECRITURES if e["dossier"] == dossier]
        assert round(_somme(lignes, "debit"), 2) == round(_somme(lignes, "credit"), 2), dossier


def test_tous_les_comptes_sont_au_pcg():
    pcg = _pcg()
    inconnus = {e["compte"] for e in ECRITURES} - set(pcg)
    assert not inconnus, f"comptes hors référentiel PCG : {sorted(inconnus)}"


def test_dates_dans_l_exercice():
    for e in ECRITURES:
        debut, fin = EXERCICES[e["dossier"]]
        d = e["date"]
        assert debut.isoformat() <= d <= fin.isoformat(), (e["dossier"], d)


def test_exercice_court_de_neuf_mois():
    debut, fin = EXERCICES["PENNY-1003"]
    duree = (fin.year - debut.year) * 12 + fin.month - debut.month + 1
    assert duree == 9


def test_comptes_de_bilan_limites_aux_tiers_et_banque():
    bilan = {e["compte"] for e in ECRITURES if e["compte"][:1] in ("1", "2", "3", "4", "5")}
    assert bilan <= {"401", "411", "512"}


def test_p1_detecte_6161_non_classe_sur_1001():
    # Dans le modèle, ASSUR exclut 6161 et seul PENNY-1002 a une règle dédiée : 6161 reste non classé sur 1001
    non = couverture.comptes_non_classes(RUBRIQUES, "PENNY-1001", *EXERCICES["PENNY-1001"], ECRITURES)
    assert "6161" in non
    assert "606" in non and "708" in non


def test_p1_616_et_706_sont_classes_sur_1001():
    non = couverture.comptes_non_classes(RUBRIQUES, "PENNY-1001", *EXERCICES["PENNY-1001"], ECRITURES)
    assert "616" not in non and "706" not in non


def test_p1_6161_classe_sur_1002_par_regle_dediee():
    non = couverture.comptes_non_classes(RUBRIQUES, "PENNY-1002", *EXERCICES["PENNY-1002"], ECRITURES)
    assert "6161" not in non


def test_generation_reproductible(tmp_path):
    import importlib.util, hashlib
    spec = importlib.util.spec_from_file_location("gen", RACINE / "generer_ecritures.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.main(str(tmp_path))
    a = hashlib.sha256((tmp_path / "ecritures_synthetiques.csv").read_bytes()).hexdigest()
    b = hashlib.sha256((FIX / "ecritures_synthetiques.csv").read_bytes()).hexdigest()
    assert a == b
