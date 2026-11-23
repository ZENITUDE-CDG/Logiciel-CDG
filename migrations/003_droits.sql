-- Migration 003 : rôles d'accès et règles par ligne (décision 0004).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_utilisateur') THEN
    CREATE ROLE app_utilisateur NOLOGIN;
  END IF;
END
$$;

-- Permet au compte qui lance les tests de prendre le rôle restreint (SET ROLE).
GRANT app_utilisateur TO CURRENT_USER;

-- Utilisateur connecté, transmis par l'application dans la session.
CREATE OR REPLACE FUNCTION utilisateur_courant() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.utilisateur_id', true), '')::uuid
$$;

-- Rôle de l'utilisateur connecté (NULL si inconnu ou inactif).
CREATE OR REPLACE FUNCTION role_courant() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role FROM profils WHERE id = utilisateur_courant() AND actif
$$;

CREATE OR REPLACE FUNCTION est_administrateur() RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT coalesce(role_courant() = 'administrateur', false)
$$;

-- Une résidence est visible si elle est dans le parc, directement ou par un groupe.
CREATE OR REPLACE FUNCTION voit_residence(r text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role_courant() IS NOT NULL AND (
       role_courant() = 'administrateur'
    OR EXISTS (
         SELECT 1 FROM parcs p
         WHERE p.utilisateur_id = utilisateur_courant()
           AND (p.residence_id = r
                OR p.groupe_id IN (SELECT rg.groupe_id FROM residence_groupe rg
                                   WHERE rg.residence_id = r))
       )
  )
$$;

-- Modifier : administrateur ou collaborateur, uniquement sur ce qui est visible.
CREATE OR REPLACE FUNCTION modifie_residence(r text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role_courant() IN ('administrateur', 'collaborateur') AND voit_residence(r)
$$;

-- Un groupe est visible s'il figure dans le parc de l'utilisateur.
CREATE OR REPLACE FUNCTION voit_groupe(g text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role_courant() IS NOT NULL AND (
       role_courant() = 'administrateur'
    OR EXISTS (SELECT 1 FROM parcs p
               WHERE p.utilisateur_id = utilisateur_courant() AND p.groupe_id = g)
  )
$$;

ALTER TABLE profils          ENABLE ROW LEVEL SECURITY;
ALTER TABLE residences       ENABLE ROW LEVEL SECURITY;
ALTER TABLE groupes          ENABLE ROW LEVEL SECURITY;
ALTER TABLE residence_groupe ENABLE ROW LEVEL SECURITY;
ALTER TABLE parcs            ENABLE ROW LEVEL SECURITY;

-- profils : chacun voit son profil ; l'administrateur voit et gère tout
DROP POLICY IF EXISTS profils_lecture ON profils;
CREATE POLICY profils_lecture ON profils FOR SELECT TO app_utilisateur
  USING (id = utilisateur_courant() OR est_administrateur());
DROP POLICY IF EXISTS profils_admin ON profils;
CREATE POLICY profils_admin ON profils FOR ALL TO app_utilisateur
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- residences
DROP POLICY IF EXISTS residences_lecture ON residences;
CREATE POLICY residences_lecture ON residences FOR SELECT TO app_utilisateur
  USING (voit_residence(id));
DROP POLICY IF EXISTS residences_modification ON residences;
CREATE POLICY residences_modification ON residences FOR UPDATE TO app_utilisateur
  USING (modifie_residence(id)) WITH CHECK (modifie_residence(id));
DROP POLICY IF EXISTS residences_creation ON residences;
CREATE POLICY residences_creation ON residences FOR INSERT TO app_utilisateur
  WITH CHECK (est_administrateur());
DROP POLICY IF EXISTS residences_suppression ON residences;
CREATE POLICY residences_suppression ON residences FOR DELETE TO app_utilisateur
  USING (est_administrateur());

-- groupes : lecture selon le parc ; écriture administrateur seulement
DROP POLICY IF EXISTS groupes_lecture ON groupes;
CREATE POLICY groupes_lecture ON groupes FOR SELECT TO app_utilisateur
  USING (voit_groupe(id));
DROP POLICY IF EXISTS groupes_admin ON groupes;
CREATE POLICY groupes_admin ON groupes FOR ALL TO app_utilisateur
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- appartenance : visible si la résidence l'est ; écriture administrateur
DROP POLICY IF EXISTS residence_groupe_lecture ON residence_groupe;
CREATE POLICY residence_groupe_lecture ON residence_groupe FOR SELECT TO app_utilisateur
  USING (est_administrateur() OR voit_residence(residence_id));
DROP POLICY IF EXISTS residence_groupe_admin ON residence_groupe;
CREATE POLICY residence_groupe_admin ON residence_groupe FOR ALL TO app_utilisateur
  USING (est_administrateur()) WITH CHECK (est_administrateur());

-- parcs : chacun voit ses propres parcs ; écriture administrateur seulement
DROP POLICY IF EXISTS parcs_lecture ON parcs;
CREATE POLICY parcs_lecture ON parcs FOR SELECT TO app_utilisateur
  USING (est_administrateur() OR utilisateur_id = utilisateur_courant());
DROP POLICY IF EXISTS parcs_admin ON parcs;
CREATE POLICY parcs_admin ON parcs FOR ALL TO app_utilisateur
  USING (est_administrateur()) WITH CHECK (est_administrateur());

GRANT USAGE ON SCHEMA public TO app_utilisateur;
GRANT SELECT, INSERT, UPDATE, DELETE ON profils, residences, groupes, residence_groupe, parcs
  TO app_utilisateur;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_utilisateur;
