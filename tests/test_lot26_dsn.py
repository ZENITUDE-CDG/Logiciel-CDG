"""Lot 26 - lecture DSN de référence (zenitude/social/dsn.py), sur des DSN fictives."""
import json
import pathlib
import sys

import pytest

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import generer_dsn  # noqa: E402
from zenitude.social import dsn  # noqa: E402

ENTETE = ["S10.G00.00.001,'X'", "S20.G00.05.001,'01'", "S20.G00.05.002,'01'", "S20.G00.05.003,'11'", "S20.G00.05.005,'01032026'",
          "S21.G00.06.001,'999002001'", "S21.G00.11.001,'00011'", "S21.G00.11.008,'2'"]


def salarie(debut, nature="01", q="151.67", fin=None, motif=None, arrets=(), brut="2000.00", sexe="02", naissance="01011990"):
    L = ["S21.G00.30.001,'2900199000001'", "S21.G00.30.002,'FICTIF'", f"S21.G00.30.005,'{sexe}'", f"S21.G00.30.006,'{naissance}'",
         f"S21.G00.40.001,'{debut}'", "S21.G00.40.003,'04'", f"S21.G00.40.007,'{nature}'", "S21.G00.40.008,'99'", "S21.G00.40.012,'151.67'"]
    if q is not None:
        L.append(f"S21.G00.40.013,'{q}'")
    for a in arrets:
        L += [f"S21.G00.60.{k},'{v}'" for k, v in a]
    if fin:
        L += [f"S21.G00.62.001,'{fin}'", f"S21.G00.62.002,'{motif}'"]
    L += ["S21.G00.50.001,'31032026'", "S21.G00.50.004,'1500.00'", "S21.G00.50.009,'45.10'",
          "S21.G00.51.011,'001'", f"S21.G00.51.013,'{brut}'", "S21.G00.51.011,'002'", "S21.G00.51.012,'151.67'", "S21.G00.51.013,'1.00'"]
    return L


def un(lignes):
    r = dsn.analyser("\r\n".join(ENTETE + lignes).encode("latin-1"))
    assert len(r["declarations"]) == 1
    return r["declarations"][0]


def test_totaux_d_une_declaration():
    d = un(salarie("01012020") + salarie("15032026", "02", q="75.84") + salarie("01062025", fin="20032026", motif="059"))
    c = d["contenu"]
    assert (d["siret"], d["mois"]) == ("99900200100011", "2026-03")
    assert c["effectif_fin"] == 2 and c["categories"]["CDI"] == 1 and c["categories"]["CDD"] == 1
    assert c["etp_milli"] == 1500  # 75,84 / 151,67 = 0,500 au millième
    assert c["entrees"]["CDD"] == 1 and c["sorties"]["DEMISSION"] == 1
    assert c["brut"] == 600000 and c["net_verse"] == 450000 and c["pas"] == 13530 and c["heures_payees"] == 45501
    assert c["alertes"] == []


def test_aucune_donnee_nominative_conservee():
    c = un(salarie("01012020"))["contenu"]
    texte = json.dumps(c)
    assert "FICTIF" not in texte and "2900199000001" not in texte and "01011990" not in texte and "1990" not in texte


def test_etp_non_calculable_sans_quotite():
    c = un(salarie("01012020", q=None))["contenu"]
    assert c["etp_incomplet"] == 1 and "ETP non calculable" in c["alertes"][0]


def test_refus_et_erreurs():
    for remplace, motif in [("S20.G00.05.001,'01'", "nature 02"), ("S20.G00.05.002,'01'", "annulation"), ("S20.G00.05.003,'11'", "fractionnée")]:
        valeur = {"nature 02": "S20.G00.05.001,'02'", "annulation": "S20.G00.05.002,'04'", "fractionnée": "S20.G00.05.003,'12'"}[motif]
        lignes = [valeur if x == remplace else x for x in ENTETE] + salarie("01012020")
        d = dsn.analyser("\n".join(lignes).encode())["declarations"][0]
        assert motif.split()[0] in d["refus"] and "contenu" not in d
    d = un(salarie("01012020", brut="12,50"))
    assert "montant illisible" in d["refus"]
    with pytest.raises(dsn.ErreurDSN, match="ligne 3"):
        dsn.analyser(b"S10.G00.00.001,'X'\nS20.G00.05.001,'01'\nBONJOUR\n")
    with pytest.raises(dsn.ErreurDSN, match="aucune déclaration"):
        dsn.analyser(b"S10.G00.00.001,'X'\n")


def test_arret_suivi_d_un_mois_a_l_autre():
    debut = [("001", "01"), ("002", "10022026"), ("003", "15042026")]
    fev = un(salarie("01012020", arrets=[debut]))["contenu"]
    avr = un(salarie("01012020", arrets=[debut + [("010", "06042026")]]))["contenu"]
    assert fev["arrets"][0]["cle"] == avr["arrets"][0]["cle"]
    contenus = {"2026-02": fev, "2026-03": {"arrets": []}, "2026-04": avr}
    assert dsn.jours_arret(contenus, "2026-02")["MALADIE"] == 18  # 11 au 28 février
    assert dsn.jours_arret(contenus, "2026-03")["MALADIE"] == 31  # mois sans déclaration de l'arrêt
    assert dsn.jours_arret(contenus, "2026-04")["MALADIE"] == 5  # reprise le 6 avril
    assert dsn.jours_arret(contenus, "2026-05") is None


def test_dsn_fictives_de_demonstration(tmp_path):
    fichiers = generer_dsn.generer(tmp_path)
    assert len(fichiers) == 13
    bruts = generer_dsn.bruts_641()
    vus = {}
    for f in fichiers:
        r = dsn.analyser(f.read_bytes())
        assert r["avertissements"] == []
        for x in r["declarations"]:
            vus[(x["siret"], x["mois"])] = x
    assert len(vus) == 13 * 8 - 1  # DEMO-2005, février 2026 manquant
    x = vus[(generer_dsn.siret("DEMO-2003"), "2026-06")]
    assert bruts[("DEMO-2003", "2026-06")] * 100 - x["contenu"]["brut"] == 123456
    assert vus[(generer_dsn.siret("DEMO-2008"), "2026-05")]["type"] == "03"
    assert vus[(generer_dsn.siret("DEMO-2007"), "2026-03")]["contenu"]["etp_incomplet"] == 1
    for f in fichiers:  # dépôt à jour
        assert f.read_bytes() == (RACINE / "interface" / "demo" / "dsn" / f.name).read_bytes()
