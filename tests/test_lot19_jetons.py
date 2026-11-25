"""Lot 19 (décision 0013) : jetons Pennylane chiffrés, un par dossier. Données et jetons fictifs.

- chiffrement / déchiffrement (même format que la page), empreinte de clé ;
- test d'un jeton : lecture seule, droits d'écriture refusés (jeton effacé), société d'une autre résidence,
  société différente de celle déjà rattachée, jeton refusé par Pennylane, expiration, droits non fournis ;
- demande « test » traitée par publier_supabase (base simulée), clé de GitHub différente de celle du logiciel ;
- jeton du logiciel utilisé pour le dossier de test ; dossiers réels connectés signalés « non lue ».
"""
import base64
import pathlib
import sys
from datetime import date

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "tests"))
import publier_supabase as pub  # noqa: E402
from test_lot18b_synchro import FausseBase  # noqa: E402
from zenitude.connecteurs import jetons  # noqa: E402
from zenitude.connecteurs import pennylane as pl  # noqa: E402

JETON = "fictif_jeton_pennylane_1234567890abcdWXYZ"


def paire():
    cp = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = cp.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    pub_b64 = base64.b64encode(cp.public_key().public_bytes(serialization.Encoding.DER,
                                                           serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    return jetons.charger_cle_privee(pem), pem, pub_b64


@pytest.fixture(scope="module")
def cle():
    return paire()


class FauxClient:
    """Réponse de /me choisie par le test ; erreur Pennylane si `erreur`."""

    def __init__(self, me=None, erreur=None):
        self.me, self.erreur, self.jetons = me, erreur, []

    def __call__(self, jeton):
        self.jetons.append(jeton)
        return self

    def get(self, chemin):
        assert chemin == "/me"  # aucune donnée comptable n'est lue pendant le test
        if self.erreur:
            raise pl.ErreurPennylane(self.erreur)
        return self.me


def me(sid=172916, nom="SAS FICTIVE ANNECY", scopes=("ledger:readonly", "journals:readonly")):
    out = {"user": {"id": 1, "email": "fictif@exemple.invalid"}, "company": {"id": sid, "name": nom, "reg_no": "fictif"}}
    if scopes is not None:
        out["scopes"] = list(scopes)
    return out


def connexion(cle, **kw):
    cp, _, pub_b64 = cle
    c = {"dossier": "D-1", "jeton_chiffre": jetons.chiffrer(JETON, pub_b64), "empreinte_cle": jetons.empreinte_spki_b64(pub_b64),
         "societe_attendue": None, "expire_le": "2027-11-25"}
    c.update(kw)
    return c


def test_chiffrement_aller_retour_et_empreinte(cle):
    cp, _, pub_b64 = cle
    c = jetons.chiffrer(JETON, pub_b64)
    assert c.startswith("v1.") and JETON not in c and len(c.split(".")) == 4
    assert jetons.dechiffrer(c, cp) == JETON
    assert jetons.empreinte_publique(cp) == jetons.empreinte_spki_b64(pub_b64)
    autre = paire()[0]
    with pytest.raises(jetons.ErreurCle):
        jetons.dechiffrer(c, autre)
    with pytest.raises(jetons.ErreurCle):
        jetons.dechiffrer("v0.abc", cp)
    with pytest.raises(jetons.ErreurCle):
        jetons.charger_cle_privee("pas une clé")


def test_jeton_en_lecture_seule_accepte(cle):
    f = FauxClient(me())
    r = jetons.tester(connexion(cle), cle[0], {}, client_de=f, aujourdhui=date(2026, 11, 25))
    assert r["etat"] == "connectee" and r["societe_attendue"] == "172916" and r["societe_nom"] == "SAS FICTIVE ANNECY"
    assert r["droits"] == ["ledger:readonly", "journals:readonly"] and r["motif"] is None
    assert f.jetons == [JETON]  # jeton déchiffré passé au client, jamais renvoyé
    assert JETON not in repr(r) and "jeton_chiffre" not in r


def test_droits_d_ecriture_refuses_et_jeton_efface(cle):
    r = jetons.tester(connexion(cle), cle[0], {}, client_de=FauxClient(me(scopes=["ledger:readonly", "customer_invoices:all"])))
    assert r["etat"] == "refusee" and "customer_invoices:all" in r["motif"] and "Lecture seule" in r["motif"]
    assert r["jeton_chiffre"] is None and r["fin_jeton"] is None


def test_societe_deja_rattachee_a_une_autre_residence(cle):
    r = jetons.tester(connexion(cle), cle[0], {"172916": "D-2"}, client_de=FauxClient(me()))
    assert r["etat"] == "refusee" and "D-2" in r["motif"] and r["jeton_chiffre"] is None


def test_societe_differente_de_celle_rattachee(cle):
    r = jetons.tester(connexion(cle, societe_attendue="999"), cle[0], {"999": "D-1"}, client_de=FauxClient(me()))
    assert r["etat"] == "refusee" and "n° 999" in r["motif"] and r["jeton_chiffre"] is None
    # Même société que celle rattachée : accepté (renouvellement du jeton)
    r = jetons.tester(connexion(cle, societe_attendue="172916"), cle[0], {"172916": "D-1"}, client_de=FauxClient(me()))
    assert r["etat"] == "connectee"


def test_jeton_refuse_par_pennylane_et_panne(cle):
    r = jetons.tester(connexion(cle), cle[0], {}, client_de=FauxClient(erreur="jeton refusé (401) : jeton expiré"))
    assert r["etat"] == "refusee" and "expiré, supprimé ou mal copié" in r["motif"] and "jeton_chiffre" not in r
    r = jetons.tester(connexion(cle), cle[0], {}, client_de=FauxClient(erreur="réponse inattendue de Pennylane (code 500)"))
    assert r["etat"] == "erreur"


def test_expiration_droits_absents_et_cle_differente(cle):
    r = jetons.tester(connexion(cle, expire_le="2026-01-31"), cle[0], {}, client_de=FauxClient(me()), aujourdhui=date(2026, 11, 25))
    assert r["etat"] == "a_renouveler"
    r = jetons.tester(connexion(cle), cle[0], {}, client_de=FauxClient(me(scopes=None)))
    assert r["etat"] == "connectee" and "Lecture seule" in r["motif"]
    r = jetons.tester(connexion(cle, empreinte_cle="0" * 64), cle[0], {}, client_de=FauxClient(me()))
    assert r["etat"] == "refusee" and "autre clé" in r["motif"]
    assert jetons.tester({"dossier": "D-1"}, cle[0], {})["etat"] == "erreur"


def test_lecture_seule():
    assert jetons.lecture_seule(["a:readonly", "b:readonly"])
    assert not jetons.lecture_seule(["a:readonly", "b:all"]) and not jetons.lecture_seule([])
    assert jetons._scopes({"scopes": "a:readonly, b:readonly"}) == ["a:readonly", "b:readonly"]
    assert jetons._scopes({"token": {"scopes": ["x:readonly"]}}) == ["x:readonly"]
    assert jetons._scopes({"company": {}}) is None


@pytest.fixture
def env(monkeypatch, cle):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_FICTIF")
    monkeypatch.setenv("SUPABASE_URL", "https://fictif.supabase.co")
    monkeypatch.setenv("PENNYLANE_CLE_PRIVEE", cle[1])
    monkeypatch.delenv("PENNYLANE_TOKEN_PILOTE", raising=False)


def demande_test(dossiers):
    return {"id": 9, "type": "test", "statut": "demandée", "dossiers": dossiers, "perimetre": "Groupe", "resultat": {}}


def test_demande_de_test_traitee(env, cle, monkeypatch):
    base = FausseBase(demande_test(["D-1", "D-2", "D-3"]))
    base.cles = [{"empreinte": jetons.empreinte_publique(cle[0])}]
    base.connexions = [connexion(cle), connexion(cle, dossier="D-2")]
    clients = {"n": 0}

    def client_de(jeton):
        clients["n"] += 1
        return FauxClient(me(sid=100 + clients["n"], nom=f"SOCIETE FICTIVE {clients['n']}"))(jeton)

    monkeypatch.setattr(pub, "requete", base)
    monkeypatch.setattr(pl, "Client", client_de)
    assert pub.main(["--demande", "9"]) == 0
    d = base.demandes[9]
    assert d["statut"] == "terminée"
    assert d["resultat"]["D-1"]["statut"] == "connectée" and d["resultat"]["D-2"]["statut"] == "connectée"
    assert d["resultat"]["D-3"] == {"statut": "non connectée", "motif": "aucun jeton enregistré"}
    assert [x[0] for x in base.maj_connexions] == ["D-1", "D-2"]
    assert base.maj_connexions[0][1]["societe_attendue"] == "101"
    assert not base.publie  # un test ne publie rien
    assert all(JETON not in repr(x) for x in base.historique)


def test_meme_societe_sur_deux_residences_de_la_demande(env, cle, monkeypatch):
    base = FausseBase(demande_test(["D-1", "D-2"]))
    base.cles = [{"empreinte": jetons.empreinte_publique(cle[0])}]
    base.connexions = [connexion(cle), connexion(cle, dossier="D-2")]
    monkeypatch.setattr(pub, "requete", base)
    monkeypatch.setattr(pl, "Client", FauxClient(me()))
    assert pub.main(["--demande", "9"]) == 0
    assert base.demandes[9]["resultat"]["D-1"]["statut"] == "connectée"
    assert base.demandes[9]["resultat"]["D-2"]["statut"] == "refusée"


def test_cle_de_github_differente(env, cle, monkeypatch):
    base = FausseBase(demande_test(["D-1"]))
    base.cles = [{"empreinte": "f" * 64}]
    monkeypatch.setattr(pub, "requete", base)
    assert pub.main(["--demande", "9"]) == 1
    assert base.demandes[9]["statut"] == "échec" and "ne correspond pas" in base.demandes[9]["message"]
    monkeypatch.delenv("PENNYLANE_CLE_PRIVEE")
    base = FausseBase(demande_test(["D-1"]))
    monkeypatch.setattr(pub, "requete", base)
    assert pub.main(["--demande", "9"]) == 1
    assert "PENNYLANE_CLE_PRIVEE absent" in base.demandes[9]["message"]


def test_jeton_du_logiciel_pour_le_dossier_de_test(env, cle):
    base = FausseBase()
    base.connexions = [connexion(cle, dossier="PENNY-TEST", etat="connectee")]
    assert pub.jeton_stocke("https://x", "k", "PENNY-TEST", envoyer=base) == JETON
    base.connexions = [connexion(cle, dossier="PENNY-TEST", etat="refusee")]
    assert pub.jeton_stocke("https://x", "k", "PENNY-TEST", envoyer=base) is None


def test_dossiers_reels_connectes_non_lus():
    r = pub._resultat_demande({"dossiers": ["D-9", "D-8"]}, {}, None, [{"dossier": "D-9", "etat": "connectee"}])
    assert r["D-9"]["statut"] == "non lue" and "décision 0013" in r["D-9"]["motif"]
    assert r["D-8"]["statut"] == "non connectée"
