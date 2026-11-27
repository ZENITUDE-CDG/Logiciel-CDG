"""Lot 26 - droits et contrôles de la migration 017 (totaux DSN par établissement et par mois).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB = "admin@exemple.invalid", "collab@exemple.invalid"
EMP = "b" * 64
CONTENU = json.dumps({"effectif_fin": 3, "brut": 600000, "arrets": []})
SIRET = "99900200100011"


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.dsn_mois') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 017 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "F1", "D-1"), ("RES-002", "F2", "D-2")])
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", (COLLAB,))
        yield conn
    finally:
        conn.rollback()
        conn.close()


def connecte(conn, email):
    cur = conn.cursor()
    cur.execute("SET ROLE authenticated")
    cur.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email}),))
    return cur


def refuse(conn, cur, sql, params=None, erreur=errors.InsufficientPrivilege):
    with pytest.raises(erreur):
        with conn.transaction():
            cur.execute(sql, params)


MOIS = ("INSERT INTO dsn_mois (siret, dossier, mois, type_decl, contenu, fichier, empreinte, importe_par) "
        "VALUES (%s, 'D-2', %s, '01', %s::jsonb, 'f.dsn', %s, 'pirate@exemple.invalid') "
        "ON CONFLICT (siret, mois) DO UPDATE SET contenu = EXCLUDED.contenu, empreinte = EXCLUDED.empreinte, type_decl = EXCLUDED.type_decl "
        "RETURNING dossier, importe_par")


def test_import_rattachement_et_journal(jeu):
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO dsn_etablissements (siret, dossier) VALUES (%s, 'D-1')", (SIRET,))
    a.execute(MOIS, (SIRET, "2026-03", CONTENU, EMP))
    assert a.fetchone() == ("D-1", ADMIN)  # résidence et auteur posés par la base
    a.execute(MOIS, (SIRET, "2026-03", CONTENU, "c" * 64))  # remplacement du même mois
    a.execute("SELECT count(*) FROM dsn_mois")
    assert a.fetchone()[0] == 1
    a.execute("UPDATE dsn_etablissements SET dossier = 'D-2' WHERE siret = %s", (SIRET,))
    a.execute("SELECT dossier, importe_par FROM dsn_mois")
    assert a.fetchone() == ("D-2", ADMIN)
    a.execute("SELECT action FROM dsn_journal ORDER BY id")
    assert [r[0] for r in a.fetchall()] == ["rattachement", "import", "remplacement", "rattachement"]
    a.execute("DELETE FROM dsn_mois")
    a.execute("SELECT action FROM dsn_journal ORDER BY id DESC LIMIT 1")
    assert a.fetchone()[0] == "suppression"


def test_reserve_aux_administrateurs(jeu):
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO dsn_etablissements (siret, dossier) VALUES (%s, 'D-1')", (SIRET,))
    a.execute(MOIS, (SIRET, "2026-03", CONTENU, EMP))
    c = connecte(jeu, COLLAB)
    for t in ("dsn_mois", "dsn_etablissements", "dsn_journal"):
        c.execute(f"SELECT count(*) FROM {t}")
        assert c.fetchone()[0] == 0  # même pour une résidence de son parc
    refuse(jeu, c, MOIS, (SIRET, "2026-04", CONTENU, EMP), errors.InsufficientPrivilege)
    refuse(jeu, c, "INSERT INTO dsn_etablissements (siret, dossier) VALUES ('99900200200011', 'D-1')")


def test_controles(jeu):
    a = connecte(jeu, ADMIN)
    refuse(jeu, a, "INSERT INTO dsn_etablissements (siret, dossier) VALUES ('123', 'D-1')", None, errors.CheckViolation)
    refuse(jeu, a, "INSERT INTO dsn_etablissements (siret, dossier) VALUES (%s, 'D-9')", (SIRET,), errors.CheckViolation)
    refuse(jeu, a, MOIS, (SIRET, "2026-03", CONTENU, EMP), errors.CheckViolation)  # SIRET non rattaché
    a.execute("INSERT INTO dsn_etablissements (siret, dossier) VALUES (%s, 'D-1')", (SIRET,))
    nominatif = json.dumps({"effectif_fin": 1, "brut": 1, "nir": "1"})
    refuse(jeu, a, MOIS, (SIRET, "2026-03", nominatif, EMP), errors.CheckViolation)
    refuse(jeu, a, MOIS, (SIRET, "2026-13", CONTENU, EMP), errors.CheckViolation)
    refuse(jeu, a, "INSERT INTO dsn_journal (action, siret) VALUES ('import', 'x')")
