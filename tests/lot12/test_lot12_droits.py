"""
Lot 12 - droits d'accès vérifiés dans la base (décisions 0004 et 0006).

Ces tests tournent automatiquement sur GitHub (onglet Actions) contre une base
PostgreSQL temporaire, créée à partir de migrations/ puis jetée. Ils ne touchent
jamais Supabase. Chaque test est annulé à la fin : aucune donnée n'est conservée.

La personne connectée est simulée exactement comme sur Supabase : rôle PostgreSQL
'authenticated' (ou 'anon') et adresse e-mail dans 'request.jwt.claims'.

Sans base de test (ZENITUDE_ENV=test et DATABASE_URL), ces tests sont ignorés.
"""
import json
import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

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
        cur.execute("SELECT to_regclass('public.parcs') IS NOT NULL")
        if not cur.fetchone()[0]:
            pytest.fail("Migrations non appliquées sur la base de test.")
        cur.execute("SELECT (SELECT count(*) FROM profils) + (SELECT count(*) FROM residences)")
        if cur.fetchone()[0] != 0:
            pytest.fail("La base de test doit être vide avant les tests.")
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def jeu(db):
    """Trois profils fictifs, trois résidences, un groupe (RES-001 et RES-002)."""
    cur = db.cursor()
    cur.executemany(
        "INSERT INTO profils (email, nom, role) VALUES (%s, %s, %s)",
        [(ADMIN, "Administrateur fictif", "administrateur"),
         (COLLAB, "Collaborateur fictif", "collaborateur"),
         (LECTURE, "Lecteur fictif", "lecture")],
    )
    cur.executemany(
        "INSERT INTO residences (id, libelle) VALUES (%s, %s)",
        [("RES-001", "Résidence fictive 1"), ("RES-002", "Résidence fictive 2"),
         ("RES-003", "Résidence fictive 3")],
    )
    cur.execute("INSERT INTO groupes (id, libelle) VALUES ('GRP-A', 'Groupe fictif A')")
    cur.execute("INSERT INTO residence_groupe VALUES ('RES-001', 'GRP-A'), ('RES-002', 'GRP-A')")
    # Collaborateur : parc restreint à une résidence. Lecteur : parc = le groupe.
    cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-001')", (COLLAB,))
    cur.execute("INSERT INTO parcs (utilisateur_email, groupe_id) VALUES (%s, 'GRP-A')", (LECTURE,))
    return db


def connecte(conn, email):
    """Simule une requête du site : personne connectée avec cette adresse, ou anonyme."""
    cur = conn.cursor()
    if email is None:
        cur.execute("SET ROLE anon")
        cur.execute("SELECT set_config('request.jwt.claims', '', true)")
    else:
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps({"email": email, "role": "authenticated"}),))
    return cur


def liste(cur, sql):
    cur.execute(sql)
    return sorted(str(r[0]) for r in cur.fetchall())


def refuse(conn, cur, sql, params=None):
    """L'opération doit être refusée par la base (droit insuffisant)."""
    with pytest.raises(errors.InsufficientPrivilege):
        with conn.transaction():
            cur.execute(sql, params)


# --- Lecture --------------------------------------------------------------

def test_administrateur_voit_tout(jeu):
    cur = connecte(jeu, ADMIN)
    assert liste(cur, "SELECT id FROM residences") == ["RES-001", "RES-002", "RES-003"]
    assert liste(cur, "SELECT id FROM groupes") == ["GRP-A"]
    assert liste(cur, "SELECT email FROM profils") == sorted([ADMIN, COLLAB, LECTURE])
    assert len(liste(cur, "SELECT id FROM parcs")) == 2


def test_collaborateur_ne_voit_que_son_parc(jeu):
    cur = connecte(jeu, COLLAB)
    assert liste(cur, "SELECT id FROM residences") == ["RES-001"]
    assert liste(cur, "SELECT id FROM groupes") == []


def test_lecteur_voit_les_residences_de_son_groupe(jeu):
    cur = connecte(jeu, LECTURE)
    assert liste(cur, "SELECT id FROM residences") == ["RES-001", "RES-002"]
    assert liste(cur, "SELECT id FROM groupes") == ["GRP-A"]


def test_residence_ajoutee_plus_tard_au_groupe_devient_visible(jeu):
    jeu.cursor().execute("INSERT INTO residence_groupe VALUES ('RES-003', 'GRP-A')")
    cur = connecte(jeu, LECTURE)
    assert liste(cur, "SELECT id FROM residences") == ["RES-001", "RES-002", "RES-003"]


def test_chacun_ne_voit_que_son_profil_et_son_parc(jeu):
    assert liste(connecte(jeu, COLLAB), "SELECT email FROM profils") == [COLLAB]
    assert liste(connecte(jeu, LECTURE), "SELECT utilisateur_email FROM parcs") == [LECTURE]


def test_adresse_en_majuscules_reconnue(jeu):
    cur = connecte(jeu, COLLAB.upper())
    assert liste(cur, "SELECT id FROM residences") == ["RES-001"]


def test_adresse_inconnue_ne_voit_rien(jeu):
    cur = connecte(jeu, "inconnu@exemple.invalid")
    assert liste(cur, "SELECT id FROM residences") == []
    assert liste(cur, "SELECT email FROM profils") == []


def test_compte_desactive_ne_voit_plus_rien(jeu):
    jeu.cursor().execute("UPDATE profils SET actif = false WHERE email = %s", (COLLAB,))
    cur = connecte(jeu, COLLAB)
    assert liste(cur, "SELECT id FROM residences") == []


def test_personne_non_connectee_refusee(jeu):
    cur = connecte(jeu, None)
    refuse(jeu, cur, "SELECT id FROM residences")
    refuse(jeu, cur, "SELECT email FROM profils")


# --- Modification ---------------------------------------------------------

def test_administrateur_modifie_toute_residence(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE residences SET libelle = 'Modifié' WHERE id = 'RES-003'")
    assert cur.rowcount == 1


def test_collaborateur_modifie_son_parc(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("UPDATE residences SET libelle = 'Modifié' WHERE id = 'RES-001'")
    assert cur.rowcount == 1


def test_collaborateur_ne_modifie_pas_hors_parc(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("UPDATE residences SET libelle = 'Modifié' WHERE id = 'RES-002'")
    assert cur.rowcount == 0


def test_lecteur_ne_modifie_rien(jeu):
    cur = connecte(jeu, LECTURE)
    cur.execute("UPDATE residences SET libelle = 'Modifié' WHERE id = 'RES-001'")
    assert cur.rowcount == 0
    cur.execute("UPDATE groupes SET libelle = 'Modifié' WHERE id = 'GRP-A'")
    assert cur.rowcount == 0


def test_collaborateur_ne_change_pas_son_role(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("UPDATE profils SET role = 'administrateur' WHERE email = %s", (COLLAB,))
    assert cur.rowcount == 0


# --- Administration (création de comptes, groupes, parcs) -----------------

def test_seul_l_administrateur_cree_utilisateurs_groupes_residences(jeu):
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        refuse(jeu, cur, "INSERT INTO profils (email, nom, role) VALUES ('x@exemple.invalid', 'X', 'lecture')")
        refuse(jeu, cur, "INSERT INTO groupes (id, libelle) VALUES ('GRP-B', 'B')")
        refuse(jeu, cur, "INSERT INTO residences (id, libelle) VALUES ('RES-009', 'Nouvelle')")
    cur = connecte(jeu, ADMIN)
    cur.execute("INSERT INTO profils (email, nom, role) VALUES ('x@exemple.invalid', 'X', 'lecture')")
    cur.execute("INSERT INTO groupes (id, libelle) VALUES ('GRP-B', 'B')")
    cur.execute("INSERT INTO residences (id, libelle) VALUES ('RES-009', 'Nouvelle')")
    cur.execute("INSERT INTO residence_groupe VALUES ('RES-009', 'GRP-B')")


def test_personne_ne_s_attribue_un_parc_sauf_l_administrateur(jeu):
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        refuse(jeu, cur, "INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-003')", (email,))
    cur = connecte(jeu, ADMIN)
    cur.execute("INSERT INTO parcs (utilisateur_email, residence_id) VALUES (%s, 'RES-003')", (COLLAB,))
    assert liste(connecte(jeu, COLLAB), "SELECT id FROM residences") == ["RES-001", "RES-003"]


def test_collaborateur_ne_rattache_pas_une_residence_a_un_groupe(jeu):
    cur = connecte(jeu, COLLAB)
    refuse(jeu, cur, "INSERT INTO residence_groupe VALUES ('RES-001', 'GRP-A')")


# --- Intégrité ------------------------------------------------------------

def test_identifiant_de_residence_invalide_refuse(jeu):
    with pytest.raises(errors.CheckViolation):
        with jeu.transaction():
            jeu.cursor().execute("INSERT INTO residences (id, libelle) VALUES ('res 4', 'Mauvais')")


def test_parc_residence_et_groupe_a_la_fois_refuse(jeu):
    with pytest.raises(errors.CheckViolation):
        with jeu.transaction():
            jeu.cursor().execute(
                "INSERT INTO parcs (utilisateur_email, residence_id, groupe_id) VALUES (%s, 'RES-001', 'GRP-A')",
                (COLLAB,))


# --- Démonstration : les deux comptes réels voient des parcs différents ---

def test_demonstration_deux_parcs_differents(db):
    db.cursor().execute((RACINE / "scripts" / "donnees_test.sql").read_text(encoding="utf-8"))
    admin = liste(connecte(db, "raphael.bracq@zenitude-groupe.com"), "SELECT id FROM residences")
    collab = liste(connecte(db, "benjamin.gagneur@zenitude-groupe.com"), "SELECT id FROM residences")
    # Depuis le lot 13 (nettoyage) : les huit résidences de démonstration ; Benjamin a le groupe seniors.
    assert admin == [f"RES-00{i}" for i in range(1, 9)]
    assert collab == ["RES-003", "RES-004", "RES-005"]
