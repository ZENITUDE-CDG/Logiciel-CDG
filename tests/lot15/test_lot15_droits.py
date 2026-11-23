"""Lot 15 - droits sur les KPI importés et les paramètres des comptes bancaires (migration 006).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB, LECTURE = "admin@exemple.invalid", "collab@exemple.invalid", "lecture@exemple.invalid"


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.mesures_importees') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 006 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur"), (LECTURE, "L", "lecture")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "F1", "D-1"), ("RES-002", "F2", "D-2")])
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001'), (%s, 'RES-001')", (COLLAB, LECTURE))
        yield conn
    finally:
        conn.rollback()
        conn.close()


def connecte(conn, email):
    cur = conn.cursor()
    cur.execute("SET ROLE authenticated" if email else "SET ROLE anon")
    cur.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email}) if email else "",))
    return cur


def refuse(conn, cur, sql, params=None, erreur=errors.InsufficientPrivilege):
    with pytest.raises(erreur):
        with conn.transaction():
            cur.execute(sql, params)


MES = "INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES (%s, '2026-03', 'LN_VENDUES', 1540)"
BQ = "INSERT INTO comptes_bancaires (dossier, compte, libelle, role, solde_min) VALUES (%s, '5122', 'Secondaire', 'secondaire', 500000)"


def test_seul_l_administrateur_importe(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute(MES, ("D-1",))
    cur.execute(MES, ("D-2",))
    cur.execute("SELECT importe_par FROM mesures_importees WHERE dossier = 'D-1'")
    assert cur.fetchone()[0] == ADMIN
    for email in (COLLAB, LECTURE):
        refuse(jeu, connecte(jeu, email), MES.replace("'2026-03'", "'2026-04'"), ("D-1",))


def test_lecture_selon_le_parc(jeu):
    connecte(jeu, ADMIN).execute(MES, ("D-1",))
    connecte(jeu, ADMIN).execute(MES, ("D-2",))
    connecte(jeu, ADMIN).execute(BQ, ("D-2",))
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        cur.execute("SELECT dossier FROM mesures_importees")
        assert [r[0] for r in cur.fetchall()] == ["D-1"]
        cur.execute("SELECT count(*) FROM comptes_bancaires")
        assert cur.fetchone()[0] == 0
    refuse(jeu, connecte(jeu, None), "SELECT * FROM mesures_importees")


def test_valeurs_et_formats_controles(jeu):
    cur = connecte(jeu, ADMIN)
    refuse(jeu, cur, "INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-3', 'LN_VENDUES', 1)", erreur=errors.CheckViolation)
    refuse(jeu, cur, "INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-03', 'LN_VENDUES', -1)", erreur=errors.CheckViolation)
    refuse(jeu, cur, "INSERT INTO comptes_bancaires (dossier, compte, role) VALUES ('D-1', '411', 'autre')", erreur=errors.CheckViolation)
    refuse(jeu, cur, "INSERT INTO comptes_bancaires (dossier, compte, role) VALUES ('D-1', '512', 'chef')", erreur=errors.CheckViolation)


def test_parametres_bancaires_par_l_administrateur(jeu):
    connecte(jeu, ADMIN).execute(BQ, ("D-1",))
    refuse(jeu, connecte(jeu, COLLAB), BQ.replace("'5122'", "'512'"), ("D-1",))
    cur = connecte(jeu, COLLAB)
    cur.execute("UPDATE comptes_bancaires SET solde_min = 0")
    assert cur.rowcount == 0
    cur = connecte(jeu, LECTURE)
    cur.execute("SELECT role, solde_min, modifie_par FROM comptes_bancaires")
    assert cur.fetchone() == ("secondaire", 500000, ADMIN)
