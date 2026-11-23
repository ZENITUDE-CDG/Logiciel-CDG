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
