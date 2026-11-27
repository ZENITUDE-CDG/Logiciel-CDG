"""Lot 31 - droits et contrôles de la migration 020 (sociétés, noms et codes, classements, groupes, journal).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB, LECT, AUTRE = "admin@exemple.invalid", "collab@exemple.invalid", "lect@exemple.invalid", "autre@exemple.invalid"


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.residence_identifiants') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 020 non appliquée sur la base de test.")
        cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                        [(ADMIN, "A", "administrateur"), (COLLAB, "C", "collaborateur"), (LECT, "L", "lecture"), (AUTRE, "O", "collaborateur")])
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


def test_societe_creation_archivage_et_traces(jeu):
    c = connecte(jeu, COLLAB)
    refuse(jeu, c, "INSERT INTO residences (id, libelle) VALUES ('RES-009', 'X')")
    refuse(jeu, c, "UPDATE residences SET archivee = true WHERE id = 'RES-001'")
    refuse(jeu, c, "UPDATE residences SET dossier_pennylane = 'D-9' WHERE id = 'RES-001'")
    c.execute("UPDATE residences SET nom = 'Nom d''usage', raison_sociale = 'SAS F1', siren = '123456789' WHERE id = 'RES-001' RETURNING modifie_par")
    assert c.fetchone()[0] == COLLAB
    refuse(jeu, c, "UPDATE residences SET siren = '12' WHERE id = 'RES-001'", erreur=errors.CheckViolation)
    c.execute("UPDATE residences SET nom = 'Pirate' WHERE id = 'RES-002'")
    assert c.rowcount == 0  # hors parc
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO residences (id, libelle, nom, cree_par) VALUES ('RES-009', 'Nouvelle', 'Nouvelle', 'pirate@exemple.invalid') RETURNING cree_par")
    assert a.fetchone()[0] == ADMIN
    a.execute("UPDATE residences SET archivee = true WHERE id = 'RES-009' RETURNING archivee_par, archivee_le IS NOT NULL")
    assert a.fetchone() == (ADMIN, True)
    a.execute("UPDATE residences SET archivee = false WHERE id = 'RES-009' RETURNING archivee_par, archivee_le")
    assert a.fetchone() == (None, None)
    a.execute("SELECT action FROM societes_journal WHERE objet = 'societe' AND residence_id = 'RES-009' ORDER BY id")
    assert [x[0] for x in a.fetchall()] == ["insert", "archivage", "restauration"]
    a.execute("SELECT par, detail FROM societes_journal WHERE residence_id = 'RES-001' AND action = 'update'")
    par, detail = a.fetchone()
    assert par == COLLAB and detail["siren"] == [None, "123456789"] and "modifie_le" not in detail


def test_identifiants_parc_et_unicite(jeu):
    c = connecte(jeu, COLLAB)
    c.execute("INSERT INTO residence_identifiants (residence_id, libelle, code) VALUES ('RES-001', 'Mews', 'TRT') RETURNING cree_par")
    assert c.fetchone()[0] == COLLAB
    refuse(jeu, c, "INSERT INTO residence_identifiants (residence_id, libelle, code) VALUES ('RES-002', 'Pennylane', 'YTR')", erreur=errors.InsufficientPrivilege)
    refuse(jeu, c, "INSERT INTO residence_identifiants (residence_id, libelle, code) VALUES ('RES-001', 'Mews', ' TRT')", erreur=errors.CheckViolation)
    a = connecte(jeu, ADMIN)
    refuse(jeu, a, "INSERT INTO residence_identifiants (residence_id, libelle, code) VALUES ('RES-002', 'mews', 'trt')", erreur=errors.UniqueViolation)
    a.execute("INSERT INTO residence_identifiants (residence_id, libelle, code) VALUES ('RES-002', 'Pennylane', 'TRT')")
    l = connecte(jeu, LECT)
    l.execute("SELECT code FROM residence_identifiants ORDER BY id")
    assert [x[0] for x in l.fetchall()] == ["TRT"]  # seulement RES-001
    refuse(jeu, l, "INSERT INTO residence_identifiants (residence_id, libelle, code) VALUES ('RES-001', 'Silae', 'S1')")
    o = connecte(jeu, AUTRE)
    o.execute("SELECT count(*) FROM residence_identifiants")
    assert o.fetchone()[0] == 0
    o.execute("SELECT count(*) FROM societes_journal")
    assert o.fetchone()[0] == 0
    refuse(jeu, o, "INSERT INTO societes_journal (objet, action) VALUES ('societe', 'insert')")


def test_classements_exclusifs_et_groupes(jeu):
    c = connecte(jeu, COLLAB)
    refuse(jeu, c, "INSERT INTO classements (id, libelle) VALUES ('CL-RM', 'RM')")
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO classements (id, libelle) VALUES ('CL-RM', 'RM')")
    a.execute("INSERT INTO groupes (id, libelle, classement_id) VALUES ('GRP-N', 'RM Nord', 'CL-RM'), ('GRP-S', 'RM Sud', 'CL-RM'), ('GRP-L', 'Libre', NULL)")
    a.execute("INSERT INTO residence_groupe VALUES ('RES-001', 'GRP-N'), ('RES-001', 'GRP-L')")
    refuse(jeu, a, "INSERT INTO residence_groupe VALUES ('RES-001', 'GRP-S')", erreur=errors.CheckViolation)
    refuse(jeu, a, "UPDATE groupes SET classement_id = 'CL-RM' WHERE id = 'GRP-L'", erreur=errors.CheckViolation)
    a.execute("UPDATE classements SET exclusif = false WHERE id = 'CL-RM'")
    a.execute("INSERT INTO residence_groupe VALUES ('RES-001', 'GRP-S')")
    a.execute("DELETE FROM classements WHERE id = 'CL-RM'")
    a.execute("SELECT count(*) FROM groupes WHERE classement_id IS NULL AND id IN ('GRP-N', 'GRP-S')")
    assert a.fetchone()[0] == 2  # groupes conservés, sans classement
    c = connecte(jeu, COLLAB)
    c.execute("SELECT count(*) FROM classements")
    assert c.fetchone()[0] == 0
    a = connecte(jeu, ADMIN)
    a.execute("SELECT objet, action FROM societes_journal WHERE objet IN ('classement', 'appartenance') ORDER BY id")
    assert ("appartenance", "insert") in a.fetchall()


def test_groupe_du_parc_non_supprimable(jeu):
    a = connecte(jeu, ADMIN)
    a.execute("INSERT INTO groupes (id, libelle) VALUES ('GRP-P', 'Parc')")
    a.execute("INSERT INTO parcs (utilisateur_email, groupe_id) VALUES (%s, 'GRP-P')", (AUTRE,))
    refuse(jeu, a, "DELETE FROM groupes WHERE id = 'GRP-P'", erreur=errors.CheckViolation)
    a.execute("DELETE FROM parcs WHERE groupe_id = 'GRP-P'")
    a.execute("DELETE FROM groupes WHERE id = 'GRP-P'")
    assert a.rowcount == 1
