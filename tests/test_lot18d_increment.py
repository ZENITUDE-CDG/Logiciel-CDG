"""Lot 18d : lecture par modifications (journal des modifications Pennylane) et tailles de page.

Sans réseau : faux serveur Pennylane avec journal des modifications, filtre par identifiants, balance et
groupes de lettrage portés par les lignes. Vérifie que la lecture par modifications donne exactement le même
résultat qu'une relecture complète, avec bien moins de requêtes, et qu'elle se replie sur une relecture
complète quand la balance de Pennylane ne concorde pas ou que le journal est indisponible.
"""
import copy
import json
import pathlib
import sys
import urllib.parse
from datetime import date
from decimal import Decimal

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE))
from test_lot18_connecteur import AUJOURDHUI, ENTREES, LIGNES, FauxPennylane, _ligne  # noqa: E402
from zenitude.connecteurs import pennylane as pl  # noqa: E402

DEPUIS = date(2025, 10, 1)


GROUPES = {12: [12, 61], 61: [12, 61]}


def avec_ids(l):
    l["lettered_ledger_entry_lines"] = {"ids": GROUPES.get(l["id"], []), "url": "x"}
    return l


class Serveur(FauxPennylane):
    """Ajoute : journal des modifications, filtre « id in », lecture unitaire, balance, ids de lettrage."""

    def __init__(self, entrees=ENTREES, lignes=LIGNES, journal_ecritures=True, taille_max=None, **kw):
        lignes = copy.deepcopy(lignes)
        for l in lignes:  # Pennylane donne le groupe de lettrage sur la ligne (ids)
            avec_ids(l)
        super().__init__(entrees=copy.deepcopy(entrees), lignes=lignes, **kw)
        self.evenements = {"/changelogs/ledger_entry_lines": [], "/changelogs/ledger_entries": []}
        self.journal_ecritures, self.taille_max = journal_ecritures, taille_max

    def modifier_ligne(self, ligne, op="update"):
        lignes = [l for l in self.donnees["/ledger_entry_lines"] if l["id"] != ligne["id"]]
        if op != "delete":
            lignes.append(avec_ids(ligne))
        self.donnees["/ledger_entry_lines"] = sorted(lignes, key=lambda x: x["id"])
        self.evenements["/changelogs/ledger_entry_lines"].append({"id": ligne["id"], "operation": op,
                                                                  "processed_at": "2026-11-25T10:00:00Z"})

    def __call__(self, url, entetes):
        parts = urllib.parse.urlsplit(url)
        chemin = parts.path.replace("/api/external/v2", "")
        q = dict(urllib.parse.parse_qsl(parts.query))
        self_appels = self.appels
        if self.taille_max and int(q.get("limit") or 0) > self.taille_max and not chemin.startswith(("/changelogs", "/trial")):
            self_appels.append(url)
            return 400, {}, "{}"
        if chemin.startswith("/changelogs/"):
            self_appels.append(url)
            if chemin == "/changelogs/ledger_entries" and not self.journal_ecritures:
                return 404, {}, "{}"
            assert ("start_date" in q) != ("cursor" in q)
            return 200, {}, json.dumps({"items": self.evenements[chemin], "has_more": False, "next_cursor": None})
        if chemin == "/trial_balance":
            self_appels.append(url)
            tot = {}
            for l in self.donnees["/ledger_entry_lines"]:
                if q["period_start"] <= l["date"] <= q["period_end"]:
                    n = l["ledger_account"]["number"]
                    d, c = tot.get(n, (Decimal(0), Decimal(0)))
                    tot[n] = (d + Decimal(l["debit"]), c + Decimal(l["credit"]))
            return 200, {}, json.dumps({"items": [{"number": n, "debits": str(d), "credits": str(c)} for n, (d, c) in tot.items()],
                                        "has_more": False, "next_cursor": None})
        morceaux = chemin.split("/")
        if len(morceaux) == 3 and morceaux[2].isdigit():  # lecture unitaire
            self_appels.append(url)
            x = [e for e in self.donnees["/" + morceaux[1]] if e["id"] == int(morceaux[2])]
            return (200, {}, json.dumps(x[0])) if x else (404, {}, "{}")
        if "filter" in q and json.loads(q["filter"])[0]["field"] == "id":
            self_appels.append(url)
            ids = set(json.loads(q["filter"])[0]["value"])
            return 200, {}, json.dumps({"items": [e for e in self.donnees[chemin] if e["id"] in ids], "has_more": False,
                                        "next_cursor": None})
        return super().__call__(url, entetes)


def lire(serveur, magasin=None, mode="tous", periode=None):
    c = pl.Client("jeton-fictif", ouvrir=serveur, dormir=lambda s: None)
    lignes, exo, r = pl.extraire(c, "PENNY-TEST", mode, depuis=DEPUIS, aujourdhui=AUJOURDHUI, periode=periode, magasin=magasin)
    return lignes, r, c


def magasin_de(r, depuis="2026-11-25T09:00:00+00:00"):
    m = r["_magasin_maj"]
    return {"lignes": dict(m["lignes"]), "entrees": dict(m["entrees"]), "bornes": m["bornes"],
            "taille_page": m["taille_page"], "increment_depuis": depuis}


def modifier(s):
    s.modifier_ligne(_ligne(11, 1, "2026-03-10", 1, "6064000", debit="120.00"))           # montant corrigé
    s.modifier_ligne(_ligne(12, 1, "2026-03-10", 1, "4010001", credit="120.00"))
    s.modifier_ligne(_ligne(81, 6, "2026-04-15", 3, "6226000", debit="5.00"))             # ligne ajoutée
    s.modifier_ligne(_ligne(82, 6, "2026-04-15", 3, "5120000", credit="5.00"))
    s.modifier_ligne({"id": 41}, op="delete")                                              # écriture PL4 supprimée
    s.modifier_ligne({"id": 42}, op="delete")
    s.donnees["/ledger_entries"] = [dict(e, status="complete") if e["id"] == 2 else e for e in s.donnees["/ledger_entries"]]
    s.evenements["/changelogs/ledger_entries"].append({"id": 2, "operation": "update"})


def test_lecture_par_modifications_identique_a_la_lecture_complete():
    s = Serveur()
    _, r1, _ = lire(s)
    assert r1["lecture"]["mode"] == "complète" and r1["lettrage"]["depuis_ligne"] >= 2 and r1["lettrage"]["demandees"] == 0
    modifier(s)
    avant = len(s.appels)
    lignes_inc, r2, c2 = lire(s, magasin_de(r1), mode="valides")
    requetes_inc = len(s.appels) - avant
    lignes_comp, r3, _ = lire(Serveur(entrees=s.donnees["/ledger_entries"], lignes=s.donnees["/ledger_entry_lines"]), mode="valides")
    assert lignes_inc == lignes_comp
    assert r2["lecture"]["mode"] == "modifications" and r2["controle_balance"] == "identique"
    assert r2["lecture"]["lignes_modifiees"] == 4 and r2["lecture"]["lignes_supprimees"] == 2
    assert r2["statuts"] == r3["statuts"] and r2["brouillard"] == r3["brouillard"]
    assert requetes_inc <= 10
    m = r2["_magasin_maj"]
    assert m["mode"] == "increment" and set(m["lignes"]) == {11, 12, 81, 82} and m["lignes_suppr"] == [41, 42]
    assert set(m["entrees"]) == {2}
    texte = pl.texte_rapport(r2)
    assert "par modifications" in texte and "120.00" not in texte


def test_balance_differente_relecture_complete():
    s = Serveur()
    _, r1, _ = lire(s)
    modifier(s)
    s.evenements["/changelogs/ledger_entry_lines"] = s.evenements["/changelogs/ledger_entry_lines"][1:]  # événement perdu
    lignes, r2, _ = lire(s, magasin_de(r1))
    assert r2["lecture"]["mode"] == "complète" and "balance différente" in r2["lecture_motif"]
    assert r2["controle_balance"].startswith("différente")
    lignes_comp, _, _ = lire(Serveur(entrees=s.donnees["/ledger_entries"], lignes=s.donnees["/ledger_entry_lines"]))
    assert lignes == lignes_comp and r2["_magasin_maj"]["mode"] == "complet"


def test_journal_des_ecritures_absent():
    s = Serveur(journal_ecritures=False)
    _, r1, _ = lire(s)
    modifier(s)
    lignes, r2, _ = lire(s, magasin_de(r1), mode="valides")
    assert r2["lecture"]["mode"] == "modifications" and r2["lecture"]["journal_ecritures"] is False
    lignes_comp, _, _ = lire(Serveur(entrees=s.donnees["/ledger_entries"], lignes=s.donnees["/ledger_entry_lines"]), mode="valides")
    assert lignes == lignes_comp


def test_journal_indisponible_relecture_complete():
    s = Serveur()
    _, r1, _ = lire(s)
    m = magasin_de(r1)
    s.evenements = {}  # le journal répond 4xx (KeyError évitée : endpoint inconnu)

    class Refus(Serveur):
        pass
    orig = s.__call__

    def appel(url, entetes):
        if "/changelogs/" in url:
            return 422, {}, "{}"
        return orig(url, entetes)
    c = pl.Client("jeton-fictif", ouvrir=appel, dormir=lambda x: None)
    _, _, r2 = pl.extraire(c, "PENNY-TEST", "tous", depuis=DEPUIS, aujourdhui=AUJOURDHUI, magasin=m)
    assert r2["lecture"]["mode"] == "complète" and "indisponible" in r2["lecture_motif"]


def test_taille_de_page_intermediaire_et_memorisee():
    s = Serveur(taille_max=250)
    _, r, _ = lire(s)
    assert r["lecture"]["taille_page"] == 250 and r["_magasin_maj"]["taille_page"] == 250
    refus = [u for u in s.appels if "limit=1000" in u or "limit=500" in u]
    assert refus
    s2 = Serveur(taille_max=250)
    m = {"taille_page": 250}
    _, r2, _ = lire(s2, m)
    assert not [u for u in s2.appels if ("limit=1000" in u or "limit=500" in u) and "trial_balance" not in u]
    assert r2["lecture"]["taille_page"] == 250


def test_lecture_par_identifiants_sans_filtre_in():
    s = Serveur()
    orig = s.__call__

    def appel(url, entetes):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if "filter" in q and json.loads(q["filter"])[0]["field"] == "id":
            return 400, {}, "{}"
        return orig(url, entetes)
    c = pl.Client("jeton-fictif", ouvrir=appel, dormir=lambda x: None)
    assert sorted(x["id"] for x in c.par_ids("/ledger_entry_lines", [11, 12, 999])) == [11, 12]


def test_evenements():
    maj, sup = pl._evenements([{"id": 1, "operation": "insert"}, {"id": 2, "operation": "update"},
                               {"id": 1, "operation": "delete"}, {"ledger_entry_line": {"id": 3}, "operation": "update"}],
                              "ledger_entry_line")
    assert maj == {2, 3} and sup == {1}


# ------------------------------------------------------------- conservation dans la base (publier_supabase)

from datetime import datetime, timedelta, timezone  # noqa: E402

sys.path.insert(0, str(RACINE / "interface"))
import publier_supabase as pub  # noqa: E402
import pytest  # noqa: E402
from test_lot18b_synchro import FausseBase  # noqa: E402

MAINTENANT = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def etat(lecture_h=1, complete_j=1, bornes=("2025-10-01", None)):
    return {"lignes": {}, "entrees": {}, "bornes": list(bornes), "taille_page": 100,
            "derniere_lecture": (MAINTENANT - timedelta(hours=lecture_h)).isoformat(),
            "derniere_complete": (MAINTENANT - timedelta(days=complete_j)).isoformat()}


def test_choix_lecture_par_modifications():
    m = pub.preparer_magasin(etat(), date(2025, 10, 1), None, MAINTENANT)
    assert m["increment_depuis"] == "2026-11-25T10:50:00Z"
    assert pub.preparer_magasin(None, None, None, MAINTENANT) is None
    cas = [(etat(complete_j=8), date(2025, 10, 1), None, "hebdomadaire"),
           (etat(lecture_h=28 * 24, complete_j=3), date(2025, 10, 1), None, "trop ancienne"),
           (etat(bornes=("2026-01-01", None)), date(2025, 10, 1), None, "plus large"),
           (etat(bornes=("2025-10-01", "2026-06-30")), date(2025, 10, 1), None, "plus large")]
    for m, bas, haut, motif in cas:
        r = pub.preparer_magasin(m, bas, haut, MAINTENANT)
        assert "increment_depuis" not in r and motif in r["motif"] and r["taille_page"] == 100
    # Période plus étroite que celle déjà lue : lecture par modifications
    assert "increment_depuis" in pub.preparer_magasin(etat(bornes=("2025-10-01", "2026-12-31")), date(2026, 1, 1),
                                                      date(2026, 6, 30), MAINTENANT)


class BaseMagasin(FausseBase):
    """Fausse base qui conserve vraiment pennylane_etat et pennylane_magasin."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.t = {"pennylane_magasin": {}, "pennylane_etat": {}}

    def __call__(self, methode, url, cle, corps=None, prefer=None):
        chemin = url.split("/rest/v1/")[1]
        table, _, q = chemin.partition("?")
        if table not in self.t:
            return super().__call__(methode, url, cle, corps, prefer)
        d = self.t[table]
        if methode == "GET":
            return [v for _, v in sorted(d.items())]
        if methode == "POST":
            for r in corps:
                d[(r["dossier"], r.get("morceau", 0))] = dict(r)
        elif methode == "DELETE":
            d.clear()
        elif methode == "PATCH":
            for v in d.values():
                v.update(corps)

    def lignes(self):
        import base64
        import zlib
        texte = "".join(v["donnees"] for _, v in sorted(self.t["pennylane_magasin"].items()))
        return json.loads(zlib.decompress(base64.b64decode(texte)))["lignes"]


def test_magasin_en_plusieurs_morceaux(monkeypatch):
    base = BaseMagasin()
    monkeypatch.setattr(pub, "TAILLE_MORCEAU", 200)
    lignes = {i: {"id": i, "date": "2026-01-01", "label": "x" * (i % 7)} for i in range(300)}
    n, _ = pub.ecrire_magasin("https://x", "k", "PENNY-TEST", {"mode": "complet", "toutes_lignes": lignes,
                                                               "toutes_entrees": {}, "bornes": ["2025-10-01", None],
                                                               "taille_page": 100}, "2026-11-25T10:00:00+00:00", envoyer=base)
    assert n > 1 and list(base.t["pennylane_etat"].values())[0]["morceaux"] == n
    m = pub.lire_magasin("https://x", "k", "PENNY-TEST", envoyer=base)
    assert m["lignes"] == lignes and m["derniere_complete"] == "2026-11-25T10:00:00+00:00"
    del base.t["pennylane_magasin"][("PENNY-TEST", 1)]  # morceau perdu : relecture complète
    assert pub.lire_magasin("https://x", "k", "PENNY-TEST", envoyer=base) is None


def test_deux_synchronisations_de_suite(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_FICTIF")
    monkeypatch.setenv("PENNYLANE_TOKEN_PILOTE", "jeton-fictif")
    monkeypatch.delenv("PENNYLANE_MODE", raising=False)
    monkeypatch.setattr(pub, "url_supabase", lambda: "https://exemple.supabase.co")
    serveur = Serveur()
    vrai = pub.lire_pennylane
    monkeypatch.setattr(pub, "lire_pennylane", lambda **kw: vrai(client=pl.Client("jeton-fictif", ouvrir=serveur, dormir=lambda s: None),
                                                                 **{k: v for k, v in kw.items() if k != "jeton"}))
    base = BaseMagasin()
    monkeypatch.setattr(pub, "requete", base)
    assert pub.main([]) == 0
    sortie1 = capsys.readouterr().out
    assert "Lecture : complète" in sortie1 and len(base.lignes()) == 10
    assert "Contrôle de la balance Pennylane (lecture complète) : identique" in sortie1
    assert list(base.t["pennylane_etat"].values())[0]["derniere_complete"]
    modifier(serveur)
    avant = len(serveur.appels)
    assert pub.main([]) == 0
    sortie2 = capsys.readouterr().out
    assert "par modifications" in sortie2 and "(lecture par modifications) : identique" in sortie2
    assert len(serveur.appels) - avant <= 12
    assert {l["id"] for l in base.lignes()} == {11, 12, 21, 22, 31, 32, 61, 62, 81, 82}
    assert "120.00" not in sortie2


def balance(lignes, items, entrees=None):
    c = pl.Client("jeton-fictif", ouvrir=lambda u, h: (200, {}, json.dumps({"items": items, "has_more": False})),
                  dormir=lambda s: None)
    return pl._balance_identique(c, lignes, date(2026, 1, 1), date(2026, 12, 31), [(date(2026, 1, 1), date(2026, 12, 31))],
                                 entrees)


def L(i, compte, debit="0", credit="0", entree=1):
    return {"id": i, "date": "2026-03-01", "ledger_account": {"number": compte}, "debit": debit, "credit": credit,
            "ledger_entry": {"id": entree}}


def test_balance_regroupe_les_comptes_de_tiers():
    lignes = [L(1, "4010001", credit="100"), L(2, "4010002", credit="50"), L(3, "6064000", debit="150")]
    ok, texte = balance(lignes, [{"number": "401", "debits": "0", "credits": "150"},
                                 {"number": "6064000", "debits": "150", "credits": "0"}])
    assert ok and texte == "identique"


def test_balance_sans_brouillard():
    lignes = [L(1, "512", debit="10", entree=1), L(2, "471", credit="10", entree=1),
              L(3, "512", debit="5", entree=2), L(4, "471", credit="5", entree=2)]
    items = [{"number": "512", "debits": "10", "credits": "0"}, {"number": "471", "debits": "0", "credits": "10"}]
    ok, texte = balance(lignes, items, {1: {"status": "complete"}, 2: {"status": "validation_needed"}})
    assert ok and "brouillard exclues" in texte


def test_balance_diagnostic_sans_montant():
    lignes = [L(1, "4010001", credit="100"), L(2, "6064000", debit="100"), L(3, "512", debit="7"), L(4, "471", credit="7")]
    ok, texte = balance(lignes, [{"number": "6064000", "debits": "100", "credits": "0"},
                                 {"number": "512", "debits": "9", "credits": "0"}, {"number": "471", "debits": "0", "credits": "7"}])
    assert not ok
    assert texte == ("différente sur 2 compte(s) : 1 absent de la balance Pennylane (40 : 1) ; "
                     "1 montant différent (51 : 1)")
    assert "100" not in texte and "7" not in texte.replace("différente", "")
