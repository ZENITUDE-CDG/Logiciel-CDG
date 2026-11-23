"""
Tests des droits d'accès (lot 12, décision 0004).

Ils vérifient, dans la base de TEST, que la base refuse ce qu'un utilisateur
ne doit pas voir ou modifier. Chaque test s'exécute dans une transaction
annulée à la fin : aucune donnée n'est conservée.

Lancement :  ZENITUDE_ENV=test python -m pytest tests/lot12 -v
Sans ZENITUDE_ENV=test ou sans DATABASE_URL, les tests sont ignorés
(la suite habituelle reste verte sur un poste sans base).
"""
import os
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ADMIN = uuid.UUID("00000000-0000-4000-8000-00000000a001")
COLLAB = uuid.UUID("00000000-0000-4000-8000-00000000a002")
LECTURE = uuid.UUID("00000000-0000-4000-8000-00000000a003")


@pytest.fixture
def db():
    if os.environ.get("ZENITUDE_ENV") != "test":
        pytest.skip("ZENITUDE_ENV=test absent : ces tests ne tournent que sur la base de test.")
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL absent du fichier .env.")
    conn = psycopg.connect(url)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT to_regclass('public.parcs') IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_utilisateur')"
        )
        if not cur.fetchone()[0]:
            pytest.fail("Migrations 001 à 003 non appliquées sur la base de test.")
        cur.execute("SELECT (SELECT count(*) FROM profils) + (SELECT count(*) FROM residences)")
        if cur.fetchone()[0] != 0:
            pytest.fail("La base de test contient déjà des données : elle doit être vide.")
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def jeu(db):
    """Trois profils fictifs, trois résidences, un groupe. Annulé à la fin du test."""
    cur = db.cursor()
    cur.executemany(
        "INSERT INTO profils (id, email, nom, role) VALUES (%s, %s, %s, %s)",
        [
            (ADMIN, "admin@exemple.invalid", "Administrateur fictif", "administrateur"),
            (COLLAB, "collab@exemple.invalid", "Collaborateur fictif", "collaborateur"),
            (LECTURE, "lecture@exemple.invalid", "Lecteur fictif", "lecture"),
        ],
    )
    cur.executemany(
        "INSERT INTO residences (id, libelle) VALUES (%s, %s)",
        [("RES-001", "Résidence fictive 1"), ("RES-002", "Résidence fictive 2"),
         ("RES-003", "Résidence fictive 3")],
    )
    cur.execute("INSERT INTO groupes (id, libelle) VALUES ('GRP-A', 'Groupe fictif A')")
    cur.executemany(
        "INSERT INTO residence_groupe (residence_id, groupe_id) VALUES (%s, 'GRP-A')",
        [("RES-001",), ("RES-002",)],
    )
    cur.execute("INSERT INTO parcs (utilisateur_id, residence_id) VALUES (%s, 'RES-001')", (COLLAB,))
    cur.execute("INSERT INTO parcs (utilisateur_id, groupe_id) VALUES (%s, 'GRP-A')", (LECTURE,))
    return db


def connecte(db, utilisateur):
    """Se connecte comme le ferait l'application : rôle restreint + identité."""
    cur = db.cursor()
    cur.execute("SET ROLE app_utilisateur")
    valeur = "" if utilisateur is None else str(utilisateur)
    cur.execute("SELECT set_config('app.utilisateur_id', %s, true)", (valeur,))
    return cur


def ids(cur, sql):
    cur.execute(sql)
    return sorted(str(r[0]) for r in cur.fetchall())


# --- Lecture -------------------------------------------------------------

def test_administrateur_voit_tout(jeu):
    cur = connecte(jeu, ADMIN)
    assert ids(cur, "SELECT id FROM residences") == ["RES-001", "RES-002", "RES-003"]
    assert ids(cur, "SELECT id FROM groupes") == ["GRP-A"]
    assert len(ids(cur, "SELECT id FROM profils")) == 3


def test_collaborateur_ne_voit_que_son_parc(jeu):
    cur = connecte(jeu, COLLAB)
    assert ids(cur, "SELECT id FROM residences") == ["RES-001"]
    assert ids(cur, "SELECT id FROM groupes") == []


def test_lecteur_voit_le_groupe_de_son_parc(jeu):
    cur = connecte(jeu, LECTURE)
    assert ids(cur, "SELECT id FROM residences") == ["RES-001", "RES-002"]
    assert ids(cur, "SELECT id FROM groupes") == ["GRP-A"]


def test_residence_ajoutee_au_groupe_devient_visible(jeu):
    jeu.cursor().execute(
        "INSERT INTO residence_groupe (residence_id, groupe_id) VALUES ('RES-003', 'GRP-A')"
    )
    cur = connecte(jeu, LECTURE)
    assert ids(cur, "SELECT id FROM residences") == ["RES-001", "RES-002", "RES-003"]


def test_chacun_ne_voit_que_son_profil(jeu):
    assert ids(connecte(jeu, COLLAB), "SELECT id FROM profils") == [str(COLLAB)]
    assert ids(connecte(jeu, LECTURE), "SELECT id FROM profils") == [str(LECTURE)]


def test_sans_identifiant_aucun_acces(jeu):
    cur = connecte(jeu, None)
    assert ids(cur, "SELECT id FROM residences") == []


# --- Modification --------------------------------------------------------

def test_administrateur_modifie_tout(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE residences SET libelle = 'Modifié' WHERE id = 'RES-002'")
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


def test_collaborateur_ne_modifie_pas_les_groupes(jeu):
    cur = connecte(jeu, COLLAB)
    cur.execute("UPDATE groupes SET libelle = 'Modifié' WHERE id = 'GRP-A'")
    assert cur.rowcount == 0


# --- Création et droits d'administration ---------------------------------

def test_collaborateur_ne_cree_pas_de_residence(jeu):
    cur = connecte(jeu, COLLAB)
    with pytest.raises(errors.InsufficientPrivilege):
        with jeu.transaction():
            cur.execute("INSERT INTO residences (id, libelle) VALUES ('RES-009', 'Nouvelle')")


def test_collaborateur_ne_peut_pas_se_donner_un_parc(jeu):
    cur = connecte(jeu, COLLAB)
    with pytest.raises(errors.InsufficientPrivilege):
        with jeu.transaction():
            cur.execute(
                "INSERT INTO parcs (utilisateur_id, residence_id) VALUES (%s, 'RES-002')",
                (COLLAB,),
            )


def test_lecteur_ne_peut_pas_se_donner_un_parc(jeu):
    cur = connecte(jeu, LECTURE)
    with pytest.raises(errors.InsufficientPrivilege):
        with jeu.transaction():
            cur.execute(
                "INSERT INTO parcs (utilisateur_id, residence_id) VALUES (%s, 'RES-002')",
                (LECTURE,),
            )


# --- Intégrité -----------------------------------------------------------

def test_identifiant_de_residence_refuse(jeu):
    cur = jeu.cursor()
    with pytest.raises(errors.CheckViolation):
        with jeu.transaction():
            cur.execute("INSERT INTO residences (id, libelle) VALUES ('res 4', 'Mauvais')")
