-- Migration 001 : utilisateurs (décision 0004). Données fictives uniquement.

CREATE TABLE IF NOT EXISTS profils (
    id      uuid PRIMARY KEY,
    email   text NOT NULL UNIQUE,
    nom     text NOT NULL,
    role    text NOT NULL CHECK (role IN ('administrateur', 'collaborateur', 'lecture')),
    actif   boolean NOT NULL DEFAULT true,
    fictif  boolean NOT NULL DEFAULT true
);
