"""Lot 7 : site de démonstration (index.html), généré par le moteur réel. Données fictives."""
import csv
import json
import pathlib
import re
import sys
from datetime import date
from decimal import Decimal

import pytest

from zenitude import kpi
from zenitude.config import controles
from zenitude.config.versions import Depot

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
import generer_demo  # noqa: E402
import generer_site  # noqa: E402


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("site")
    demo = dossier / "demo"
    generer_demo.main(str(demo))
    sortie = dossier / "index.html"
    generer_site.main(str(sortie), str(demo))
    texte = sortie.read_text(encoding="utf-8")
    m = re.search(r"var D = (\{.*?\});\n", texte, re.S)
    return demo, texte, json.loads(m.group(1).replace("<\\/", "</"))


def _depot(tmp_path, demo):
    d = Depot(str(tmp_path / "store"))
    vid = d.deposer(str(demo / "configuration.xlsx"), "alice")
    d.approuver(vid, "bob")
    d.appliquer(vid, "bob")
    return d


def test_configuration_de_demo_valide(site):
    demo, _, _ = site
    assert not controles.verifier(str(demo / "configuration.xlsx")).erreurs


def test_page_autonome_sans_formule_dans_le_navigateur(site):
    _, texte, donnees = site
    assert "/*__DONNEES__*/" not in texte
    assert "eval(" not in texte and "new Function" not in texte
    assert len(donnees["residences"]) == 8


def test_chiffres_du_site_egaux_au_moteur(site, tmp_path):
    demo, _, donnees = site
    d = _depot(tmp_path, demo)
    res = kpi.calculer_groupe(d, demo / "ecritures.csv", demo / "mesures.csv", "2026-10", "2026-10",
                              dossiers=[r["dossier"] for r in donnees["residences"]])
    affiche = donnees["resultats"]["GROUPE|2026-10"]
    for k in res["kpi"]:
        assert affiche[k["code"]]["valeur"] == k["valeur"], k["code"]


def test_donnee_absente_visible_sur_le_site(site):
    _, _, donnees = site
    to = donnees["resultats"]["DEMO-2002|2026-08"]["TO-SEN"]
    assert to["statut"] == "non calculable" and "août 2026" in to["motif"]
    assert donnees["resultats"]["GROUPE|2026-08"]["TO-SEN"]["statut"] == "non calculable"
    assert donnees["resultats"]["GROUPE|2026-08"]["REVPAR"]["statut"] == "calculé"


def test_compte_de_resultat_limite_a_l_exercice(site):
    # Les écritures de démonstration courent jusqu'à décembre 2026 : seules celles de l'exercice comptent
    demo, _, donnees = site
    f = next(x for x in donnees["finance"] if x["dossier"] == "DEMO-2003")
    ca = Decimal("0")
    with open(demo / "ecritures.csv", encoding="utf-8") as fh:
        for e in csv.DictReader(fh, delimiter=";"):
            if e["dossier"] == "DEMO-2003" and e["compte"] == "706" and \
                    date(2025, 10, 1) <= date.fromisoformat(e["date"]) <= date(2026, 9, 30):
                ca += Decimal(e["credit"] or 0) - Decimal(e["debit"] or 0)
    assert Decimal(f["resultat"]["CA_HEBERGEMENT"]) == ca.quantize(Decimal("0.01"))
