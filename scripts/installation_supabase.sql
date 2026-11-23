-- INSTALLATION COMPLÈTE DE LA BASE DE TEST SUPABASE (lot 12). À coller en une fois dans SQL Editor.
-- Fichier assemblé : scripts/reinitialiser_base_test.sql + migrations/001 à 003 + scripts/donnees_test.sql.
-- Remet la base de test à zéro : données fictives uniquement. Ne jamais exécuter sur une base réelle.

-- ===================== scripts/reinitialiser_base_test.sql =====================
-- Remise à zéro de la BASE DE TEST Supabase (données fictives uniquement).
-- Supprime les tableaux et fonctions du lot 12, y compris ceux d'une version précédente.
-- Ne jamais exécuter sur une base contenant des données réelles.

DROP TABLE IF EXISTS parcs, residence_groupe, groupes, residences, profils CASCADE;

DROP FUNCTION IF EXISTS voit_groupe(text), voit_residence(text), modifie_residence(text),
  est_administrateur(), role_courant(), email_courant(), utilisateur_courant() CASCADE;

-- Rôle d'une version précédente du lot 12, devenu inutile.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_utilisateur') THEN
    BEGIN
      EXECUTE 'REVOKE ALL ON SCHEMA public FROM app_utilisateur';
      EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_utilisateur';
      EXECUTE 'DROP ROLE app_utilisateur';
    EXCEPTION WHEN others THEN
      RAISE NOTICE 'Rôle app_utilisateur non supprimé : %', SQLERRM;
    END;
  END IF;
END
$$;

-- ===================== migrations/001_profils.sql =====================
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

-- ===================== migrations/002_residences_groupes_parcs.sql =====================
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

-- ===================== migrations/003_droits.sql =====================
-- Migration 003 : droits d'accès vérifiés dans la base (lot 12, décisions 0004 et 0006).
--
-- Qui est connecté ? L'adresse e-mail présente dans le jeton de connexion
-- (réglage standard 'request.jwt.claims', rempli par PostgREST, utilisé par Supabase).
-- Le passage à Microsoft 365 ne change rien ici : le jeton contiendra toujours l'adresse.
--
-- Rôles PostgreSQL : 'authenticated' (personne connectée) et 'anon' (personne non connectée).
-- Ils existent déjà sur Supabase ; ils sont créés ici s'ils manquent (autre serveur, tests).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
END
$$;

-- Adresse de la personne connectée (NULL si personne).
CREATE OR REPLACE FUNCTION email_courant() RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT nullif(lower(coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::json ->> 'email'), '')
$$;

-- Rôle dans le logiciel de la personne connectée (NULL si inconnue ou désactivée).
CREATE OR REPLACE FUNCTION role_courant() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role FROM profils WHERE email = email_courant() AND actif
$$;

CREATE OR REPLACE FUNCTION est_administrateur() RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT coalesce(role_courant() = 'administrateur', false)
$$;

-- Une résidence est visible si elle est dans le parc, directement ou par un groupe.
CREATE OR REPLACE FUNCTION voit_residence(r text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT coalesce(role_courant() = 'administrateur', false) OR (
    role_courant() IS NOT NULL AND EXISTS (
      SELECT 1 FROM parcs p
      WHERE p.utilisateur_email = email_courant()
        AND (p.residence_id = r
             OR p.groupe_id IN (SELECT rg.groupe_id FROM residence_groupe rg
                                WHERE rg.residence_id = r))
    )
  )
$$;

-- Modifier une résidence : administrateur, ou collaborateur sur son parc.
CREATE OR REPLACE FUNCTION modifie_residence(r text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT coalesce(role_courant() IN ('administrateur', 'collaborateur'), false) AND voit_residence(r)
$$;

-- Un groupe est visible s'il figure dans le parc.
CREATE OR REPLACE FUNCTION voit_groupe(g text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT coalesce(role_courant() = 'administrateur', false) OR (
    role_courant() IS NOT NULL AND EXISTS (
      SELECT 1 FROM parcs p WHERE p.utilisateur_email = email_courant() AND p.groupe_id = g
    )
  )
$$;

ALTER TABLE profils          ENABLE ROW LEVEL SECURITY;
ALTER TABLE residences       ENABLE ROW LEVEL SECURITY;
ALTER TABLE groupes          ENABLE ROW LEVEL SECURITY;
ALTER TABLE residence_groupe ENABLE ROW LEVEL SECURITY;
ALTER TABLE parcs            ENABLE ROW LEVEL SECURITY;

-- profils : chacun lit son profil ; l'administrateur lit et gère tous les profils.
DROP POLICY IF EXISTS profils_lecture ON profils;
CREATE POLICY profils_lecture ON profils FOR SELECT TO authenticated
  USING (email = email_courant() OR est_administrateur());
DROP POLICY IF EXISTS profils_admin ON profils;
CREATE POLICY profils_admin ON profils FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- residences : lecture selon le parc ; modification selon le rôle ; création et suppression admin.
DROP POLICY IF EXISTS residences_lecture ON residences;
CREATE POLICY residences_lecture ON residences FOR SELECT TO authenticated
  USING (voit_residence(id));
DROP POLICY IF EXISTS residences_modification ON residences;
CREATE POLICY residences_modification ON residences FOR UPDATE TO authenticated
  USING (modifie_residence(id)) WITH CHECK (modifie_residence(id));
DROP POLICY IF EXISTS residences_creation ON residences;
CREATE POLICY residences_creation ON residences FOR INSERT TO authenticated
  WITH CHECK (est_administrateur());
DROP POLICY IF EXISTS residences_suppression ON residences;
CREATE POLICY residences_suppression ON residences FOR DELETE TO authenticated
  USING (est_administrateur());

-- groupes : lecture selon le parc ; écriture administrateur.
DROP POLICY IF EXISTS groupes_lecture ON groupes;
CREATE POLICY groupes_lecture ON groupes FOR SELECT TO authenticated
  USING (voit_groupe(id));
DROP POLICY IF EXISTS groupes_admin ON groupes;
CREATE POLICY groupes_admin ON groupes FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- appartenance d'une résidence à un groupe : lisible si la résidence l'est ; écriture admin.
DROP POLICY IF EXISTS residence_groupe_lecture ON residence_groupe;
CREATE POLICY residence_groupe_lecture ON residence_groupe FOR SELECT TO authenticated
  USING (voit_residence(residence_id));
DROP POLICY IF EXISTS residence_groupe_admin ON residence_groupe;
CREATE POLICY residence_groupe_admin ON residence_groupe FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- parcs : chacun lit son parc ; écriture administrateur.
DROP POLICY IF EXISTS parcs_lecture ON parcs;
CREATE POLICY parcs_lecture ON parcs FOR SELECT TO authenticated
  USING (utilisateur_email = email_courant() OR est_administrateur());
DROP POLICY IF EXISTS parcs_admin ON parcs;
CREATE POLICY parcs_admin ON parcs FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- Une personne non connectée n'a accès à rien.
REVOKE ALL ON profils, residences, groupes, residence_groupe, parcs FROM anon;
REVOKE ALL ON SEQUENCE parcs_id_seq FROM anon;

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON profils, residences, groupes, residence_groupe, parcs
  TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE parcs_id_seq TO authenticated;

-- ===================== scripts/donnees_test.sql =====================
-- Données de départ de la phase test (lot 12). Tout est fictif sauf les deux adresses
-- autorisées par la décision 0004. Peut être relancé sans créer de doublons.
--
-- Démonstration (décision 0006) : Raphael est administrateur et voit tout ;
-- Benjamin est collaborateur, son parc est le groupe pilote : il ne voit que la résidence pilote.

INSERT INTO profils (email, nom, role, fictif) VALUES
  ('raphael.bracq@zenitude-groupe.com',  'Raphael Bracq',    'administrateur', false),
  ('benjamin.gagneur@zenitude-groupe.com', 'Benjamin Gagneur', 'collaborateur',  false)
ON CONFLICT (email) DO NOTHING;

INSERT INTO residences (id, libelle, dossier_pennylane, fictif) VALUES
  ('RES-901', 'Résidence pilote (fictif)',    'PENNY-9001', true),
  ('RES-902', 'Résidence hors parc (fictif)', 'PENNY-9002', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO groupes (id, libelle, fictif) VALUES
  ('GRP-PILOTE', 'Groupe pilote (fictif)', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO residence_groupe (residence_id, groupe_id) VALUES ('RES-901', 'GRP-PILOTE')
ON CONFLICT DO NOTHING;

INSERT INTO parcs (utilisateur_email, groupe_id)
SELECT 'benjamin.gagneur@zenitude-groupe.com', 'GRP-PILOTE'
WHERE NOT EXISTS (SELECT 1 FROM parcs
                  WHERE utilisateur_email = 'benjamin.gagneur@zenitude-groupe.com'
                    AND groupe_id = 'GRP-PILOTE');
