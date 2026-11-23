"""
Lot 13 - droits sur les données publiées et les ajustements partagés (décision 0007).

Comme au lot 12 : base PostgreSQL temporaire construite depuis migrations/ (GitHub Actions), personne
connectée simulée par le rôle 'authenticated' et l'adresse dans 'request.jwt.claims'. Chaque test est
annulé à la fin. Sans base de test (ZENITUDE_ENV=test et DATABASE_URL), ces tests sont ignorés.
"""
import json
import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]

ADMIN = "admin@exemple.invalid"
COLLAB = "collab@exemple.invalid"
LECTURE = "lecture@exemple.invalid"


@pytest.fixture
def db():
    if os.environ.get("ZENITUDE_ENV") != "test":
        pytest.skip("ZENITUDE_ENV=test absent : tests réservés à la base de test.")
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL absent.")
    conn = psycopg.connect(url)
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.ajustements') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migration 004 non appliquée sur la base de test.")
        cur.execute("SELECT (SELECT count(*) FROM profils) + (SELECT count(*) FROM residences) + (SELECT count(*) FROM ajustements)")
        if cur.fetchone()[0] != 0:
            pytest.fail("La base de test doit être vide avant les tests.")
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def jeu(db):
    """Trois profils, trois résidences (dossiers D-1 à D-3), groupe GRP-A = RES-001 et RES-002.
    Collaborateur : RES-001. Lecteur : GRP-A. Données publiées pour les trois résidences."""
    cur = db.cursor()
    cur.executemany("INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
                    [(ADMIN, "Administrateur fictif", "administrateur"),
                     (COLLAB, "Collaborateur fictif", "collaborateur"),
                     (LECTURE, "Lecteur fictif", "lecture")])
    cur.executemany("INSERT INTO residences (id, libelle, dossier_pennylane) VALUES (%s, %s, %s)",
                    [("RES-001", "Fictive 1", "D-1"), ("RES-002", "Fictive 2", "D-2"), ("RES-003", "Fictive 3", "D-3")])
    cur.execute("INSERT INTO groupes (id, libelle) VALUES ('GRP-A', 'Groupe fictif A')")
    cur.execute("INSERT INTO residence_groupe VALUES ('RES-001', 'GRP-A'), ('RES-002', 'GRP-A')")
    cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", (COLLAB,))
    cur.execute("INSERT INTO parcs (utilisateur_email, groupe_id) VALUES (%s, 'GRP-A')", (LECTURE,))
    cur.execute("INSERT INTO donnees_communes (id, contenu, empreinte) VALUES ('SITE', %s, 'x')", (Jsonb({"kpi": []}),))
    for r in ("RES-001", "RES-002", "RES-003"):
        cur.execute("INSERT INTO donnees_residences (residence_id, contenu, empreinte) VALUES (%s, %s, 'x')",
                    (r, Jsonb({"residence": {"code": r}})))
    return db


def connecte(conn, email):
    cur = conn.cursor()
    if email is None:
        cur.execute("SET ROLE anon")
        cur.execute("SELECT set_config('request.jwt.claims', '', true)")
    else:
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps({"email": email, "role": "authenticated"}),))
    return cur


def en_superviseur(conn):
    cur = conn.cursor()
    cur.execute("RESET ROLE")
    cur.execute("SELECT set_config('request.jwt.claims', '', true)")
    return cur


def liste(cur, sql, params=None):
    cur.execute(sql, params)
    return sorted(str(r[0]) for r in cur.fetchall())


def refuse(conn, cur, sql, params=None, erreur=errors.InsufficientPrivilege):
    with pytest.raises(erreur):
        with conn.transaction():
            cur.execute(sql, params)


def creer_ajustement(cur, tous, dossiers, libelle="Fictif"):
    cur.execute("INSERT INTO ajustements (portee_tous, dossiers, contenu) VALUES (%s, %s, %s) RETURNING id",
                (tous, dossiers, Jsonb({"libelle": libelle, "compte": "65800000P", "mode": "regle"})))
    return cur.fetchone()[0]


# --- Données publiées ----------------------------------------------------------

def test_donnees_lues_selon_le_parc(jeu):
    sql = "SELECT residence_id FROM donnees_residences"
    assert liste(connecte(jeu, ADMIN), sql) == ["RES-001", "RES-002", "RES-003"]
    assert liste(connecte(jeu, COLLAB), sql) == ["RES-001"]
    assert liste(connecte(jeu, LECTURE), sql) == ["RES-001", "RES-002"]
    assert liste(connecte(jeu, "inconnu@exemple.invalid"), sql) == []


def test_donnees_communes_reservees_aux_profils_actifs(jeu):
    assert liste(connecte(jeu, LECTURE), "SELECT id FROM donnees_communes") == ["SITE"]
    assert liste(connecte(jeu, "inconnu@exemple.invalid"), "SELECT id FROM donnees_communes") == []
    en_superviseur(jeu).execute("UPDATE profils SET actif = false WHERE email = %s", (COLLAB,))
    assert liste(connecte(jeu, COLLAB), "SELECT residence_id FROM donnees_residences") == []


def test_personne_non_connectee_refusee(jeu):
    cur = connecte(jeu, None)
    for t in ("donnees_communes", "donnees_residences", "ajustements", "comptes_simules"):
        refuse(jeu, cur, f"SELECT * FROM {t}")


def test_personne_n_ecrit_les_donnees_publiees(jeu):
    for email in (ADMIN, COLLAB, LECTURE):
        cur = connecte(jeu, email)
        refuse(jeu, cur, "UPDATE donnees_residences SET empreinte = 'y'")
        refuse(jeu, cur, "DELETE FROM donnees_communes")
        refuse(jeu, cur, "INSERT INTO donnees_communes (id, contenu, empreinte) VALUES ('SITE', '{}', 'y')")


def test_donnee_marquee_reelle_refusee(jeu):
    cur = en_superviseur(jeu)
    refuse(jeu, cur, "UPDATE donnees_residences SET fictif = false WHERE residence_id = 'RES-001'",
           erreur=errors.CheckViolation)


# --- Ajustements : création -----------------------------------------------------

def test_collaborateur_cree_sur_son_parc(jeu):
    cur = connecte(jeu, COLLAB)
    i = creer_ajustement(cur, False, ["D-1"])
    cur.execute("SELECT cree_par, modifie_par, actif FROM ajustements WHERE id = %s", (i,))
    assert cur.fetchone() == (COLLAB, COLLAB, True)


def test_collaborateur_ne_cree_pas_hors_parc_ni_pour_tous(jeu):
    cur = connecte(jeu, COLLAB)
    refuse(jeu, cur, "INSERT INTO ajustements (dossiers, contenu) VALUES ('{D-2}', '{}')")
    refuse(jeu, cur, "INSERT INTO ajustements (dossiers, contenu) VALUES ('{D-1,D-2}', '{}')")
    refuse(jeu, cur, "INSERT INTO ajustements (portee_tous, contenu) VALUES (true, '{}')")
    refuse(jeu, cur, "INSERT INTO ajustements (dossiers, contenu) VALUES ('{INCONNU}', '{}')")


def test_lecteur_ne_cree_rien(jeu):
    cur = connecte(jeu, LECTURE)
    refuse(jeu, cur, "INSERT INTO ajustements (dossiers, contenu) VALUES ('{D-1}', '{}')")
    refuse(jeu, cur, "INSERT INTO comptes_simules (numero, libelle) VALUES ('65800000P', 'X')")


def test_auteur_non_falsifiable(jeu):
    cur = connecte(jeu, COLLAB)
    refuse(jeu, cur, "INSERT INTO ajustements (dossiers, contenu, cree_par) VALUES ('{D-1}', '{}', %s)", (ADMIN,))


def test_administrateur_cree_pour_toutes_les_residences(jeu):
    creer_ajustement(connecte(jeu, ADMIN), True, [])


def test_portee_incoherente_refusee(jeu):
    cur = en_superviseur(jeu)
    refuse(jeu, cur, "INSERT INTO ajustements (portee_tous, dossiers, contenu) VALUES (true, '{D-1}', '{}')",
           erreur=errors.CheckViolation)
    refuse(jeu, cur, "INSERT INTO ajustements (portee_tous, dossiers, contenu) VALUES (false, '{}', '{}')",
           erreur=errors.CheckViolation)


# --- Ajustements : lecture --------------------------------------------------------

def test_visibilite_des_ajustements(jeu):
    adm = connecte(jeu, ADMIN)
    tous = creer_ajustement(adm, True, [], "Pour tous")
    sur2 = creer_ajustement(adm, False, ["D-2"], "Sur D-2")
    sur13 = creer_ajustement(adm, False, ["D-1", "D-3"], "Sur D-1 et D-3")
    sql = "SELECT id FROM ajustements"
    assert liste(connecte(jeu, ADMIN), sql) == sorted(str(i) for i in (tous, sur2, sur13))
    assert liste(connecte(jeu, COLLAB), sql) == [str(tous)]
    assert liste(connecte(jeu, LECTURE), sql) == sorted(str(i) for i in (tous, sur2))
    assert liste(connecte(jeu, "inconnu@exemple.invalid"), sql) == []


# --- Ajustements : modification et suppression -------------------------------------

def test_collaborateur_modifie_et_supprime_ses_ajustements(jeu):
    cur = connecte(jeu, COLLAB)
    i = creer_ajustement(cur, False, ["D-1"])
    cur.execute("UPDATE ajustements SET actif = false, rev = 2 WHERE id = %s", (i,))
    assert cur.rowcount == 1
    cur.execute("DELETE FROM ajustements WHERE id = %s", (i,))
    assert cur.rowcount == 1


def test_collaborateur_n_elargit_pas_hors_parc(jeu):
    cur = connecte(jeu, COLLAB)
    i = creer_ajustement(cur, False, ["D-1"])
    refuse(jeu, cur, "UPDATE ajustements SET dossiers = '{D-1,D-2}' WHERE id = %s", (i,))
    refuse(jeu, cur, "UPDATE ajustements SET portee_tous = true, dossiers = '{}' WHERE id = %s", (i,))


def test_collaborateur_ne_touche_pas_un_ajustement_pour_tous(jeu):
    i = creer_ajustement(connecte(jeu, ADMIN), True, [])
    cur = connecte(jeu, COLLAB)
    cur.execute("UPDATE ajustements SET actif = false WHERE id = %s", (i,))
    assert cur.rowcount == 0
    cur.execute("DELETE FROM ajustements WHERE id = %s", (i,))
    assert cur.rowcount == 0


def test_lecteur_ne_modifie_rien(jeu):
    i = creer_ajustement(connecte(jeu, ADMIN), False, ["D-1"])
    cur = connecte(jeu, LECTURE)
    cur.execute("UPDATE ajustements SET actif = false WHERE id = %s", (i,))
    assert cur.rowcount == 0
    cur.execute("DELETE FROM ajustements WHERE id = %s", (i,))
    assert cur.rowcount == 0


def test_trace_de_la_derniere_modification(jeu):
    i = creer_ajustement(connecte(jeu, COLLAB), False, ["D-1"])
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE ajustements SET actif = false, cree_par = 'pirate@exemple.invalid' WHERE id = %s", (i,))
    cur.execute("SELECT cree_par, modifie_par FROM ajustements WHERE id = %s", (i,))
    assert cur.fetchone() == (COLLAB, ADMIN)


# --- Comptes simulés -------------------------------------------------------------

def test_comptes_simules(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("INSERT INTO comptes_simules (numero, libelle) VALUES ('65800000P', 'Provision fictive')")
    connecte(jeu, ADMIN).execute("INSERT INTO comptes_simules (numero, libelle) VALUES ('70610000P', 'Hébergement provision')")
    assert liste(connecte(jeu, LECTURE), "SELECT numero FROM comptes_simules") == ["65800000P", "70610000P"]
    cur = connecte(jeu, COLLAB)
    cur.execute("DELETE FROM comptes_simules WHERE numero = '70610000P'")
    assert cur.rowcount == 0
    cur.execute("DELETE FROM comptes_simules WHERE numero = '65800000P'")
    assert cur.rowcount == 1
    refuse(jeu, connecte(jeu, ADMIN), "INSERT INTO comptes_simules (numero, libelle) VALUES ('12345', 'Mauvais')",
           erreur=errors.CheckViolation)


# --- Démonstration (scripts/donnees_test.sql) -------------------------------------

def test_demonstration_nettoyee(db):
    db.cursor().execute((RACINE / "scripts" / "donnees_test.sql").read_text(encoding="utf-8"))
    admin = liste(connecte(db, "raphael.bracq@zenitude-groupe.com"), "SELECT id FROM residences")
    collab = liste(connecte(db, "benjamin.gagneur@zenitude-groupe.com"), "SELECT id FROM residences")
    assert admin == [f"RES-00{i}" for i in range(1, 9)]
    assert collab == ["RES-003", "RES-004", "RES-005"]
    cur = en_superviseur(db)
    cur.execute("SELECT count(*) FROM residences WHERE id IN ('RES-901', 'RES-902') OR NOT fictif")
    assert cur.fetchone()[0] == 0
