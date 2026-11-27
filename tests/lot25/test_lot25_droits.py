"""Lot 25 - droits et contrôles de la migration 016 (missions Claude versionnées, journal des paquets).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB, LECTURE = "admin@exemple.invalid", "collab@exemple.invalid", "lecture@exemple.invalid"
EMP = "a" * 64


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.missions_claude') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 016 non appliquée sur la base de test.")
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


MISSION = "INSERT INTO missions_claude (code, categorie, titre, consignes, livrables) VALUES (%s, 'Budget', 'Normatif', 'Hypothèses…', 'Note.md') RETURNING id, version, modifie_par"
PAQUET = ("INSERT INTO paquets_claude (perimetre, dossiers, du, au, niveau, empreinte, mission_code, mission_version, cree_par, reference) "
          "VALUES ('P', %s, '2025-10', '2026-09', 'synthese', %s, %s, %s, 'pirate@exemple.invalid', 'PQ-999999') RETURNING id, reference, cree_par")


def test_missions_administrateur_et_versions(jeu):
    a = connecte(jeu, ADMIN)
    a.execute(MISSION, ("NORMATIF-BUDGET",))
    mid, version, par = a.fetchone()
    assert version == 1 and par == ADMIN
    a.execute("UPDATE missions_claude SET consignes = 'Hypothèses v2', version = 99 WHERE id = %s RETURNING version", (mid,))
    assert a.fetchone()[0] == 2  # la version est posée par la base
    a.execute("UPDATE missions_claude SET actif = false WHERE id = %s RETURNING version", (mid,))
    assert a.fetchone()[0] == 2  # archiver ne crée pas de version
    refuse(jeu, a, MISSION, ("NORMATIF-BUDGET",), errors.UniqueViolation)
    refuse(jeu, a, MISSION, ("minuscules",), errors.CheckViolation)
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        cur.execute("SELECT version, consignes FROM missions_versions WHERE mission_id = %s", (mid,))
        assert cur.fetchall() == [(1, "Hypothèses…")]  # versions lisibles par tous
        cur.execute("SELECT count(*) FROM missions_claude")
        assert cur.fetchone()[0] == 1
        refuse(jeu, cur, MISSION, ("AUTRE",))
        cur.execute("UPDATE missions_claude SET titre = 'x' WHERE id = %s", (mid,))
        assert cur.rowcount == 0
        refuse(jeu, cur, "INSERT INTO missions_versions (mission_id, version, code, titre, consignes, modifie_le) VALUES (%s, 9, 'X', 't', 'c', now())", (mid,))
    refuse(jeu, connecte(jeu, None), "SELECT count(*) FROM missions_claude")


def test_journal_des_paquets(jeu):
    c = connecte(jeu, COLLAB)
    c.execute(PAQUET, (["D-1"], EMP, "NORMATIF-BUDGET", 2))
    pid, ref, par = c.fetchone()
    assert ref == "PQ-" + str(pid).zfill(6) and par == COLLAB  # référence et auteur posés par la base
    refuse(jeu, c, PAQUET, (["D-1", "D-2"], EMP, None, None), errors.InsufficientPrivilege)  # D-2 hors de son parc
    refuse(jeu, c, PAQUET, (["D-1"], "pas-une-empreinte", None, None), errors.CheckViolation)
    refuse(jeu, c, PAQUET, (["D-1"], EMP, "NORMATIF-BUDGET", None), errors.CheckViolation)  # code sans version
    c.execute("UPDATE paquets_claude SET resultat = 'https://exemple.invalid/doc.xlsx', resultat_note = 'v1' WHERE id = %s RETURNING resultat_par", (pid,))
    assert c.fetchone()[0] == COLLAB
    refuse(jeu, c, "UPDATE paquets_claude SET empreinte = %s WHERE id = %s", ("b" * 64, pid), errors.CheckViolation)
    refuse(jeu, c, "DELETE FROM paquets_claude WHERE id = %s", (pid,))
    lec = connecte(jeu, LECTURE)
    lec.execute("SELECT count(*) FROM paquets_claude")
    assert lec.fetchone()[0] == 0  # ne voit que ses propres paquets
    lec.execute("UPDATE paquets_claude SET resultat = 'x' WHERE id = %s", (pid,))
    assert lec.rowcount == 0
    a = connecte(jeu, ADMIN)
    a.execute("SELECT reference, resultat FROM paquets_claude")
    assert a.fetchall() == [(ref, "https://exemple.invalid/doc.xlsx")]
