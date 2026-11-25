-- Migration 009 : écritures Pennylane conservées entre deux synchronisations (lot 18d, lecture par
-- modifications). SQL standard PostgreSQL, rejouable.
--
-- pennylane_lignes    : lignes d'écritures d'un dossier, réduites aux champs utiles (date, compte, journal,
--                       écriture, libellé, débit, crédit, lettrage, date de modification).
-- pennylane_ecritures : écritures d'un dossier (pièce, statut, journal, date).
-- pennylane_etat      : par dossier, dates de la dernière lecture et de la dernière relecture complète,
--                       période couverte, taille de page acceptée par Pennylane.
-- Même contenu que le détail des écritures déjà publié pour les renvois au clic (lot 14). Tables techniques :
-- aucun accès depuis la page (ni lecture ni écriture) ; seul GitHub Actions y accède, avec la clé secrète.

CREATE TABLE IF NOT EXISTS pennylane_lignes (
    dossier  text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    id       bigint NOT NULL,
    contenu  jsonb NOT NULL,
    PRIMARY KEY (dossier, id)
);

CREATE TABLE IF NOT EXISTS pennylane_ecritures (
    dossier  text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    id       bigint NOT NULL,
    contenu  jsonb NOT NULL,
    PRIMARY KEY (dossier, id)
);

CREATE TABLE IF NOT EXISTS pennylane_etat (
    dossier            text PRIMARY KEY CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    derniere_lecture   timestamptz NOT NULL,
    derniere_complete  timestamptz NOT NULL,
    borne_debut        date,
    borne_fin          date,
    taille_page        integer CHECK (taille_page IS NULL OR taille_page BETWEEN 1 AND 1000)
);

ALTER TABLE pennylane_lignes ENABLE ROW LEVEL SECURITY;
ALTER TABLE pennylane_ecritures ENABLE ROW LEVEL SECURITY;
ALTER TABLE pennylane_etat ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pennylane_lignes, pennylane_ecritures, pennylane_etat FROM anon, authenticated;
