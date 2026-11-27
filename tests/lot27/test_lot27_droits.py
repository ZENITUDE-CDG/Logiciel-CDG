"""Lot 27 - migration 018 : détail pseudonymisé par salarié et référentiel des postes.
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB = "admin@exemple.invalid", "collab@exemple.invalid"
SIRET = "99900200100011"


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.dsn_postes') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 018 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)", [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur")])
        cur.execute("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES ('RES-001', 'F1', 'D-1')")
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


MOIS = "INSERT INTO dsn_mois (siret, dossier, mois, type_decl, contenu, empreinte) VALUES (%s, 'D-1', '2026-03', '01', %s::jsonb, %s)"


def test_detail_pseudonymise_seulement(jeu):
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO dsn_etablissements (siret, dossier) VALUES (%s, 'D-1')", (SIRET,))
    sal = {"id": "abc123def456", "emploi": "RECEPTIONNISTE", "age": 30, "brut": 200000}
    a.execute(MOIS, (SIRET, json.dumps({"effectif_fin": 1, "brut": 200000, "salaries": [sal]}), "a" * 64))
    for interdit in ("nir", "nom", "naissance", "matricule"):
        x = json.dumps({"effectif_fin": 1, "brut": 1, "salaries": [dict(sal, **{interdit: "x"})]})
        refuse(jeu, a, "UPDATE dsn_mois SET contenu = %s::jsonb", (x,), errors.CheckViolation)


def test_referentiel_des_postes(jeu):
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO dsn_postes (emploi, poste, famille, modifie_par) VALUES ('RÉCEPTIONNISTE H/F', 'RECEPTIONNISTE', 'Réception', 'x') RETURNING modifie_par")
    assert a.fetchone()[0] == ADMIN
    a.execute("SELECT action, detail FROM dsn_journal ORDER BY id DESC LIMIT 1")
    assert a.fetchone() == ("référentiel", "RÉCEPTIONNISTE H/F → RECEPTIONNISTE (Réception)")
    refuse(jeu, a, "INSERT INTO dsn_postes (emploi, poste, famille) VALUES ('X', 'Y', 'Inconnue')", None, errors.CheckViolation)
    c = connecte(jeu, COLLAB)
    c.execute("SELECT count(*) FROM dsn_postes")
    assert c.fetchone()[0] == 0
    refuse(jeu, c, "INSERT INTO dsn_postes (emploi, poste, famille) VALUES ('X', 'Y', 'Autre')")
