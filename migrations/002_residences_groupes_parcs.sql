-- Migration 002 : résidences, groupes, appartenance et parcs (lot 12).
-- Une résidence correspond à un dossier Pennylane. Identifiants en [A-Z0-9_-] (invariant 11).

CREATE TABLE IF NOT EXISTS residences (
    id                text PRIMARY KEY CHECK (id ~ '^[A-Z0-9_-]+$'),
    libelle           text NOT NULL,
    dossier_pennylane text CHECK (dossier_pennylane IS NULL OR dossier_pennylane ~ '^[A-Z0-9_-]+$'),
    fictif            boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS groupes (
    id      text PRIMARY KEY CHECK (id ~ '^[A-Z0-9_-]+$'),
    libelle text NOT NULL,
    fictif  boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS residence_groupe (
    residence_id text NOT NULL REFERENCES residences(id) ON UPDATE CASCADE ON DELETE CASCADE,
    groupe_id    text NOT NULL REFERENCES groupes(id) ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (residence_id, groupe_id)
);

-- Un élément de parc donne à un utilisateur UNE résidence ou UN groupe.
-- Donner un groupe donne aussi les résidences ajoutées plus tard à ce groupe.
CREATE TABLE IF NOT EXISTS parcs (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    utilisateur_email text NOT NULL REFERENCES profils(email) ON UPDATE CASCADE ON DELETE CASCADE,
    residence_id      text REFERENCES residences(id) ON UPDATE CASCADE ON DELETE CASCADE,
    groupe_id         text REFERENCES groupes(id) ON UPDATE CASCADE ON DELETE CASCADE,
    CHECK ((residence_id IS NULL) <> (groupe_id IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS parcs_unique_residence
    ON parcs (utilisateur_email, residence_id) WHERE residence_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS parcs_unique_groupe
    ON parcs (utilisateur_email, groupe_id) WHERE groupe_id IS NOT NULL;
