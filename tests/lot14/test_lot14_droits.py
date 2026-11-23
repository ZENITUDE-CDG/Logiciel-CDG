"""
Lot 14 - droits sur les lissages d'écritures (migration 005, décision 0008).

Même principe qu'aux lots 12 et 13 : base PostgreSQL temporaire (GitHub Actions), personne connectée simulée,
chaque test annulé. Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL).
"""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN = "admin@exemple.invalid"
COLLAB = "collab@exemple.invalid"
LECTURE = "lecture@exemple.invalid"
INSERT = ("INSERT INTO lissages (dossier, ecriture, compte, montant, date_ecriture, du, au) "
          "VALUES (%s, %s, '635', -117863, '2026-09-28', '2025-10', '2026-09')")


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test":
        pytest.skip("ZENITUDE_ENV=test absent : tests réservés à la base de test.")
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL absent.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.lissages') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 005 non appliquée sur la base de test.")
        cur.execute("SELECT (SELECT count(*) FROM profils) + (SELECT count(*) FROM lissages)")
        if cur.fetchone()[0] != 0:
            pytest.fail("La base de test doit être vide avant les tests.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur"), (LECTURE, "L", "lecture")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "Fictive 1", "D-1"), ("RES-002", "Fictive 2", "D-2")])
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", (COLLAB,))
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", (LECTURE,))
        yield conn
    finally:
        conn.rollback()
        conn.close()


def connecte(conn, email):
    cur = conn.cursor()
    if email is None:
        cur.execute("SET ROLE anon")
        cur.execute("SELECT set_config('request.jwt.claims', '', true)")
    else:
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email}),))
    return cur


def refuse(conn, cur, sql, params=None, erreur=errors.InsufficientPrivilege):
    with pytest.raises(erreur):
        with conn.transaction():
            cur.execute(sql, params)


def ids(cur):
    cur.execute("SELECT dossier || '/' || ecriture FROM lissages")
    return sorted(r[0] for r in cur.fetchall())


def test_collaborateur_lisse_sur_son_parc(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute(INSERT, ("D-1", "HA00192-1"))
    cur.execute("SELECT cree_par, actif FROM lissages")
    assert cur.fetchone() == (COLLAB, True)
    refuse(jeu, cur, INSERT, ("D-2", "HA00001-1"))


def test_lecture_seule_et_anonyme_refuses(jeu):
    refuse(jeu, connecte(jeu, LECTURE), INSERT, ("D-1", "HA00192-1"))
    refuse(jeu, connecte(jeu, None), "SELECT * FROM lissages")


def test_visibilite_selon_le_parc(jeu):
    adm = connecte(jeu, ADMIN)
    adm.execute(INSERT, ("D-1", "A-1"))
    adm.execute(INSERT, ("D-2", "B-1"))
    assert ids(connecte(jeu, ADMIN)) == ["D-1/A-1", "D-2/B-1"]
    assert ids(connecte(jeu, COLLAB)) == ["D-1/A-1"]
    assert ids(connecte(jeu, LECTURE)) == ["D-1/A-1"]


def test_modification_et_suppression(jeu):
    connecte(jeu, ADMIN).execute(INSERT, ("D-2", "B-1"))
    cur = connecte(jeu, COLLAB)
    cur.execute(INSERT, ("D-1", "A-1"))
    cur.execute("UPDATE lissages SET au = '2027-09', rev = 2 WHERE dossier = 'D-1'")
    assert cur.rowcount == 1
    cur.execute("UPDATE lissages SET actif = false WHERE dossier = 'D-2'")
    assert cur.rowcount == 0
    refuse(jeu, cur, "UPDATE lissages SET dossier = 'D-2' WHERE dossier = 'D-1'")
    cur = connecte(jeu, LECTURE)
    cur.execute("DELETE FROM lissages")
    assert cur.rowcount == 0
    cur = connecte(jeu, COLLAB)
    cur.execute("DELETE FROM lissages WHERE dossier = 'D-1'")
    assert cur.rowcount == 1


def test_une_ecriture_lissee_une_seule_fois_et_periode_valide(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute(INSERT, ("D-1", "A-1"))
    refuse(jeu, cur, INSERT, ("D-1", "A-1"), erreur=errors.UniqueViolation)
    refuse(jeu, cur, "INSERT INTO lissages (dossier, ecriture, compte, montant, date_ecriture, du, au) "
                     "VALUES ('D-1', 'A-2', '635', 1, '2026-01-01', '2026-12', '2026-01')", erreur=errors.CheckViolation)
    refuse(jeu, cur, "INSERT INTO lissages (dossier, ecriture, compte, montant, date_ecriture, du, au) "
                     "VALUES ('D-1', 'A-3', '411', 1, '2026-01-01', '2026-01', '2026-02')", erreur=errors.CheckViolation)


def test_trace_du_modificateur(jeu):
    connecte(jeu, COLLAB).execute(INSERT, ("D-1", "A-1"))
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE lissages SET actif = false")
    cur.execute("SELECT cree_par, modifie_par FROM lissages")
    assert cur.fetchone() == (COLLAB, ADMIN)
