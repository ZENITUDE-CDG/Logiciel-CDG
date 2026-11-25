"""Lot 21 - migration 013 (modèle Mixte) : après toutes les migrations, la base contient exactement le catalogue de
départ d'interface/catalogue_kpi.py. Ignoré sans base de test (ZENITUDE_ENV=test et DATABASE_URL)."""
import os
import pathlib
import sys

import pytest

psycopg = pytest.importorskip("psycopg")
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "interface"))
import catalogue_kpi as ck  # noqa: E402


@pytest.fixture
def cur():
    if os.environ.get("ZENITUDE_ENV") != "test" or not os.environ.get("DATABASE_URL"):
        pytest.skip("Base de test absente.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn.cursor()
    finally:
        conn.rollback()
        conn.close()


def test_catalogue_final_identique_au_catalogue_de_depart(cur):
    cur.execute("SELECT id, libelle FROM kpi_modeles ORDER BY ordre")
    assert cur.fetchall() == [(m["id"], m["libelle"]) for m in ck.MODELES]
    cur.execute("SELECT code, modeles FROM kpi_catalogue")
    base = {c: sorted(m) for c, m in cur.fetchall()}
    assert base == {x["code"]: sorted(x["modeles"]) for x in ck.CATALOGUE}


def test_migration_013_rejouable(cur):
    texte = (pathlib.Path(__file__).parent.parent.parent / "migrations" / "013_modele_mixte.sql").read_text(encoding="utf-8")
    cur.execute(texte)
    cur.execute("SELECT count(*) FROM kpi_catalogue WHERE array_length(array_positions(modeles, 'MIXTE'), 1) > 1")
    assert cur.fetchone()[0] == 0
