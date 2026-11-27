"""Lot 25 - socle de données pour Claude : référence Python (zenitude/socle/paquet.py).

Jeu synthétique minimal (fictif) pour chaque fichier et chaque contrôle, puis cohérence sur la démonstration :
balances équilibrées, CR de gestion = somme des mois, groupe = somme des résidences, ligne de commande.
"""
import csv
import io
import pathlib
import sys
import zipfile

import pytest

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE))
from zenitude import socle  # noqa: E402
from zenitude.socle import paquet as pq  # noqa: E402

MOIS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]
LIGNES = [
    {"code": "CA", "libelle": "Chiffre d'affaires", "niveau": 1, "sens": "produit", "regle": {"prefixes": ["7"]}},
    {"code": "CH", "libelle": "Charges", "niveau": 1, "sens": "charge", "regle": {"prefixes": ["6"]}},
    {"code": "EBITDA", "libelle": "EBITDA", "niveau": 0, "sens": "total", "regle": {"termes": [[1, "CA"], [-1, "CH"]]}},
]


def e(i, date, journal, piece, compte, libelle, montant_c, tiers="", lettrage="", echeance=""):
    return [f"{piece}-{i}", date, journal, piece, compte, libelle, montant_c, tiers, lettrage, echeance]


def jeu():
    """Deux résidences fictives. A : 6 mois couverts (2025-10 à 2026-03), B : 2025-10 seulement."""
    ea = [e(1, "2025-10-01", "AN", "AN1", "512", "Ouverture (fictif)", -100000), e(2, "2025-10-01", "AN", "AN1", "106", "Ouverture (fictif)", 100000)]
    n = 0
    for m in ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]:
        n += 1
        ea += [e(1, m + "-05", "VT", f"VT{n}", "411", "Séjours (fictif)", -120000, "CLI1", "L1"),
               e(2, m + "-05", "VT", f"VT{n}", "706", "Séjours (fictif)", 120000)]
        if m != "2026-02":  # paie manquante en février
            ea += [e(1, m + "-28", "OD", f"SAL{n}", "641", "Salaires (fictif)", -50000), e(2, m + "-28", "OD", f"SAL{n}", "421", "Salaires (fictif)", 50000)]
        if m != "2026-01":  # fournisseur récurrent absent en janvier
            ea += [e(1, m + "-10", "HA", f"EDF{n}", "401", "Énergie (fictif)", 10000 + n, "FOU-ENERGIE", "L2"),
                   e(2, m + "-10", "HA", f"EDF{n}", "6061", "Énergie (fictif)", -(10000 + n))]
    # doublon possible : même fournisseur, même montant, 2 jours d'écart
    ea += [e(1, "2026-03-12", "HA", "LIN1", "401", "Linge (fictif)", 33300, "FOU-LINGE"), e(2, "2026-03-12", "HA", "LIN1", "6135", "Linge (fictif)", -33300),
           e(1, "2026-03-14", "HA", "LIN2", "401", "Linge (fictif)", 33300, "FOU-LINGE"), e(2, "2026-03-14", "HA", "LIN2", "6135", "Linge (fictif)", -33300)]
    # paiement sans facture (fournisseur débiteur), client créditeur, 471 et 580 non soldés, taxe de séjour en CA
    ea += [e(1, "2026-03-20", "BQ", "BQ1", "401", "Acompte (fictif)", -7700, "FOU-ACOMPTE"), e(2, "2026-03-20", "BQ", "BQ1", "512", "Acompte (fictif)", 7700),
           e(1, "2026-03-21", "BQ", "BQ2", "512", "Avance client (fictif)", -2500), e(2, "2026-03-21", "BQ", "BQ2", "411", "Avance client (fictif)", 2500, "CLI2"),
           e(1, "2026-03-22", "BQ", "BQ3", "471", "Inconnu (fictif)", -999), e(2, "2026-03-22", "BQ", "BQ3", "512", "Inconnu (fictif)", 999),
           e(1, "2026-03-23", "BQ", "BQ4", "580", "Virement interne (fictif)", -5000), e(2, "2026-03-23", "BQ", "BQ4", "512", "Virement interne (fictif)", 5000),
           e(1, "2026-03-24", "VT", "TS1", "411", "Taxe de séjour mars (fictif)", -1500, "CLI1"), e(2, "2026-03-24", "VT", "TS1", "7088", "Taxe de séjour mars (fictif)", 1500)]
    eb = [e(1, "2025-10-05", "VT", "VB1", "411", "Loyers (fictif)", -30000, "CLI9"), e(2, "2025-10-05", "VT", "VB1", "706", "Loyers, avec virgule, et \"guillemets\" (fictif)", 30000)]
    ecritures = {"A": ea, "B": eb}
    compta = {}
    for d, ls in ecritures.items():
        for x in ls:
            if x[4][0] in "67":
                c = compta.setdefault(d, {}).setdefault(x[1][:7], {})
                c[x[4]] = c.get(x[4], 0) + x[6]
    compta = {d: {m: {c: pq.euros(v) for c, v in cs.items()} for m, cs in ms.items()} for d, ms in compta.items()}
    return {
        "meta": {"version_config": "v1", "dernier_mois_importe": "2026-03"},
        "residences": [{"dossier": "A", "code": "RA", "nom": "Résidence A (fictive)", "activite": "Hôtellerie", "region": "Nord",
                        "societe": "SAS A (fictive)", "marque": "M", "ouverture": "2020-01-01", "statut": "actif", "exercice": ["2025-10-01", "2026-09-30"]},
                       {"dossier": "B", "code": "RB", "nom": "Résidence B (fictive)", "activite": "Seniors", "region": "Sud",
                        "societe": "SAS B (fictive)", "marque": "", "ouverture": "", "statut": "actif", "exercice": None}],
        "perimetres": [{"id": "GROUPE", "libelle": "Groupe", "type": "groupe", "dossiers": ["A", "B"]},
                       {"id": "ACT-H", "libelle": "Activité Hôtellerie", "type": "activite", "dossiers": ["A"]},
                       {"id": "A", "libelle": "Résidence A (fictive)", "type": "residence", "dossiers": ["A"]}],
        "lignes_ebitda": LIGNES, "plan": [],
        "calcul": {"mois": MOIS, "compta": compta,
                   "couverts": {"A": ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"], "B": ["2025-10"]},
                   "exploitation": {"A": {"2025-10": {"LN_VENDUES": "310", "PRIX": "85.5"}}},
                   "libelles_comptes": {"401": "Fournisseurs", "512": "Banques", "706": "Prestations de services", "7088": "Autres produits"}},
        "ecritures": ecritures,
    }


def lire(texte):
    return list(csv.DictReader(io.StringIO(texte)))


@pytest.fixture(scope="module")
def paquet():
    return socle.construire(jeu(), ["B", "A"], "2025-10", "2026-03", complet=True, genere_le="G", auteur="A", perimetre="Groupe",
                            mission={"titre": "Test", "code": "TEST", "version": 3, "consignes": "Faire X.\n\n", "livrables": "Note_<dossier>.md"},
                            reference="PQ-000042")


def ctrl(paquet, code, dossier="A"):
    return [x for x in lire(paquet["controles.csv"]) if x["code"] == code and x["dossier"] == dossier]


def test_fichiers_et_colonnes(paquet):
    attendus = {f["nom"] for f in socle.FICHIERS} | {"LISEZ-MOI.md", "MISSION.md"}
    assert set(paquet) == attendus
    for f in socle.FICHIERS:
        if f["colonnes"]:
            assert paquet[f["nom"]].split("\n", 1)[0] == ",".join(f["colonnes"])
    synthese = socle.construire(jeu(), ["A"], "2025-10", "2026-03", complet=False)
    assert "ecritures.csv" not in synthese and "banque_mouvements.csv" not in synthese
    assert "groupe_cr_gestion.csv" not in synthese and "MISSION.md" not in synthese  # une seule résidence, sans mission


def test_lisez_moi_et_mission(paquet):
    t = paquet["LISEZ-MOI.md"]
    assert "Groupe (2 résidence(s))" in t and "2025-10 à 2026-03" in t and "N’interroge pas Pennylane" in t
    assert "{{" not in t and "| controles.csv |" in t
    assert "Référence du paquet : PQ-000042 ; empreinte des données : " in t
    emp = socle.empreinte([(k, v) for k, v in paquet.items() if k.endswith(".csv")])
    assert emp in t and len(emp) == 64
    m = paquet["MISSION.md"]
    assert m.startswith("# Mission : Test\n\n- Code : TEST ; version 3\n- Référence du paquet : PQ-000042 ; empreinte des données : " + emp)
    assert socle.ENTETE_MISSION in m and "## Consignes\n\nFaire X.\n" in m and m.endswith("## Livrables attendus\n\nNote_<dossier>.md\n")


def test_empreinte_change_avec_les_donnees():
    a = socle.construire(jeu(), ["A"], "2025-10", "2026-03")
    b = socle.construire(jeu(), ["A"], "2025-10", "2026-02")
    ea = a["LISEZ-MOI.md"].split("empreinte des données : ")[1][:64]
    eb = b["LISEZ-MOI.md"].split("empreinte des données : ")[1][:64]
    assert ea != eb and ea == socle.construire(jeu(), ["A"], "2025-10", "2026-03")["LISEZ-MOI.md"].split("empreinte des données : ")[1][:64]


def test_residences_et_csv_echappe(paquet):
    r = lire(paquet["residences.csv"])
    assert [x["dossier"] for x in r] == ["A", "B"]  # triées
    assert r[0]["groupes"] == "Activité Hôtellerie" and r[0]["mois_couverts_periode"] == "6" and r[1]["mois_couverts_periode"] == "1"
    assert r[1]["exercice_debut"] == "" and r[1]["dernier_mois_donnees"] == "2025-10"
    ecr = lire(paquet["ecritures.csv"])
    assert any(x["libelle"] == 'Loyers, avec virgule, et "guillemets" (fictif)' for x in ecr)


def test_cr_gestion_et_groupe(paquet):
    p = {(x["dossier"], x["ligne"]): x for x in lire(paquet["cr_gestion_periode.csv"])}
    assert p[("A", "CA")]["montant_periode"] == "7215.00"  # 6 × 1 200 + 15 de taxe de séjour (constatée, non retraitée)
    assert p[("A", "EBITDA")]["montant_n1"] == ""  # N-1 hors de la frise
    m = [x for x in lire(paquet["cr_gestion_mensuel.csv"]) if x["dossier"] == "A" and x["ligne"] == "CH"]
    assert sum(float(x["montant"]) for x in m) == pytest.approx(float(p[("A", "CH")]["montant_periode"]))
    g = {x["ligne"]: x for x in lire(paquet["groupe_cr_gestion.csv"])}
    assert float(g["CA"]["montant_periode"]) == pytest.approx(7215 + 300) and g["CA"]["nb_residences"] == "2"
    gr = lire(paquet["groupe_residences.csv"])
    assert list(gr[0].keys()) == ["dossier", "nom", "activite", "CA", "CH", "EBITDA", "nb_controles"]


def test_balances_tiers_banque(paquet):
    bm = [x for x in lire(paquet["balance_mensuelle.csv"]) if x["dossier"] == "A"]
    assert sum(float(x["debit"]) for x in bm) == pytest.approx(sum(float(x["credit"]) for x in bm))
    bf = {x["compte"]: x for x in lire(paquet["balance_fin.csv"]) if x["dossier"] == "A"}
    assert bf["512"]["solde_debiteur"] == "888.01"  # 1 000 − 77 + 25 − 9,99 − 50 and bf["401"]["libelle_compte"] == "Fournisseurs"
    ti = {(x["compte"], x["tiers"]): x for x in lire(paquet["tiers_soldes.csv"]) if x["dossier"] == "A"}
    assert ti[("401", "FOU-ACOMPTE")]["solde_debiteur"] == "77.00"
    assert ti[("401", "FOU-LINGE")]["non_lettre_solde_debiteur"] == "-666.00"
    bq = [x for x in lire(paquet["banque_mensuel.csv"]) if x["dossier"] == "A"]
    assert bq[0]["mois"] == "2025-10" and bq[0]["encaissements"] == "0.00"  # à-nouveau exclu des encaissements…
    assert bq[0]["solde_fin"] == "1000.00"  # … mais compris dans le solde
    mv = {x["piece"]: x for x in lire(paquet["banque_mouvements.csv"]) if x["dossier"] == "A"}
    assert mv["BQ1"]["montant"] == "-77.00" and mv["BQ1"]["contreparties"] == "401" and mv["BQ1"]["tiers"] == "FOU-ACOMPTE"


def test_fournisseurs_et_kpi(paquet):
    fo = [x for x in lire(paquet["fournisseurs_mensuel.csv"]) if x["tiers"] == "FOU-LINGE"]
    assert fo == [{"dossier": "A", "tiers": "FOU-LINGE", "mois": "2026-03", "charges": "666.00", "nb_pieces": "2", "comptes": "6135"}]
    assert not any(x["tiers"] == "FOU-ACOMPTE" for x in lire(paquet["fournisseurs_mensuel.csv"]))  # paiement : pas une charge
    k = lire(paquet["kpi_mensuel.csv"])
    assert [(x["donnee"], x["valeur"]) for x in k] == [("LN_VENDUES", "310"), ("PRIX", "85.5")]


def test_controles(paquet):
    assert [x["mois"] for x in ctrl(paquet, "C01", "B")] == ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]
    assert ctrl(paquet, "C01", "A") == [] and ctrl(paquet, "C02", "A") == []
    assert [x["mois"] for x in ctrl(paquet, "C03")] == ["2026-02"]
    c4 = ctrl(paquet, "C04")
    assert [(x["tiers"], x["mois"]) for x in c4] == [("FOU-ENERGIE", "2026-01")] and c4[0]["montant"] == "100.03"  # médiane basse de 5 mois
    assert "facturé 5 mois sur 6" in c4[0]["detail"]
    c5 = ctrl(paquet, "C05")
    assert len(c5) == 1 and c5[0]["tiers"] == "FOU-LINGE" and "LIN1" in c5[0]["detail"] and "LIN2" in c5[0]["detail"]
    assert [(x["tiers"], x["montant"]) for x in ctrl(paquet, "C06")] == [("FOU-ACOMPTE", "77.00")]
    assert [(x["tiers"], x["montant"]) for x in ctrl(paquet, "C07")] == [("CLI2", "-25.00")]
    assert [(x["compte"], x["montant"]) for x in ctrl(paquet, "C08")] == [("471", "9.99")]
    assert [(x["compte"], x["montant"]) for x in ctrl(paquet, "C09")] == [("580", "50.00")]
    assert [(x["compte"], x["mois"], x["montant"]) for x in ctrl(paquet, "C10")] == [("7088", "2026-03", "15.00")]


def test_periode_et_dossier_refuses():
    with pytest.raises(ValueError):
        socle.construire(jeu(), ["A"], "2030-01", "2030-02")
    with pytest.raises(ValueError):
        socle.construire(jeu(), ["Z"], "2025-10", "2026-03")


def test_demonstration_coherente():
    import generer_site
    d = generer_site.construire()
    per = next(p for p in d["perimetres"] if p["id"] == "GROUPE")
    f = socle.construire(d, per["dossiers"], "2025-10", "2026-09", complet=True)
    bm = lire(f["balance_mensuelle.csv"])
    for dos in per["dossiers"]:
        x = [r for r in bm if r["dossier"] == dos]
        assert round(sum(float(r["debit"]) for r in x), 2) == round(sum(float(r["credit"]) for r in x), 2)
    g = {x["ligne"]: float(x["montant_periode"]) for x in lire(f["groupe_cr_gestion.csv"]) if x["montant_periode"]}
    p = lire(f["cr_gestion_periode.csv"])
    for code in ("CA", "EBITDA", "RN"):
        assert g[code] == pytest.approx(sum(float(x["montant_periode"]) for x in p if x["ligne"] == code and x["montant_periode"]))
    assert len(lire(f["ecritures.csv"])) == sum(1 for dos in per["dossiers"] for r in d["ecritures"][dos] if "2025-10-01" <= r[1] <= "2026-09-30")
    assert "socle" in d and d["socle"]["controles"] == socle.CONTROLES  # définition publiée pour la page


def test_ligne_de_commande(tmp_path):
    from zenitude.socle.__main__ import main
    z = tmp_path / "p.zip"
    main(["paquet", "--perimetre", "DEMO-2001", "--du", "2025-10", "--au", "2026-09", "--synthese", "--sortie", str(z)])
    noms = zipfile.ZipFile(z).namelist()
    assert "LISEZ-MOI.md" in noms and "controles.csv" in noms and "ecritures.csv" not in noms
