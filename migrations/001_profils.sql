-- Migration 001 : profils des utilisateurs (lot 12, décisions 0004 et 0006).
-- SQL standard PostgreSQL. Aucune donnée réelle : les comptes de connexion sont gérés
-- par le service de connexion (Supabase aujourd'hui, Microsoft 365 demain) ; ce tableau
-- ne contient que l'adresse, le nom affiché et le rôle dans le logiciel.

CREATE TABLE IF NOT EXISTS profils (
    email   text PRIMARY KEY CHECK (email = lower(email) AND position('@' in email) > 1),
    nom     text NOT NULL,
    role    text NOT NULL CHECK (role IN ('administrateur', 'collaborateur', 'lecture')),
    actif   boolean NOT NULL DEFAULT true,
    fictif  boolean NOT NULL DEFAULT true
);
