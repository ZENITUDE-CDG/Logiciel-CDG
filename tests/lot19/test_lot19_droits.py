"""Lot 19 - droits de la migration 011 (base PostgreSQL de test, données fictives).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL).

(décision 0017 : les jetons Pennylane chiffrés dans le logiciel sont retirés ; leurs tests aussi.)
- statut des mois : lecture selon le parc ; historique des dépôts : administrateurs ;
- code Mews modifiable par un administrateur seulement ; montants CA signés, quantités positives.
"""
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
        cur.execute("SELECT to_regclass('public.depots_kpi') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 011 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur"), (LECTURE, "L", "lecture")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "F1", "D-1"), ("RES-002", "F2", "D-2")])
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001'), (%s, 'RES-001')", (COLLAB, LECTURE))
        cur.execute("INSERT INTO kpi_mois (dossier, mois, source, statut) VALUES ('D-1', '2026-10', 'Import Mews', 'Complet'), "
                    "('D-2', '2026-10', 'Import Mews', 'Estimé')")
        yield conn
    finally:
        conn.rollback()
        conn.close()


def connecte(conn, email):
    cur = conn.cursor()
    cur.execute("SET ROLE authenticated" if email else "SET ROLE anon")
    cur.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps({"email": email}) if email else "",))
    return cur


def service(conn):
    cur = conn.cursor()
    cur.execute("RESET ROLE")
    return cur


def refuse(conn, cur, sql, params=None, erreur=errors.InsufficientPrivilege):
    with pytest.raises(erreur):
        with conn.transaction():
            cur.execute(sql, params)


def test_statut_des_mois_et_depots(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("SELECT dossier, statut FROM kpi_mois ORDER BY 1")
    assert cur.fetchall() == [("D-1", "Complet")]
    cur.execute("UPDATE kpi_mois SET statut = 'x'")
    assert cur.rowcount == 0
    refuse(jeu, cur, "INSERT INTO depots_kpi (fichier) VALUES ('f.xlsx')", erreur=errors.InsufficientPrivilege)
    cur.execute("SELECT * FROM depots_kpi")
    assert cur.fetchall() == []
    cur = connecte(jeu, ADMIN)
    cur.execute("INSERT INTO kpi_mois (dossier, mois, statut, detail) VALUES ('D-1', '2026-09', 'Estimé', 'clients repris') RETURNING importe_par")
    assert cur.fetchone()[0] == ADMIN
    cur.execute("INSERT INTO depots_kpi (fichier, perimetre, residences, nouvelles) VALUES ('Consolide_KPI_2026.xlsx', 'Groupe', 2, 10) RETURNING depose_par")
    assert cur.fetchone()[0] == ADMIN
    refuse(jeu, cur, "UPDATE depots_kpi SET nouvelles = 0")
    refuse(jeu, cur, "DELETE FROM depots_kpi")


def test_code_mews_par_un_administrateur(jeu):
    cur = connecte(jeu, COLLAB)  # le collaborateur modifie les résidences de son parc (lot 12)...
    refuse(jeu, cur, "UPDATE residences SET code_mews = 'ABA' WHERE id = 'RES-001'")  # ...mais pas le code Mews
    cur.execute("UPDATE residences SET libelle = 'F1 bis' WHERE id = 'RES-001'")
    assert cur.rowcount == 1
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE residences SET code_mews = 'ABA' WHERE id = 'RES-001'")
    refuse(jeu, cur, "UPDATE residences SET code_mews = 'ABA' WHERE id = 'RES-002'", erreur=errors.UniqueViolation)
    refuse(jeu, cur, "UPDATE residences SET code_mews = 'aba x' WHERE id = 'RES-002'", erreur=errors.CheckViolation)


def test_montants_signes_quantites_positives(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-10', 'CA_MEWS_TOTAL', -120.5)")
    refuse(jeu, cur, "INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-10', 'NUITEES_CLIENTS', -3)",
           erreur=errors.CheckViolation)

