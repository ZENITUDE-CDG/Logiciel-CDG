-- Migration 002 : résidences, groupes, appartenance et parcs (décision 0004).

CREATE TABLE IF NOT EXISTS residences (
    id                text PRIMARY KEY CHECK (id ~ '^[A-Z0-9_-]+$'),
    libelle           text NOT NULL,
    dossier_pennylane text,
    fictif            boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS groupes (
    id      text PRIMARY KEY CHECK (id ~ '^[A-Z0-9_-]+$'),
    libelle text NOT NULL,
    fictif  boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS residence_groupe (
    residence_id text NOT NULL REFERENCES residences(id) ON DELETE CASCADE,
    groupe_id    text NOT NULL REFERENCES groupes(id) ON DELETE CASCADE,
    PRIMARY KEY (residence_id, groupe_id)
);

-- Un parc relie un utilisateur à UNE résidence OU à UN groupe.
CREATE TABLE IF NOT EXISTS parcs (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    utilisateur_id uuid NOT NULL REFERENCES profils(id) ON DELETE CASCADE,
    residence_id   text REFERENCES residences(id) ON DELETE CASCADE,
    groupe_id      text REFERENCES groupes(id) ON DELETE CASCADE,
    CHECK ((residence_id IS NULL) <> (groupe_id IS NULL))
);
