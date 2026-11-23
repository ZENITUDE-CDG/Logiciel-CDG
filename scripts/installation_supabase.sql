-- INSTALLATION COMPLÈTE DE LA BASE DE TEST SUPABASE (lots 12 à 14). À coller en une fois dans SQL Editor.
-- Fichier assemblé par scripts/assembler_installation.py : remise à zéro + migrations + données de départ.
-- Remet la base de test à zéro : données fictives uniquement. Ne jamais exécuter sur une base réelle.
-- Après l'avoir lancé, relancer la publication des données (GitHub, Actions, « Run workflow »).

-- ===================== scripts/reinitialiser_base_test.sql =====================
-- Remise à zéro de la BASE DE TEST Supabase (données fictives uniquement).
-- Supprime les tableaux et fonctions des lots 12 à 14, y compris ceux d'une version précédente.
-- Ne jamais exécuter sur une base contenant des données réelles.

DROP TABLE IF EXISTS lissages, ajustements, comptes_simules, donnees_residences, donnees_communes,
  parcs, residence_groupe, groupes, residences, profils CASCADE;

DROP FUNCTION IF EXISTS gere_ajustement(boolean, text[]), voit_ajustement(boolean, text[]),
  modifie_dossier(text), voit_dossier(text), ajustements_trace(),
  voit_groupe(text), voit_residence(text), modifie_residence(text),
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

-- ===================== migrations/004_donnees_ajustements.sql =====================
-- Migration 004 : données calculées par le moteur et ajustements partagés (lot 13, décision 0007).
-- SQL standard PostgreSQL, rejouable. Aucun calcul comptable dans la base : elle stocke les
-- résultats du moteur Python (publiés par GitHub Actions) et les ajustements saisis dans la page.
--
-- donnees_communes   : paramètres communs du site (KPI, lignes EBITDA et SIG, modèle PCG...).
--                      Aucune donnée propre à une résidence.
-- donnees_residences : une ligne par résidence (compte de résultat figé, montants mensuels par
--                      compte, trésorerie, couverture). Lisible selon le parc, comme residences.
-- comptes_simules    : comptes créés pour porter des provisions (exemple 70610000P).
-- ajustements        : provisions, ajustements de compte et lissages, actifs dès leur création.
--
-- Écriture des données publiées : uniquement par le rôle de service (GitHub Actions, clé secrète
-- gardée dans les secrets GitHub). Aucune règle n'autorise une personne connectée à les modifier.

-- Phase test : tout est fictif. La contrainte empêche d'enregistrer une ligne marquée réelle.
CREATE TABLE IF NOT EXISTS donnees_communes (
    id        text PRIMARY KEY CHECK (id = 'SITE'),
    contenu   jsonb NOT NULL CHECK (jsonb_typeof(contenu) = 'object'),
    empreinte text NOT NULL,
    genere_le timestamptz NOT NULL DEFAULT now(),
    fictif    boolean NOT NULL DEFAULT true CHECK (fictif)
);

CREATE TABLE IF NOT EXISTS donnees_residences (
    residence_id text PRIMARY KEY REFERENCES residences(id) ON UPDATE CASCADE ON DELETE CASCADE,
    contenu      jsonb NOT NULL CHECK (jsonb_typeof(contenu) = 'object'),
    empreinte    text NOT NULL,
    genere_le    timestamptz NOT NULL DEFAULT now(),
    fictif       boolean NOT NULL DEFAULT true CHECK (fictif)
);

CREATE TABLE IF NOT EXISTS comptes_simules (
    numero   text PRIMARY KEY CHECK (numero ~ '^[67][0-9A-Z]{2,12}$'),
    libelle  text NOT NULL CHECK (length(btrim(libelle)) > 0),
    cree_par text DEFAULT email_courant(),
    cree_le  timestamptz NOT NULL DEFAULT now()
);

-- Un ajustement porte soit sur toutes les résidences (y compris celles ajoutées plus tard),
-- soit sur une liste de dossiers Pennylane. Le reste de sa définition (libellé, compte, règle,
-- saisie, lissage) est un objet structuré lu comme des données, jamais interprété (invariant 6).
CREATE TABLE IF NOT EXISTS ajustements (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    portee_tous boolean NOT NULL DEFAULT false,
    dossiers    text[] NOT NULL DEFAULT '{}',
    contenu     jsonb NOT NULL CHECK (jsonb_typeof(contenu) = 'object'),
    actif       boolean NOT NULL DEFAULT true,
    rev         integer NOT NULL DEFAULT 1 CHECK (rev >= 1),
    cree_par    text DEFAULT email_courant(),
    cree_le     timestamptz NOT NULL DEFAULT now(),
    modifie_par text DEFAULT email_courant(),
    modifie_le  timestamptz NOT NULL DEFAULT now(),
    CHECK (portee_tous <> (cardinality(dossiers) > 0))
);

-- Auteur et date de la dernière modification, renseignés par la base (pas par la page).
CREATE OR REPLACE FUNCTION ajustements_trace() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.modifie_par := email_courant();
  NEW.modifie_le := now();
  NEW.cree_par := OLD.cree_par;
  NEW.cree_le := OLD.cree_le;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS ajustements_trace ON ajustements;
CREATE TRIGGER ajustements_trace BEFORE UPDATE ON ajustements
  FOR EACH ROW EXECUTE FUNCTION ajustements_trace();

-- Un dossier Pennylane est visible (modifiable) si sa résidence l'est (règles du lot 12).
CREATE OR REPLACE FUNCTION voit_dossier(d text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM residences r WHERE r.dossier_pennylane = d AND voit_residence(r.id))
$$;

CREATE OR REPLACE FUNCTION modifie_dossier(d text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM residences r WHERE r.dossier_pennylane = d AND modifie_residence(r.id))
$$;

-- Lecture d'un ajustement : administrateur ; ou ajustement « toutes les résidences » (il change
-- les chiffres de tout le monde) ; ou toutes ses résidences sont dans le parc.
CREATE OR REPLACE FUNCTION voit_ajustement(tous boolean, ds text[]) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT role_courant() IS NOT NULL AND (
       est_administrateur()
    OR tous
    OR (cardinality(ds) > 0 AND NOT EXISTS (SELECT 1 FROM unnest(ds) AS x(d) WHERE NOT voit_dossier(x.d)))
  )
$$;

-- Création, modification, suppression : administrateur ; ou collaborateur sur des résidences
-- toutes dans son parc. Seul l'administrateur gère un ajustement « toutes les résidences ».
CREATE OR REPLACE FUNCTION gere_ajustement(tous boolean, ds text[]) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT est_administrateur() OR (
        role_courant() = 'collaborateur'
    AND NOT tous
    AND cardinality(ds) > 0
    AND NOT EXISTS (SELECT 1 FROM unnest(ds) AS x(d) WHERE NOT modifie_dossier(x.d))
  )
$$;

ALTER TABLE donnees_communes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE donnees_residences ENABLE ROW LEVEL SECURITY;
ALTER TABLE comptes_simules    ENABLE ROW LEVEL SECURITY;
ALTER TABLE ajustements        ENABLE ROW LEVEL SECURITY;

-- Données publiées : lecture seule pour les personnes connectées.
DROP POLICY IF EXISTS donnees_communes_lecture ON donnees_communes;
CREATE POLICY donnees_communes_lecture ON donnees_communes FOR SELECT TO authenticated
  USING (role_courant() IS NOT NULL);
DROP POLICY IF EXISTS donnees_residences_lecture ON donnees_residences;
CREATE POLICY donnees_residences_lecture ON donnees_residences FOR SELECT TO authenticated
  USING (voit_residence(residence_id));

-- Comptes simulés : lus par tout profil actif ; créés par administrateur ou collaborateur ;
-- supprimés par l'administrateur ou par leur auteur.
DROP POLICY IF EXISTS comptes_simules_lecture ON comptes_simules;
CREATE POLICY comptes_simules_lecture ON comptes_simules FOR SELECT TO authenticated
  USING (role_courant() IS NOT NULL);
DROP POLICY IF EXISTS comptes_simules_creation ON comptes_simules;
CREATE POLICY comptes_simules_creation ON comptes_simules FOR INSERT TO authenticated
  WITH CHECK (coalesce(role_courant() IN ('administrateur', 'collaborateur'), false)
              AND cree_par = email_courant());
DROP POLICY IF EXISTS comptes_simules_suppression ON comptes_simules;
CREATE POLICY comptes_simules_suppression ON comptes_simules FOR DELETE TO authenticated
  USING (est_administrateur() OR (role_courant() = 'collaborateur' AND cree_par = email_courant()));

-- Ajustements.
DROP POLICY IF EXISTS ajustements_lecture ON ajustements;
CREATE POLICY ajustements_lecture ON ajustements FOR SELECT TO authenticated
  USING (voit_ajustement(portee_tous, dossiers));
DROP POLICY IF EXISTS ajustements_creation ON ajustements;
CREATE POLICY ajustements_creation ON ajustements FOR INSERT TO authenticated
  WITH CHECK (gere_ajustement(portee_tous, dossiers) AND cree_par = email_courant());
DROP POLICY IF EXISTS ajustements_modification ON ajustements;
CREATE POLICY ajustements_modification ON ajustements FOR UPDATE TO authenticated
  USING (gere_ajustement(portee_tous, dossiers)) WITH CHECK (gere_ajustement(portee_tous, dossiers));
DROP POLICY IF EXISTS ajustements_suppression ON ajustements;
CREATE POLICY ajustements_suppression ON ajustements FOR DELETE TO authenticated
  USING (gere_ajustement(portee_tous, dossiers));

-- Privilèges : personne non connectée, rien ; personne connectée, lecture des données publiées.
REVOKE ALL ON donnees_communes, donnees_residences, comptes_simules, ajustements FROM anon;
REVOKE ALL ON SEQUENCE ajustements_id_seq FROM anon;
REVOKE ALL ON donnees_communes, donnees_residences FROM authenticated;
GRANT SELECT ON donnees_communes, donnees_residences TO authenticated;
GRANT SELECT, INSERT, DELETE ON comptes_simules TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ajustements TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE ajustements_id_seq TO authenticated;

-- Rôle de service (Supabase : clé secrète, utilisée par GitHub Actions). Il contourne les règles
-- par ligne ; il lui faut seulement les privilèges sur les tables. Absent sur un autre serveur.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    GRANT USAGE ON SCHEMA public TO service_role;
    GRANT SELECT ON residences TO service_role;
    GRANT SELECT, INSERT, UPDATE, DELETE ON donnees_communes, donnees_residences TO service_role;
  END IF;
END
$$;

-- ===================== migrations/005_lissages.sql =====================
-- Migration 005 : lissage de postes, écriture par écriture (lot 14, décision 0008).
-- Une ligne = une écriture comptable lissée : son montant est retiré de son mois et réparti à parts égales
-- sur les mois de du à au (au plus l'exercice suivant). Le calcul est fait par la page (décision 0002) ;
-- la base ne stocke que le choix (quelle écriture, quelle période) et une copie du montant et de la date
-- de l'écriture, pour détecter une écriture modifiée ou supprimée à la publication suivante.
-- SQL standard PostgreSQL, rejouable.

CREATE TABLE IF NOT EXISTS lissages (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dossier       text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    ecriture      text NOT NULL CHECK (length(ecriture) BETWEEN 1 AND 80),
    compte        text NOT NULL CHECK (compte ~ '^[67][0-9A-Z]*$'),
    montant       bigint NOT NULL,
    date_ecriture date NOT NULL,
    du            text NOT NULL CHECK (du ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    au            text NOT NULL CHECK (au ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    actif         boolean NOT NULL DEFAULT true,
    rev           integer NOT NULL DEFAULT 1 CHECK (rev >= 1),
    cree_par      text DEFAULT email_courant(),
    cree_le       timestamptz NOT NULL DEFAULT now(),
    modifie_par   text DEFAULT email_courant(),
    modifie_le    timestamptz NOT NULL DEFAULT now(),
    CHECK (du <= au),
    UNIQUE (dossier, ecriture)
);

-- Même trace que les ajustements : auteur conservé, dernier modificateur et date posés par la base.
DROP TRIGGER IF EXISTS lissages_trace ON lissages;
CREATE TRIGGER lissages_trace BEFORE UPDATE ON lissages
  FOR EACH ROW EXECUTE FUNCTION ajustements_trace();

ALTER TABLE lissages ENABLE ROW LEVEL SECURITY;

-- Lecture : résidence du parc. Écriture : administrateur, ou collaborateur sur une résidence de son parc.
DROP POLICY IF EXISTS lissages_lecture ON lissages;
CREATE POLICY lissages_lecture ON lissages FOR SELECT TO authenticated
  USING (voit_dossier(dossier));
DROP POLICY IF EXISTS lissages_creation ON lissages;
CREATE POLICY lissages_creation ON lissages FOR INSERT TO authenticated
  WITH CHECK (gere_ajustement(false, ARRAY[dossier]) AND cree_par = email_courant());
DROP POLICY IF EXISTS lissages_modification ON lissages;
CREATE POLICY lissages_modification ON lissages FOR UPDATE TO authenticated
  USING (gere_ajustement(false, ARRAY[dossier])) WITH CHECK (gere_ajustement(false, ARRAY[dossier]));
DROP POLICY IF EXISTS lissages_suppression ON lissages;
CREATE POLICY lissages_suppression ON lissages FOR DELETE TO authenticated
  USING (gere_ajustement(false, ARRAY[dossier]));

REVOKE ALL ON lissages FROM anon;
REVOKE ALL ON SEQUENCE lissages_id_seq FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON lissages TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE lissages_id_seq TO authenticated;

-- ===================== scripts/donnees_test.sql =====================
-- Données de départ de la phase test (lots 12 et 13). Tout est fictif sauf les deux adresses
-- autorisées par la décision 0004. Peut être relancé sans créer de doublons.
--
-- Résidences : les huit résidences de démonstration (interface/demo, generer_demo.py), dont les
-- chiffres sont publiés par GitHub Actions (décision 0007). Les résidences de test RES-901 et
-- RES-902 du lot 12 sont supprimées (nettoyage du 23 novembre 2026).
--
-- Démonstration : Raphael est administrateur et voit tout ; Benjamin est collaborateur, son parc
-- est le groupe des résidences seniors : il ne voit que RES-003, RES-004 et RES-005.

INSERT INTO profils (email, nom, role, fictif) VALUES
  ('raphael.bracq@zenitude-groupe.com',  'Raphael Bracq',    'administrateur', false),
  ('benjamin.gagneur@zenitude-groupe.com', 'Benjamin Gagneur', 'collaborateur',  false)
ON CONFLICT (email) DO NOTHING;

DELETE FROM residences WHERE id IN ('RES-901', 'RES-902');
DELETE FROM groupes WHERE id = 'GRP-PILOTE';

INSERT INTO residences (id, libelle, dossier_pennylane, fictif) VALUES
  ('RES-001', 'Les Terrasses du Port (fictif)',  'DEMO-2001', true),
  ('RES-002', 'Le Belvédère (fictif)',           'DEMO-2002', true),
  ('RES-003', 'Les Tilleuls (fictif)',           'DEMO-2003', true),
  ('RES-004', 'Le Clos Fleuri (fictif)',         'DEMO-2004', true),
  ('RES-005', 'Les Marronniers (fictif)',        'DEMO-2005', true),
  ('RES-006', 'Campus Rive Gauche (fictif)',     'DEMO-2006', true),
  ('RES-007', 'Le Jardin des Sciences (fictif)', 'DEMO-2007', true),
  ('RES-008', 'Les Hauts de Loire (fictif)',     'DEMO-2008', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO groupes (id, libelle, fictif) VALUES
  ('GRP-SENIORS', 'Résidences seniors (fictif)', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO residence_groupe (residence_id, groupe_id) VALUES
  ('RES-003', 'GRP-SENIORS'), ('RES-004', 'GRP-SENIORS'), ('RES-005', 'GRP-SENIORS')
ON CONFLICT DO NOTHING;

INSERT INTO parcs (utilisateur_email, groupe_id)
SELECT 'benjamin.gagneur@zenitude-groupe.com', 'GRP-SENIORS'
WHERE NOT EXISTS (SELECT 1 FROM parcs
                  WHERE utilisateur_email = 'benjamin.gagneur@zenitude-groupe.com'
                    AND groupe_id = 'GRP-SENIORS');
