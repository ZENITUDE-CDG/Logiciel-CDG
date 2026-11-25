"""Lot 19 - droits de la migration 011 (base PostgreSQL de test, données fictives).
Ignorés sans base de test (ZENITUDE_ENV=test et DATABASE_URL).

- jeton chiffré jamais relisible par une personne connectée, colonnes de résultat jamais écrites par elle ;
- enregistrement d'un jeton : auteur, échéance et état « à tester » posés par la base ;
- une société Pennylane rattachée à une seule résidence ;
- clé publique, historique des dépôts : administrateurs ; statut des mois : lecture selon le parc ;
- code Mews modifiable par un administrateur seulement ; montants CA signés, quantités positives.
"""
import json
import os

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

ADMIN, COLLAB, LECTURE = "admin@exemple.invalid", "collab@exemple.invalid", "lecture@exemple.invalid"
CHIFFRE = "v1." + "A" * 300
EMPREINTE = "a" * 64


@pytest.fixture
def jeu():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.connexions_pennylane') IS NOT NULL")
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


def enregistrer(cur, dossier="D-1", duree="12"):
    cur.execute("INSERT INTO connexions_pennylane (dossier, jeton_chiffre, empreinte_cle, fin_jeton, duree) "
                "VALUES (%s, %s, %s, 'WXYZ', %s) RETURNING dossier", (dossier, CHIFFRE, EMPREINTE, duree))


def test_jeton_chiffre_jamais_relisible_et_trace(jeu):
    cur = connecte(jeu, ADMIN)
    enregistrer(cur)
    refuse(jeu, cur, "SELECT jeton_chiffre FROM connexions_pennylane")
    refuse(jeu, cur, "SELECT * FROM connexions_pennylane")
    cur.execute("SELECT etat, enregistre_par, expire_le, (now() AT TIME ZONE 'Europe/Paris')::date + interval '12 months' "
                "FROM connexions_pennylane WHERE dossier = 'D-1'")
    etat, par, expire, attendu = cur.fetchone()
    assert (etat, par) == ("a_tester", ADMIN) and expire == attendu.date()
    # Les colonnes de résultat ne s'écrivent pas depuis la page
    refuse(jeu, cur, "UPDATE connexions_pennylane SET etat = 'connectee' WHERE dossier = 'D-1'")
    refuse(jeu, cur, "UPDATE connexions_pennylane SET societe_attendue = '1' WHERE dossier = 'D-1'")
    # Seul GitHub Actions (clé secrète) lit le jeton et écrit le résultat
    s = service(jeu)
    s.execute("UPDATE connexions_pennylane SET etat = 'connectee', societe_attendue = '172916', societe_id = '172916' WHERE dossier = 'D-1'")
    s.execute("SELECT jeton_chiffre FROM connexions_pennylane")
    assert s.fetchone()[0] == CHIFFRE
    # Nouveau jeton saisi : retour « à tester », société rattachée conservée
    cur = connecte(jeu, ADMIN)
    cur.execute("UPDATE connexions_pennylane SET jeton_chiffre = %s, duree = 'illimite' WHERE dossier = 'D-1'", (CHIFFRE + "B",))
    cur.execute("SELECT etat, societe_id, societe_attendue, expire_le FROM connexions_pennylane WHERE dossier = 'D-1'")
    assert cur.fetchone() == ("a_tester", None, "172916", None)


def test_connexions_reservees_aux_administrateurs(jeu):
    enregistrer(connecte(jeu, ADMIN))
    for email in (COLLAB, LECTURE):
        cur = connecte(jeu, email)
        cur.execute("SELECT dossier FROM connexions_pennylane")
        assert cur.fetchall() == []
        refuse(jeu, cur, "INSERT INTO connexions_pennylane (dossier, jeton_chiffre, empreinte_cle, fin_jeton) VALUES ('D-1', %s, %s, 'ABCD')",
               (CHIFFRE, EMPREINTE), erreur=(errors.InsufficientPrivilege, errors.CheckViolation))
        cur.execute("DELETE FROM connexions_pennylane WHERE dossier = 'D-1'")
        assert cur.rowcount == 0
    refuse(jeu, connecte(jeu, None), "SELECT dossier FROM connexions_pennylane")


def test_une_societe_pour_une_seule_residence(jeu):
    cur = connecte(jeu, ADMIN)
    enregistrer(cur, "D-1")
    enregistrer(cur, "D-2")
    s = service(jeu)
    s.execute("UPDATE connexions_pennylane SET societe_attendue = '172916' WHERE dossier = 'D-1'")
    refuse(jeu, s, "UPDATE connexions_pennylane SET societe_attendue = '172916' WHERE dossier = 'D-2'", erreur=errors.UniqueViolation)


def test_formats_refuses(jeu):
    cur = connecte(jeu, ADMIN)
    refuse(jeu, cur, "INSERT INTO connexions_pennylane (dossier, jeton_chiffre, empreinte_cle, fin_jeton) VALUES ('D-1', 'court', %s, 'ABCD')",
           (EMPREINTE,), erreur=errors.CheckViolation)
    refuse(jeu, cur, "INSERT INTO connexions_pennylane (dossier, jeton_chiffre, empreinte_cle, fin_jeton, duree) VALUES ('D-1', %s, %s, 'ABCD', '24')",
           (CHIFFRE, EMPREINTE), erreur=errors.CheckViolation)


def test_cle_publique_administrateurs(jeu):
    cur = connecte(jeu, ADMIN)
    cur.execute("INSERT INTO cle_jetons (id, cle_publique, empreinte) VALUES (1, %s, %s)", ("M" * 400, EMPREINTE))
    cur.execute("SELECT creee_par FROM cle_jetons")
    assert cur.fetchone()[0] == ADMIN
    refuse(jeu, cur, "INSERT INTO cle_jetons (id, cle_publique, empreinte) VALUES (2, %s, %s)", ("M" * 400, EMPREINTE),
           erreur=errors.CheckViolation)
    cur = connecte(jeu, COLLAB)
    cur.execute("SELECT * FROM cle_jetons")
    assert cur.fetchall() == []
    cur.execute("UPDATE cle_jetons SET empreinte = %s", ("b" * 64,))
    assert cur.rowcount == 0


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


def test_type_de_demande(jeu):
    s = service(jeu)
    s.execute("INSERT INTO synchronisations (demandee_par, dossiers, type) VALUES (%s, ARRAY['D-1'], 'test') RETURNING type", (ADMIN,))
    assert s.fetchone()[0] == "test"
    refuse(jeu, s, "INSERT INTO synchronisations (demandee_par, dossiers, type) VALUES (%s, ARRAY['D-1'], 'autre')", (ADMIN,),
           erreur=errors.CheckViolation)
