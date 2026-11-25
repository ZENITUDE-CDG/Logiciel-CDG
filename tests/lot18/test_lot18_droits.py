"""Lot 18b - droits sur les paramètres d'import et le journal des synchronisations (migration 007).
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
        cur.execute("SELECT to_regclass('public.synchronisations') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 007 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur"), (LECTURE, "L", "lecture")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "F1", "D-1"), ("RES-002", "F2", "D-2")])
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001'), (%s, 'RES-001')", (COLLAB, LECTURE))
        # Écritures de la fonction serveur et de GitHub Actions : clé secrète, hors règles de lignes
        cur.execute("INSERT INTO parametres_import (dossier, mois_debut, mois_fin, masquer_brouillard, modifie_par) "
                    "VALUES ('D-1', '2026-01', '2026-10', true, %s), ('D-2', NULL, NULL, false, %s)", (ADMIN, ADMIN))
        cur.execute("INSERT INTO synchronisations (demandee_par, perimetre, dossiers, mois_debut, mois_fin) "
                    "VALUES (%s, 'Groupe', ARRAY['D-1','D-2'], '2026-01', '2026-10') RETURNING id", (ADMIN,))
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


def lignes(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


def test_lecture_des_parametres_selon_le_parc(jeu):
    assert [r[0] for r in lignes(connecte(jeu, ADMIN), "SELECT dossier FROM parametres_import ORDER BY 1")] == ["D-1", "D-2"]
    for email in (COLLAB, LECTURE):
        assert lignes(connecte(jeu, email), "SELECT dossier, mois_fin FROM parametres_import") == [("D-1", "2026-10")]


def test_anonyme_sans_acces(jeu):
    cur = connecte(jeu, None)
    refuse(jeu, cur, "SELECT * FROM parametres_import")
    refuse(jeu, cur, "SELECT * FROM synchronisations")


def test_seul_l_administrateur_modifie_les_parametres(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE parametres_import SET masquer_brouillard = false WHERE dossier = 'D-1'")
    cur.execute("SELECT modifie_par FROM parametres_import WHERE dossier = 'D-1'")
    assert cur.fetchone()[0] == ADMIN
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        cur.execute("UPDATE parametres_import SET masquer_brouillard = true WHERE dossier = 'D-1'")
        assert cur.rowcount == 0
        refuse(jeu, cur, "INSERT INTO parametres_import (dossier) VALUES ('D-1X')", erreur=errors.InsufficientPrivilege)


def test_controles_des_parametres(jeu):
    cur = connecte(jeu, ADMIN)
    refuse(jeu, cur, "UPDATE parametres_import SET mois_debut = '2026-13' WHERE dossier = 'D-1'", erreur=errors.CheckViolation)
    refuse(jeu, cur, "UPDATE parametres_import SET mois_debut = '2026-11', mois_fin = '2026-10' WHERE dossier = 'D-1'",
           erreur=errors.CheckViolation)


def test_journal_des_synchronisations_reserve_aux_administrateurs(jeu):
    assert len(lignes(connecte(jeu, ADMIN), "SELECT id FROM synchronisations")) == 1
    for email in (COLLAB, LECTURE):
        assert lignes(connecte(jeu, email), "SELECT id FROM synchronisations") == []


def test_personne_n_ecrit_le_journal_depuis_la_page(jeu):
    for email in (ADMIN, COLLAB):
        cur = connecte(jeu, email)
        refuse(jeu, cur, "INSERT INTO synchronisations (dossiers) VALUES (ARRAY['D-1'])")
        refuse(jeu, cur, "UPDATE synchronisations SET statut = 'terminée'")
        refuse(jeu, cur, "DELETE FROM synchronisations")


def test_statut_controle(jeu):
    cur = jeu.cursor()
    refuse(jeu, cur, "UPDATE synchronisations SET statut = 'inventé'", erreur=errors.CheckViolation)


def test_memoire_du_lettrage_inaccessible_depuis_la_page(jeu):
    cur = jeu.cursor()
    cur.execute("INSERT INTO lettrages_pennylane (dossier, ligne_id, maj, groupe) VALUES ('D-1', 12, 'x', 'L12')")
    cur.execute("SELECT lu_le IS NOT NULL FROM lettrages_pennylane WHERE ligne_id = 12")
    assert cur.fetchone()[0]
    for email in (ADMIN, COLLAB, None):
        c = connecte(jeu, email)
        refuse(jeu, c, "SELECT * FROM lettrages_pennylane")
        refuse(jeu, c, "INSERT INTO lettrages_pennylane (dossier, ligne_id) VALUES ('D-1', 13)")
