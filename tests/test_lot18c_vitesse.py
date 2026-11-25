"""Lot 18c : vitesse de la synchronisation (sans réseau, faux serveur Pennylane du lot 18).

Pages de 1 000 éléments avec repli sur 100, filtre de dates demandé à Pennylane avec repli sur le filtrage
local, lectures parallèles sous la même limite de débit, lettrage mémorisé (réutilisé, redemandé si la
ligne a changé ou si le relevé a plus de 7 jours), mémoire du lettrage dans la base.
"""
import pathlib
import sys
import threading
from datetime import date, datetime, timedelta, timezone

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE))
import publier_supabase as pub  # noqa: E402
from test_lot18_connecteur import AUJOURDHUI, FauxPennylane  # noqa: E402
from zenitude.connecteurs import pennylane as pl  # noqa: E402

PERIODE = (date(2026, 3, 1), date(2026, 3, 31))


def lire(serveur, periode=PERIODE, memo=None, mode="tous"):
    c = pl.Client("jeton-fictif", ouvrir=serveur, dormir=lambda s: None)
    return pl.extraire(c, "PENNY-TEST", mode, depuis=date(2025, 10, 1), aujourdhui=AUJOURDHUI, periode=periode,
                       lettrage_memo=memo), c


def appels(serveur, mot):
    return [u for u in serveur.appels if mot in u]


def test_grandes_pages_et_filtre_a_la_source():
    s = FauxPennylane()
    (lignes, _, r), _ = lire(s)
    assert r["lecture"] == {"mode": "complète", "taille_page": 1000, "filtre_dates": True}
    assert all("limit=1000" in u and "filter=" in u for u in appels(s, "/ledger_entry_lines?"))
    assert r["lignes_lues"] == 4 and r["lignes_hors_periode"] == 0  # Pennylane n'a renvoyé que mars
    assert {l["date"][:7] for l in lignes} == {"2026-03"}


def test_repli_sur_les_pages_de_100():
    s = FauxPennylane(refuse_grand=True)
    (lignes, _, r), _ = lire(s)
    assert r["lecture"]["taille_page"] == 100 and len(lignes) == 4


def test_repli_sans_filtre_meme_resultat():
    (attendu, _, _), _ = lire(FauxPennylane())
    s = FauxPennylane(refuse_filtre=True)
    (lignes, _, r), _ = lire(s)
    assert r["lecture"]["filtre_dates"] is False and r["lignes_hors_periode"] == 6
    assert lignes == attendu


def test_lettrage_memorise():
    s1 = FauxPennylane()
    (l1, _, r1), _ = lire(s1, periode=None)
    memo = r1["_lettrage_a_memoriser"]
    assert r1["lettrage"]["demandees"] == len(memo) == 4 and len(appels(s1, "lettered")) >= 2
    maintenant = datetime.now(timezone.utc).isoformat()
    memoire = {i: dict(v, lu_le=maintenant) for i, v in memo.items()}
    s2 = FauxPennylane()
    (l2, _, r2), _ = lire(s2, periode=None, memo=memoire)
    assert appels(s2, "lettered") == [] and r2["lettrage"]["depuis_memoire"] == 4
    assert [x["lettrage"] for x in l2] == [x["lettrage"] for x in l1]
    assert "mémoire" in pl.texte_rapport(r2)
    # Ligne modifiée depuis le relevé, ou relevé trop ancien : redemandée
    memoire[12] = dict(memoire[12], maj="autre")
    memoire[22] = dict(memoire[22], lu_le=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    s3 = FauxPennylane()
    (_, _, r3), _ = lire(s3, periode=None, memo=memoire)
    assert r3["lettrage"]["demandees"] == 2 and r3["lettrage"]["depuis_memoire"] == 2


def test_limite_de_debit_partagee_entre_lectures_paralleles():
    temps, verrou, attentes = [0.0], threading.Lock(), []

    def horloge():
        with verrou:
            return temps[0]

    def dormir(sec):
        with verrou:
            attentes.append(sec)
            temps[0] += sec

    c = pl.Client("jeton-fictif", ouvrir=lambda u, h: (200, {}, "{}"), dormir=dormir, horloge=horloge)
    fils = [threading.Thread(target=lambda: [c.get("/journals") for _ in range(20)]) for _ in range(5)]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert c.requetes == 100 and len(attentes) >= 3


class BaseMemoire:
    """Fausse base : table lettrages_pennylane lue par pages de 1 000, écrite par paquets."""

    def __init__(self, lignes=0):
        self.lignes = [{"ligne_id": i, "maj": "x", "groupe": "", "lu_le": "2026-11-24T10:00:00+00:00"} for i in range(lignes)]
        self.ecrits = []

    def __call__(self, methode, url, cle, corps=None, prefer=None):
        chemin = url.split("/rest/v1/")[1]
        if methode == "GET":
            assert "dossier=eq.PENNY-TEST" in chemin
            off = int(chemin.split("offset=")[1].split("&")[0])
            return self.lignes[off:off + 1000]
        self.ecrits.append((chemin, corps))


def test_memoire_du_lettrage_dans_la_base():
    b = BaseMemoire(2500)
    memo = pub.lire_memo_lettrage("https://x.supabase.co", "sb_secret_FICTIF", "PENNY-TEST", envoyer=b)
    assert len(memo) == 2500 and memo[1]["groupe"] == ""
    a_ecrire = {i: {"maj": "m", "groupe": "L1"} for i in range(1200)}
    pub.ecrire_memo_lettrage("https://x.supabase.co", "sb_secret_FICTIF", "PENNY-TEST", a_ecrire, envoyer=b)
    assert [len(c) for _, c in b.ecrits] == [1000, 200]
    assert all("on_conflict=dossier,ligne_id" in ch for ch, _ in b.ecrits)
    assert b.ecrits[0][1][0] == {"dossier": "PENNY-TEST", "ligne_id": 0, "maj": "m", "groupe": "L1"}
