"""Lots 28 à 30 - droits et contrôles de la migration 019 (suivi des écarts, paramètres, paquet d'écarts).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB, LECT = "admin@exemple.invalid", "collab@exemple.invalid", "lect@exemple.invalid"


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.ecarts_suivi') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 019 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur"), (LECT, "L", "lecture")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "F1", "D-1"), ("RES-002", "F2", "D-2")])
        cur.executemany("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", [(COLLAB,), (LECT,)])
        yield conn
    finally:
        conn.rollback()
        conn.close()


def connecte(conn, email):
    cur = conn.cursor()
    cur.execute("RESET ROLE")
    cur.execute("SET ROLE authenticated")
    cur.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email}),))
    return cur


def refuse(conn, cur, sql, params=None, erreur=errors.InsufficientPrivilege):
    with pytest.raises(erreur):
        with conn.transaction():
            cur.execute(sql, params)


AJOUT = ("INSERT INTO ecarts_suivi (cle, dossier, code, du, au, reference, statut, commentaire, montant, cree_par) "
         "VALUES (%s, %s, %s, '2026-09', '2026-09', 'prec', %s, %s, -4800000, 'pirate@exemple.invalid') RETURNING id, cree_par, modifie_par")


def cle(code, d, objet="X"):
    return f"{code}|{d}|{objet}|2026-09|2026-09|prec"


def test_suivi_parc_et_traces(jeu):
    c = connecte(jeu, COLLAB)
    c.execute(AJOUT, (cle("A2", "D-1"), "D-1", "A2", "explique", "Séminaire annuel"))
    i, cree, modif = c.fetchone()
    assert cree == COLLAB and modif == COLLAB
    refuse(jeu, c, AJOUT, (cle("A2", "D-2"), "D-2", "A2", "explique", "Hors parc"))
    c.execute("UPDATE ecarts_suivi SET statut = 'corrige', commentaire = 'Repris' WHERE id = %s RETURNING statut", (i,))
    assert c.fetchone()[0] == "corrige"
    refuse(jeu, c, "UPDATE ecarts_suivi SET cle = %s WHERE id = %s", (cle("A2", "D-1", "Y"), i), errors.CheckViolation)
    c.execute("DELETE FROM ecarts_suivi WHERE id = %s", (i,))
    assert c.rowcount == 0  # un collaborateur ne supprime pas
    c.execute("SELECT action, statut, par FROM ecarts_journal WHERE suivi_id = %s ORDER BY id", (i,))
    assert c.fetchall() == [("insert", "explique", COLLAB), ("update", "corrige", COLLAB)]
    refuse(jeu, c, "INSERT INTO ecarts_journal (suivi_id, cle, dossier, action) VALUES (1, 'x', 'D-1', 'faux')")
    a = connecte(jeu, ADMIN)
    a.execute(AJOUT, (cle("N1", "D-2"), "D-2", "N1", "a_analyser", ""))
    a.execute("SELECT count(*) FROM ecarts_suivi")
    assert a.fetchone()[0] == 2
    c = connecte(jeu, COLLAB)
    c.execute("SELECT dossier FROM ecarts_suivi")
    assert [x[0] for x in c.fetchall()] == ["D-1"]
    a = connecte(jeu, ADMIN)
    a.execute("DELETE FROM ecarts_suivi WHERE id = %s", (i,))
    assert a.rowcount == 1
    a.execute("SELECT action FROM ecarts_journal WHERE suivi_id = %s ORDER BY id DESC LIMIT 1", (i,))
    assert a.fetchone()[0] == "suppression"


def test_lecture_seule_et_controles(jeu):
    l = connecte(jeu, LECT)
    refuse(jeu, l, AJOUT, (cle("A2", "D-1"), "D-1", "A2", "explique", "x"))
    a = connecte(jeu, ADMIN)
    refuse(jeu, a, AJOUT, (cle("A2", "D-1"), "D-1", "A2", "inconnu", "x"), errors.CheckViolation)
    refuse(jeu, a, AJOUT, (cle("A2", "D-2"), "D-1", "A2", "explique", "x"), errors.CheckViolation)  # clé d'une autre résidence
    refuse(jeu, a, AJOUT, ("N1|D-1|X|2026-09|2026-09|prec", "D-1", "A2", "explique", "x"), errors.CheckViolation)  # code
    refuse(jeu, a, AJOUT, (cle("A2", "D-1"), "D-1", "A2", "explique", "x" * 2001), errors.CheckViolation)


def test_parametres(jeu):
    c = connecte(jeu, COLLAB)
    c.execute("SELECT reference FROM analyse_parametres")
    assert c.fetchone()[0] == "n1"
    c.execute("UPDATE analyse_parametres SET reference = 'prec'")
    assert c.rowcount == 0
    a = connecte(jeu, ADMIN)
    a.execute("UPDATE analyse_parametres SET seuils = %s, reference = 'moy12' RETURNING modifie_par", (json.dumps({"pct": 0.05, "montant": 100000}),))
    assert a.fetchone()[0] == ADMIN
    refuse(jeu, a, "UPDATE analyse_parametres SET seuils = %s", (json.dumps({"inconnu": 1}),), errors.CheckViolation)
    refuse(jeu, a, "UPDATE analyse_parametres SET seuils = %s", (json.dumps({"pct": -1}),), errors.CheckViolation)
    refuse(jeu, a, "INSERT INTO analyse_parametres (id) VALUES (2)")


def test_paquet_d_ecarts(jeu):
    c = connecte(jeu, COLLAB)
    c.execute("INSERT INTO paquets_claude (perimetre, dossiers, du, au, niveau, empreinte) VALUES ('F1', ARRAY['D-1'], '2026-09', '2026-09', 'ecarts', %s) RETURNING reference",
              ("c" * 64,))
    assert c.fetchone()[0].startswith("PQ-")
    refuse(jeu, c, "INSERT INTO paquets_claude (perimetre, dossiers, du, au, niveau, empreinte) VALUES ('F1', ARRAY['D-1'], '2026-09', '2026-09', 'autre', %s)",
           ("c" * 64,), errors.CheckViolation)
