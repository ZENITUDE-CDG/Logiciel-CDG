"""Lot 24 - droits et contrôles de la migration 015 (comptabilité du siège, trésorerie prévisionnelle).
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
        cur.execute("SELECT to_regclass('public.fees_regles') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 015 non appliquée sur la base de test.")
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


REGLE = "INSERT INTO fees_regles (rubrique, dossier, mois_effet, mode, valeur) VALUES ('MGT_FEES', %s, '2026-03', 'taux', 6)"
CLOT = "INSERT INTO fees_clotures (dossier, mois, contenu) VALUES (%s, '2026-03', '{\"lignes\": [], \"total\": 0, \"ca\": 0}')"
PREV = "INSERT INTO tresorerie_previsions (dossier, compte, libelle, sens, montant, date_prevue) VALUES (%s, '512', 'Loyer', 'dec', 100000, '2026-12-05')"


def test_amorce_et_lecture_selon_le_parc(jeu):
    a = connecte(jeu, ADMIN)
    a.execute(REGLE, ("D-1",))
    a.execute(REGLE, ("D-2",))
    a.execute("INSERT INTO ca_regles (dossier, inclus, exclus) VALUES ('D-2', '{706}', '{}')")
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        cur.execute("SELECT count(*) FROM fees_rubriques")
        assert cur.fetchone()[0] == 7
        cur.execute("SELECT DISTINCT dossier FROM fees_regles ORDER BY 1")
        assert [r[0] for r in cur.fetchall()] == ["*", "D-1"]  # règles du groupe + son parc
        cur.execute("SELECT count(*) FROM ca_regles")
        assert cur.fetchone()[0] == 0
    cur = connecte(jeu, None)
    refuse(jeu, cur, "SELECT count(*) FROM fees_rubriques")


def test_seul_l_administrateur_parametre_et_cloture(jeu):
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        refuse(jeu, cur, REGLE, ("D-1",), errors.InsufficientPrivilege)
        refuse(jeu, cur, "INSERT INTO fees_rubriques (code, libelle, base) VALUES ('FORMATION', 'Formation', 'CA')")
        refuse(jeu, cur, "INSERT INTO ca_regles (dossier, inclus) VALUES ('D-1', '{7}')")
        refuse(jeu, cur, CLOT, ("D-1",))
        refuse(jeu, cur, PREV, ("D-1",))
        refuse(jeu, cur, "INSERT INTO virements_suivis (dossier, compte_de, compte_vers, montant, date_virement) VALUES ('D-1', '512', '5122', 100, '2026-11-25')")
        cur.execute("UPDATE fees_regles SET valeur = 99 WHERE dossier = '*'")
        assert cur.rowcount == 0
    a = connecte(jeu, ADMIN)
    a.execute(REGLE, ("D-1",))
    a.execute("SELECT modifie_par FROM fees_regles WHERE dossier = 'D-1'")
    assert a.fetchone()[0] == ADMIN
    a.execute(CLOT, ("D-1",))
    a.execute(PREV, ("D-1",))
    a.execute("SELECT clos_par FROM fees_clotures")
    assert a.fetchone()[0] == ADMIN


def test_cloture_jamais_modifiee_et_journal(jeu):
    a = connecte(jeu, ADMIN)
    a.execute(CLOT, ("D-1",))
    refuse(jeu, a, "UPDATE fees_clotures SET contenu = '{\"lignes\": [], \"total\": 1}'", erreur=errors.CheckViolation)
    a.execute("DELETE FROM fees_clotures WHERE dossier = 'D-1'")  # rouvrir
    a.execute(REGLE, ("*",))
    a.execute("SELECT objet, action, par FROM compta_journal WHERE par IS NOT NULL ORDER BY id")
    assert a.fetchall() == [("cloture", "création", ADMIN), ("cloture", "suppression", ADMIN), ("regle", "création", ADMIN)]
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        cur.execute("SELECT count(*) FROM compta_journal")
        assert cur.fetchone()[0] == 0
        refuse(jeu, cur, "INSERT INTO compta_journal (objet, cle, action) VALUES ('regle', 'x', 'création')")


def test_controles_des_regles_et_rubriques(jeu):
    a = connecte(jeu, ADMIN)
    chk = errors.CheckViolation
    refuse(jeu, a, "INSERT INTO fees_regles (rubrique, dossier, mois_effet, mode, valeur) VALUES ('MGT_FEES', '*', '2026-03', 'groupe', NULL)", erreur=chk)
    refuse(jeu, a, "INSERT INTO fees_regles (rubrique, dossier, mois_effet, mode, valeur) VALUES ('MGT_FEES', 'D-1', '2026-03', 'taux', 1.23456)", erreur=chk)
    refuse(jeu, a, "INSERT INTO fees_regles (rubrique, dossier, mois_effet, mode, valeur) VALUES ('MGT_FEES', 'D-1', '2026-13', 'taux', 1)", erreur=chk)
    refuse(jeu, a, "INSERT INTO ca_regles (dossier, inclus) VALUES ('D-1', '{}')", erreur=chk)
    refuse(jeu, a, "INSERT INTO ca_regles (dossier, inclus) VALUES ('D-1', '{7A}')", erreur=chk)
    # Répartition : sa base doit être une rubrique sur le CA ; une base de répartitions reste sur le CA
    refuse(jeu, a, "INSERT INTO fees_rubriques (code, libelle, base, base_rubrique) VALUES ('X1', 'X', 'RUBRIQUE', 'COMPTA')", erreur=chk)
    refuse(jeu, a, "UPDATE fees_rubriques SET base = 'RUBRIQUE', base_rubrique = 'DROIT_MARQUE' WHERE code = 'MGT_FEES'", erreur=chk)
    refuse(jeu, a, "DELETE FROM fees_rubriques WHERE code = 'MGT_FEES'", erreur=errors.ForeignKeyViolation)
    a.execute("INSERT INTO fees_rubriques (code, libelle, base, base_rubrique) VALUES ('FORMATION', 'Formation', 'RUBRIQUE', 'MGT_FEES')")
    a.execute("INSERT INTO comptes_bancaires (dossier, compte, solde_min, solde_max) VALUES ('D-1', '512', 1000, 5000)")
    refuse(jeu, a, "UPDATE comptes_bancaires SET solde_max = 10 WHERE dossier = 'D-1'", erreur=chk)
    refuse(jeu, a, "INSERT INTO virements_suivis (dossier, compte_de, compte_vers, montant, date_virement) VALUES ('D-1', '512', '512', 100, '2026-11-25')", erreur=chk)
    refuse(jeu, a, "INSERT INTO tresorerie_previsions (dossier, compte, libelle, sens, montant, date_prevue, jusqu_au) VALUES ('D-1', '512', 'x', 'dec', 1, '2026-12-05', '2027-01-01')", erreur=chk)


def test_migration_015_rejouable(jeu):
    import pathlib
    texte = (pathlib.Path(__file__).parent.parent.parent / "migrations" / "015_comptabilite_et_tresorerie_previsionnelle.sql").read_text(encoding="utf-8")
    cur = jeu.cursor()
    cur.execute(texte)
    cur.execute("SELECT count(*) FROM fees_regles WHERE dossier = '*'")
    assert cur.fetchone()[0] == 6
