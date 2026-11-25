"""Lot 20 - droits et contrôles de la migration 012 (base PostgreSQL de test, données fictives).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB = "admin@exemple.invalid", "collab@exemple.invalid"


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.kpi_catalogue') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 012 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur")])
        cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                        [("RES-001", "F1", "D-1"), ("RES-002", "F2", "D-2")])
        cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", (COLLAB,))
        cur.execute("INSERT INTO residence_modele (dossier, modele) VALUES ('D-1', 'TOURISME'), ('D-2', 'SENIORS')")
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


DONNEE = ("INSERT INTO kpi_catalogue (code, type, libelle, rubrique, modeles, signe) "
          "VALUES (%s, 'donnee', %s, 'Test', ARRAY['TOURISME'], %s)")


def test_lecture_pour_tous_ecriture_administrateur(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("SELECT count(*) FROM kpi_catalogue")
    assert cur.fetchone()[0] == 30
    cur.execute("SELECT dossier FROM residence_modele")
    assert cur.fetchall() == [("D-1",)]  # selon le parc
    cur.execute("UPDATE kpi_catalogue SET libelle = 'x' WHERE code = 'PM'")
    assert cur.rowcount == 0
    refuse(jeu, cur, DONNEE, ("ESSAI", "Essai", "positif"), erreur=errors.InsufficientPrivilege)
    cur.execute("SELECT * FROM kpi_journal")
    assert cur.fetchall() == []
    cur.execute("UPDATE residence_modele SET modele = 'SENIORS'")
    assert cur.rowcount == 0


def test_controles_du_catalogue(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute(DONNEE, ("ESSAI", "Essai", "positif"))
    refuse(jeu, cur, "INSERT INTO kpi_catalogue (code, type, libelle, modeles, numerateur) VALUES ('I_X', 'indicateur', 'X', ARRAY['TOURISME'], ARRAY['INCONNUE'])",
           erreur=errors.ForeignKeyViolation)
    refuse(jeu, cur, "INSERT INTO kpi_catalogue (code, type, libelle, modeles) VALUES ('I_Y', 'indicateur', 'Y', ARRAY['TOURISME'])",
           erreur=errors.CheckViolation)  # indicateur sans numérateur
    refuse(jeu, cur, DONNEE.replace("ARRAY['TOURISME']", "ARRAY['INCONNU']"), ("ESSAI2", "E", "positif"), erreur=errors.ForeignKeyViolation)
    refuse(jeu, cur, "UPDATE kpi_catalogue SET code = 'AUTRE' WHERE code = 'ESSAI'", erreur=errors.CheckViolation)
    refuse(jeu, cur, "UPDATE kpi_catalogue SET type = 'indicateur', numerateur = ARRAY['LN_VENDUES'] WHERE code = 'ESSAI'", erreur=errors.CheckViolation)
    # Donnée utilisée par un indicateur actif : ni désactivée, ni supprimée
    refuse(jeu, cur, "UPDATE kpi_catalogue SET actif = false WHERE code = 'LN_VENDUES'", erreur=errors.CheckViolation)
    refuse(jeu, cur, "DELETE FROM kpi_catalogue WHERE code = 'LN_VENDUES'", erreur=errors.ForeignKeyViolation)
    cur.execute("UPDATE kpi_catalogue SET actif = false WHERE code = 'TO_RES'")
    cur.execute("SELECT version, modifie_par FROM kpi_catalogue WHERE code = 'TO_RES'")
    assert cur.fetchone() == (2, ADMIN)
    # Donnée avec des valeurs importées : on la désactive, on ne la supprime pas
    cur.execute("INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-10', 'ESSAI', 3)")
    refuse(jeu, cur, "DELETE FROM kpi_catalogue WHERE code = 'ESSAI'", erreur=errors.ForeignKeyViolation)
    cur.execute("UPDATE kpi_catalogue SET actif = false WHERE code = 'ESSAI'")
    cur.execute(DONNEE, ("ESSAI3", "Essai 3", "positif"))
    cur.execute("DELETE FROM kpi_catalogue WHERE code = 'ESSAI3'")


def test_journal_ecrit_par_la_base(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE kpi_catalogue SET seuil = 0.6, sens = 'haut' WHERE code = 'TO_HOT'")
    cur.execute("SELECT action, par, avant->>'seuil', apres->>'seuil' FROM kpi_journal WHERE code = 'TO_HOT' ORDER BY id DESC LIMIT 1")
    assert cur.fetchone() == ("modification", ADMIN, None, "0.6")
    refuse(jeu, cur, "INSERT INTO kpi_journal (code, action) VALUES ('X', 'création')")
    refuse(jeu, cur, "DELETE FROM kpi_journal")


def test_signe_des_valeurs_importees(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute(DONNEE, ("AVOIRS_DIVERS", "Avoirs", "signe"))
    cur.execute("INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-10', 'AVOIRS_DIVERS', -50)")
    cur.execute("INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-10', 'CA_MEWS_RESTO', -5)")
    refuse(jeu, cur, "INSERT INTO mesures_importees (dossier, mois, mesure, valeur) VALUES ('D-1', '2026-10', 'NUITEES_CLIENTS', -1)",
           erreur=errors.CheckViolation)


def test_modele_des_residences(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE residence_modele SET modele = 'ETUDIANTS' WHERE dossier = 'D-2' RETURNING modifie_par")
    assert cur.fetchone()[0] == ADMIN
    refuse(jeu, cur, "INSERT INTO residence_modele (dossier, modele) VALUES ('D-1X', 'INCONNU')",
           erreur=(errors.ForeignKeyViolation, errors.InsufficientPrivilege))
