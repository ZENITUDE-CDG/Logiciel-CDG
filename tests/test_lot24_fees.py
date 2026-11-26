"""Lot 24 - référence Python du CA par résidence et des FEES à refacturer (zenitude/comptabilite/fees.py)."""
import pathlib

from zenitude.comptabilite import fees as f

RACINE = pathlib.Path(__file__).parent.parent
RUB = [dict(r, actif=True) for r in f.RUBRIQUES_DEPART]


def test_exemple_du_tableau_du_siege():
    """Aix Le Tholonet, janvier : CA 95 701,44 € ; management fees 8 % puis 40/20/20/15/5 %."""
    R = f.calculer(RUB, f.REGLES_DEPART, 9570144, "AIX", "2026-01")
    m = {l["code"]: l["montant"] for l in R["lignes"]}
    assert m["MGT_FEES"] == 765612 and m["COMPTA"] == 306245 and m["COMMUNICATION"] == 153122
    assert m["COMMERCIAL"] == 153122 and m["GERANCE"] == 114842 and m["SUIVI_EXPLOITATION"] == 38281
    assert m["DROIT_MARQUE"] is None and R["lignes"][0]["motif"] == "non paramétré"  # jamais zéro
    assert R["total"] == 765612  # les répartitions ne s'ajoutent pas au total


def test_arrondi_demi_centime_loin_de_zero():
    assert f.appliquer_taux(5, 10) == 1 and f.appliquer_taux(-5, 10) == -1 and f.appliquer_taux(4, 10) == 0
    assert f.appliquer_taux(100000, "33.3333") == 33333


def test_versions_datees_et_priorite_de_la_residence():
    regles = f.REGLES_DEPART + [
        {"rubrique": "MGT_FEES", "dossier": "*", "mois_effet": "2026-06", "mode": "taux", "valeur": "9"},
        {"rubrique": "MGT_FEES", "dossier": "R1", "mois_effet": "2026-03", "mode": "taux", "valeur": "6"},
        {"rubrique": "MGT_FEES", "dossier": "R1", "mois_effet": "2026-09", "mode": "groupe", "valeur": None},
        {"rubrique": "DROIT_MARQUE", "dossier": "R1", "mois_effet": "2026-01", "mode": "montant", "valeur": "1200.50"}]
    taux = lambda d, m: f.regle_applicable(regles, "MGT_FEES", d, m)["valeur"]  # noqa: E731
    assert taux("R1", "2026-02") == "8" and taux("R1", "2026-03") == "6" and taux("R1", "2026-08") == "6"
    assert taux("R1", "2026-09") == "9"  # retour au groupe
    assert taux("R2", "2026-05") == "8" and taux("R2", "2026-06") == "9"
    assert f.regle_applicable(regles, "MGT_FEES", "R2", "2024-12") is None  # avant toute version
    R = f.calculer(RUB, regles, 1000000, "R1", "2026-04")
    m = {l["code"]: l for l in R["lignes"]}
    assert m["DROIT_MARQUE"]["montant"] == 120050 and m["MGT_FEES"]["montant"] == 60000 and m["COMPTA"]["montant"] == 24000
    assert R["total"] == 180050 and m["MGT_FEES"]["dossier_regle"] == "R1" and m["COMPTA"]["dossier_regle"] == "*"


def test_regle_de_ca_et_mois_sans_ecriture():
    compta = {"2026-01": {"706100": "1000.00", "708": "50.00", "791": "20.00", "601": "-300.00"}}
    assert f.ca_mois(compta, "2026-01", f.regle_ca([], "R1")) == 107000  # tous les comptes 7 par défaut
    regles = [{"dossier": "*", "inclus": ["7"], "exclus": ["79"]}, {"dossier": "R2", "inclus": ["706"], "exclus": []}]
    assert f.ca_mois(compta, "2026-01", f.regle_ca(regles, "R1")) == 105000
    assert f.ca_mois(compta, "2026-01", f.regle_ca(regles, "R2")) == 100000
    assert f.ca_mois(compta, "2026-02", f.regle_ca(regles, "R1")) is None
    R = f.calculer(RUB, f.REGLES_DEPART, None, "R1", "2026-02")
    assert all(l["montant"] is None for l in R["lignes"]) and R["total"] == 0
    assert {l["code"]: l["motif"] for l in R["lignes"]}["COMPTA"] == "base non calculable"


def test_rubrique_desactivee_et_instantane():
    rub = RUB + [{"code": "FORMATION", "libelle": "Formation", "base": "CA", "base_rubrique": None, "ordre": 80, "actif": False}]
    regles = f.REGLES_DEPART + [{"rubrique": "FORMATION", "dossier": "*", "mois_effet": "2025-01", "mode": "montant", "valeur": "500"}]
    I = f.instantane(rub, regles, [], {"2026-01": {"706": "1000.00"}}, "R1", "2026-01")
    assert "FORMATION" not in [l["code"] for l in I["lignes"]] and I["total"] == 8000 and I["regle_ca"] == {"inclus": ["7"], "exclus": []}


def test_amorce_de_la_migration_a_jour():
    texte = (RACINE / "migrations" / "015_comptabilite_et_tresorerie_previsionnelle.sql").read_text(encoding="utf-8")
    debut = "-- >>> amorce générée par zenitude/comptabilite/fees.py (ne pas modifier à la main)\n"
    bloc = texte[texte.index(debut) + len(debut):texte.index("-- <<< fin de l'amorce")]
    assert bloc == f.sql_amorce()
