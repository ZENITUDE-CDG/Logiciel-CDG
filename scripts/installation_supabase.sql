-- INSTALLATION COMPLÈTE DE LA BASE DE TEST SUPABASE (lots 12 à 20). À coller en une fois dans SQL Editor.
-- Fichier assemblé par scripts/assembler_installation.py : remise à zéro + migrations + données de départ.
-- Remet la base de test à zéro : données fictives uniquement. Ne jamais exécuter sur une base réelle.
-- Après l'avoir lancé, relancer la publication des données (GitHub, Actions, « Run workflow »).

-- ===================== scripts/reinitialiser_base_test.sql =====================
-- Remise à zéro de la BASE DE TEST Supabase (données fictives uniquement).
-- Supprime les tableaux et fonctions des lots 12 à 20, y compris ceux d'une version précédente.
-- Ne jamais exécuter sur une base contenant des données réelles.

DROP TABLE IF EXISTS residence_modele, kpi_journal, kpi_catalogue, kpi_modeles, connexions_pennylane, cle_jetons, depots_kpi, kpi_mois, pennylane_magasin, pennylane_etat, pennylane_ecritures, pennylane_lignes, lettrages_pennylane, synchronisations, parametres_import, mesures_importees, comptes_bancaires, lissages, ajustements, comptes_simules, donnees_residences, donnees_communes,
  parcs, residence_groupe, groupes, residences, profils CASCADE;

DROP FUNCTION IF EXISTS controle_kpi_catalogue(), journal_kpi_catalogue(), trace_residence_modele(), controle_signe_mesure(), trace_connexion_pennylane(), trace_cle_jetons(), trace_kpi(), garde_code_mews(), trace_lettrage(), trace_parametres_import(), trace_import(), gere_ajustement(boolean, text[]), voit_ajustement(boolean, text[]),
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

-- ===================== migrations/006_kpi_et_comptes_bancaires.sql =====================
-- Migration 006 : mesures d'exploitation importées et paramètres des comptes bancaires (lot 15, décision 0009).
-- SQL standard PostgreSQL, rejouable.
--
-- mesures_importees  : valeurs mensuelles par résidence (dossier), importées depuis le modèle Excel de la page
--                      Données externes. Elles remplacent, pour ce mois et cette mesure, la valeur publiée.
--                      Lecture selon le parc ; import par un administrateur seulement (un collaborateur
--                      n'importe pas, décision du lot 12).
-- comptes_bancaires  : libellé, rôle (principal, secondaire, autre) et solde minimum souhaité d'un compte de
--                      disponibilités, pour la vue du trésorier. Lecture selon le parc ; écriture administrateur.

CREATE TABLE IF NOT EXISTS mesures_importees (
    dossier     text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    mois        text NOT NULL CHECK (mois ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    mesure      text NOT NULL CHECK (mesure ~ '^[A-Z0-9_]+$'),
    valeur      numeric NOT NULL CHECK (valeur >= 0),
    importe_par text DEFAULT email_courant(),
    importe_le  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier, mois, mesure)
);

CREATE TABLE IF NOT EXISTS comptes_bancaires (
    dossier     text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    compte      text NOT NULL CHECK (compte ~ '^5[0-9A-Z]*$'),
    libelle     text NOT NULL DEFAULT '' CHECK (length(libelle) <= 80),
    role        text NOT NULL DEFAULT 'autre' CHECK (role IN ('principal', 'secondaire', 'autre')),
    solde_min   bigint CHECK (solde_min IS NULL OR solde_min >= 0),
    modifie_par text DEFAULT email_courant(),
    modifie_le  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier, compte)
);

-- Auteur et date posés par la base, à l'insertion comme à la modification.
CREATE OR REPLACE FUNCTION trace_import() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'mesures_importees' THEN
    NEW.importe_par := email_courant(); NEW.importe_le := now();
  ELSE
    NEW.modifie_par := email_courant(); NEW.modifie_le := now();
  END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS mesures_importees_trace ON mesures_importees;
CREATE TRIGGER mesures_importees_trace BEFORE INSERT OR UPDATE ON mesures_importees
  FOR EACH ROW EXECUTE FUNCTION trace_import();
DROP TRIGGER IF EXISTS comptes_bancaires_trace ON comptes_bancaires;
CREATE TRIGGER comptes_bancaires_trace BEFORE INSERT OR UPDATE ON comptes_bancaires
  FOR EACH ROW EXECUTE FUNCTION trace_import();

ALTER TABLE mesures_importees ENABLE ROW LEVEL SECURITY;
ALTER TABLE comptes_bancaires ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mesures_importees_lecture ON mesures_importees;
CREATE POLICY mesures_importees_lecture ON mesures_importees FOR SELECT TO authenticated
  USING (voit_dossier(dossier));
DROP POLICY IF EXISTS mesures_importees_admin ON mesures_importees;
CREATE POLICY mesures_importees_admin ON mesures_importees FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur() AND voit_dossier(dossier));

DROP POLICY IF EXISTS comptes_bancaires_lecture ON comptes_bancaires;
CREATE POLICY comptes_bancaires_lecture ON comptes_bancaires FOR SELECT TO authenticated
  USING (voit_dossier(dossier));
DROP POLICY IF EXISTS comptes_bancaires_admin ON comptes_bancaires;
CREATE POLICY comptes_bancaires_admin ON comptes_bancaires FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur() AND voit_dossier(dossier));

REVOKE ALL ON mesures_importees, comptes_bancaires FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON mesures_importees, comptes_bancaires TO authenticated;

-- ===================== migrations/007_synchronisation_pennylane.sql =====================
-- Migration 007 : paramètres d'import et synchronisations Pennylane lancées depuis la page (lot 18b,
-- décision 0012). SQL standard PostgreSQL, rejouable.
--
-- parametres_import : par résidence (dossier) : période d'import (mois de début et de fin) et masquage des
--                     écritures en brouillard. Lecture selon le parc ; écriture administrateur. La fonction
--                     serveur « lancer-synchro » les enregistre à chaque demande de synchronisation.
-- synchronisations  : journal des demandes (qui, quand, quelles résidences, période, statut, résultat sans
--                     montant). Lecture administrateur. Aucune écriture depuis la page : seules la fonction
--                     serveur et GitHub Actions écrivent, avec la clé secrète (hors règles de lignes).

CREATE TABLE IF NOT EXISTS parametres_import (
    dossier            text PRIMARY KEY CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    mois_debut         text CHECK (mois_debut ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    mois_fin           text CHECK (mois_fin ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    masquer_brouillard boolean NOT NULL DEFAULT true,
    modifie_par        text,
    modifie_le         timestamptz NOT NULL DEFAULT now(),
    CHECK (mois_debut IS NULL OR mois_fin IS NULL OR mois_debut <= mois_fin)
);

CREATE TABLE IF NOT EXISTS synchronisations (
    id                 bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    demandee_par       text,
    demandee_le        timestamptz NOT NULL DEFAULT now(),
    perimetre          text NOT NULL DEFAULT '' CHECK (length(perimetre) <= 120),
    dossiers           text[] NOT NULL CHECK (cardinality(dossiers) BETWEEN 1 AND 500),
    mois_debut         text CHECK (mois_debut ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    mois_fin           text CHECK (mois_fin ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    masquer_brouillard boolean NOT NULL DEFAULT true,
    statut             text NOT NULL DEFAULT 'demandée'
                       CHECK (statut IN ('demandée', 'en cours', 'terminée', 'échec')),
    debut              timestamptz,
    fin                timestamptz,
    resultat           jsonb NOT NULL DEFAULT '{}'::jsonb,
    message            text CHECK (message IS NULL OR length(message) <= 500),
    execution          text
);

-- Auteur posé par la base quand une personne connectée écrit ; conservé quand la fonction serveur écrit
-- avec la clé secrète (pas d'adresse dans le jeton) et renseigne l'auteur elle-même.
CREATE OR REPLACE FUNCTION trace_parametres_import() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.modifie_par := coalesce(email_courant(), NEW.modifie_par);
  NEW.modifie_le := now();
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS parametres_import_trace ON parametres_import;
CREATE TRIGGER parametres_import_trace BEFORE INSERT OR UPDATE ON parametres_import
  FOR EACH ROW EXECUTE FUNCTION trace_parametres_import();

ALTER TABLE parametres_import ENABLE ROW LEVEL SECURITY;
ALTER TABLE synchronisations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS parametres_import_lecture ON parametres_import;
CREATE POLICY parametres_import_lecture ON parametres_import FOR SELECT TO authenticated
  USING (voit_dossier(dossier));
DROP POLICY IF EXISTS parametres_import_admin ON parametres_import;
CREATE POLICY parametres_import_admin ON parametres_import FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur() AND voit_dossier(dossier));

DROP POLICY IF EXISTS synchronisations_lecture ON synchronisations;
CREATE POLICY synchronisations_lecture ON synchronisations FOR SELECT TO authenticated
  USING (est_administrateur());

REVOKE ALL ON parametres_import, synchronisations FROM anon;
REVOKE ALL ON synchronisations FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON parametres_import TO authenticated;
GRANT SELECT ON synchronisations TO authenticated;

-- ===================== migrations/008_lettrages_pennylane.sql =====================
-- Migration 008 : mémoire du lettrage Pennylane (lot 18c, vitesse de la synchronisation).
-- SQL standard PostgreSQL, rejouable.
--
-- lettrages_pennylane : pour chaque ligne d'écriture de tiers (comptes 40 et 41) d'un dossier, le groupe de
--                       lettrage relevé dans Pennylane, la date de dernière modification de la ligne (maj) et la
--                       date du relevé. La synchronisation ne redemande un groupe que si la ligne a changé ou si
--                       le relevé a plus de 7 jours. Aucun montant, aucun libellé.
--                       Table technique : aucun accès depuis la page (ni lecture ni écriture) ; seul GitHub
--                       Actions y accède, avec la clé secrète.

CREATE TABLE IF NOT EXISTS lettrages_pennylane (
    dossier   text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    ligne_id  bigint NOT NULL,
    maj       text NOT NULL DEFAULT '',
    groupe    text NOT NULL DEFAULT '' CHECK (groupe = '' OR groupe ~ '^[A-Z0-9_-]+$'),
    lu_le     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier, ligne_id)
);

-- Date du relevé posée par la base, à l'insertion comme à la mise à jour.
CREATE OR REPLACE FUNCTION trace_lettrage() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.lu_le := now();
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS lettrages_pennylane_trace ON lettrages_pennylane;
CREATE TRIGGER lettrages_pennylane_trace BEFORE INSERT OR UPDATE ON lettrages_pennylane
  FOR EACH ROW EXECUTE FUNCTION trace_lettrage();

ALTER TABLE lettrages_pennylane ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON lettrages_pennylane FROM anon, authenticated;

-- ===================== migrations/009_ecritures_pennylane.sql =====================
-- Migration 009 : écritures Pennylane conservées entre deux synchronisations (lot 18d, lecture par
-- modifications). SQL standard PostgreSQL, rejouable. Tables pennylane_lignes et pennylane_ecritures
-- remplacées par pennylane_magasin (migration 010).
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

-- ===================== migrations/010_magasin_compresse.sql =====================
-- Migration 010 : écritures Pennylane conservées compressées (lot 18d, vitesse). SQL standard, rejouable.
--
-- Mesuré le 25 novembre 2026 sur le dossier de test : 35 863 lignes, une ligne de table par écriture,
-- 26 à 57 s pour relire, 32 à 55 s pour écrire. Les écritures sont désormais conservées en quelques morceaux
-- compressés (environ 1 Mo pour 36 000 lignes) : une ou deux requêtes.
-- pennylane_magasin : morceaux numérotés à partir de 0 ; pennylane_etat.morceaux en donne le nombre attendu
-- (des morceaux manquants provoquent une relecture complète). Aucun accès depuis la page.

CREATE TABLE IF NOT EXISTS pennylane_magasin (
    dossier  text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    morceau  integer NOT NULL CHECK (morceau >= 0),
    donnees  text NOT NULL,
    PRIMARY KEY (dossier, morceau)
);
ALTER TABLE pennylane_etat ADD COLUMN IF NOT EXISTS morceaux integer;
ALTER TABLE pennylane_magasin ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pennylane_magasin FROM anon, authenticated;

-- Tables d'une ligne par écriture (migration 009), remplacées par pennylane_magasin. L'état est effacé :
-- la synchronisation suivante fait une lecture complète et remplit pennylane_magasin.
DROP TABLE IF EXISTS pennylane_lignes, pennylane_ecritures;
DELETE FROM pennylane_etat;

-- ===================== migrations/011_kpi_consolide_et_connexions.sql =====================
-- Migration 011 : import du consolidé KPI et connexions Pennylane par résidence (lot 19, décision 0013).
-- SQL standard PostgreSQL, rejouable. S'ajoute aux migrations 001 à 010 sans remise à zéro.
--
-- residences.code_mews  : code de la résidence dans Mews (préfixe du nom Mews, ex. « ABA »), qui rattache les
--                         lignes du consolidé KPI à la résidence. Modifiable par un administrateur seulement.
-- mesures_importees     : les montants (mesures CA_...) peuvent être négatifs (avoirs) ; les quantités restent
--                         positives ou nulles.
-- kpi_mois              : statut d'un mois importé (Complet, Estimé, Anomalie, Ancien fichier), source et détail,
--                         repris du consolidé. Lecture selon le parc ; écriture administrateur.
-- depots_kpi            : historique des dépôts du consolidé (fichier, périmètre, nombres, auteur). Lecture et
--                         ajout administrateur ; jamais modifié.
-- cle_jetons            : clé PUBLIQUE de chiffrement des jetons Pennylane (une seule ligne). La clé privée n'existe
--                         que dans le secret GitHub PENNYLANE_CLE_PRIVEE. Lecture et écriture administrateur.
-- connexions_pennylane  : un jeton par dossier, CHIFFRÉ dans le navigateur avec la clé publique. La colonne
--                         jeton_chiffre ne peut jamais être relue par une personne connectée (droits par colonne) :
--                         seul GitHub Actions la lit, avec la clé secrète, et seul lui la déchiffre. L'état du test
--                         (société Pennylane, droits, résultat) n'est écrit que par GitHub Actions.

-- ------------------------------------------------------------------ résidences : code Mews
ALTER TABLE residences ADD COLUMN IF NOT EXISTS code_mews text;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'residences_code_mews_format') THEN
    ALTER TABLE residences ADD CONSTRAINT residences_code_mews_format
      CHECK (code_mews IS NULL OR code_mews ~ '^[A-Z0-9_-]{1,40}$');
  END IF;
END
$$;
CREATE UNIQUE INDEX IF NOT EXISTS residences_code_mews_unique ON residences (code_mews) WHERE code_mews IS NOT NULL;

-- Un collaborateur peut modifier les résidences de son parc (lot 12), mais le rattachement Mews relève de l'import
-- (administrateurs).
CREATE OR REPLACE FUNCTION garde_code_mews() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_user IN ('authenticated', 'anon')
     AND NEW.code_mews IS DISTINCT FROM (CASE WHEN TG_OP = 'UPDATE' THEN OLD.code_mews ELSE NULL END)
     AND NOT est_administrateur() THEN
    RAISE EXCEPTION 'code Mews modifiable par un administrateur seulement' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS residences_code_mews ON residences;
CREATE TRIGGER residences_code_mews BEFORE INSERT OR UPDATE ON residences
  FOR EACH ROW EXECUTE FUNCTION garde_code_mews();

-- ------------------------------------------------------------------ mesures importées : montants signés
DO $$
DECLARE c text;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'mesures_importees'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) LIKE '%valeur >= %' AND conname <> 'mesures_importees_valeur_signe'
  LOOP
    EXECUTE format('ALTER TABLE mesures_importees DROP CONSTRAINT %I', c);
  END LOOP;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mesures_importees_valeur_signe') THEN
    ALTER TABLE mesures_importees ADD CONSTRAINT mesures_importees_valeur_signe
      CHECK (valeur >= 0 OR mesure LIKE 'CA\_%');
  END IF;
END
$$;

-- ------------------------------------------------------------------ statut des mois importés
CREATE TABLE IF NOT EXISTS kpi_mois (
    dossier     text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    mois        text NOT NULL CHECK (mois ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    source      text NOT NULL DEFAULT '' CHECK (length(source) <= 60),
    statut      text NOT NULL DEFAULT '' CHECK (length(statut) <= 40),
    detail      text NOT NULL DEFAULT '' CHECK (length(detail) <= 500),
    fichier     text NOT NULL DEFAULT '' CHECK (length(fichier) <= 200),
    importe_par text DEFAULT email_courant(),
    importe_le  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier, mois)
);

CREATE TABLE IF NOT EXISTS depots_kpi (
    id          bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    fichier     text NOT NULL CHECK (length(fichier) <= 200),
    perimetre   text NOT NULL DEFAULT '' CHECK (length(perimetre) <= 120),
    residences  integer NOT NULL DEFAULT 0 CHECK (residences >= 0),
    mois        integer NOT NULL DEFAULT 0 CHECK (mois >= 0),
    nouvelles   integer NOT NULL DEFAULT 0 CHECK (nouvelles >= 0),
    modifiees   integer NOT NULL DEFAULT 0 CHECK (modifiees >= 0),
    ecartees    integer NOT NULL DEFAULT 0 CHECK (ecartees >= 0),
    depose_par  text DEFAULT email_courant(),
    depose_le   timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION trace_kpi() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'kpi_mois' THEN
    NEW.importe_par := coalesce(email_courant(), NEW.importe_par); NEW.importe_le := now();
  ELSE
    NEW.depose_par := coalesce(email_courant(), NEW.depose_par); NEW.depose_le := now();
  END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS kpi_mois_trace ON kpi_mois;
CREATE TRIGGER kpi_mois_trace BEFORE INSERT OR UPDATE ON kpi_mois FOR EACH ROW EXECUTE FUNCTION trace_kpi();
DROP TRIGGER IF EXISTS depots_kpi_trace ON depots_kpi;
CREATE TRIGGER depots_kpi_trace BEFORE INSERT ON depots_kpi FOR EACH ROW EXECUTE FUNCTION trace_kpi();

ALTER TABLE kpi_mois ENABLE ROW LEVEL SECURITY;
ALTER TABLE depots_kpi ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS kpi_mois_lecture ON kpi_mois;
CREATE POLICY kpi_mois_lecture ON kpi_mois FOR SELECT TO authenticated USING (voit_dossier(dossier));
DROP POLICY IF EXISTS kpi_mois_admin ON kpi_mois;
CREATE POLICY kpi_mois_admin ON kpi_mois FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur() AND voit_dossier(dossier));
DROP POLICY IF EXISTS depots_kpi_lecture ON depots_kpi;
CREATE POLICY depots_kpi_lecture ON depots_kpi FOR SELECT TO authenticated USING (est_administrateur());
DROP POLICY IF EXISTS depots_kpi_ajout ON depots_kpi;
CREATE POLICY depots_kpi_ajout ON depots_kpi FOR INSERT TO authenticated WITH CHECK (est_administrateur());

REVOKE ALL ON kpi_mois, depots_kpi FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON kpi_mois TO authenticated;
REVOKE UPDATE, DELETE ON depots_kpi FROM authenticated;
GRANT SELECT, INSERT ON depots_kpi TO authenticated;
GRANT USAGE ON SEQUENCE depots_kpi_id_seq TO authenticated;

-- ------------------------------------------------------------------ clé publique de chiffrement des jetons
CREATE TABLE IF NOT EXISTS cle_jetons (
    id           integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    cle_publique text NOT NULL CHECK (length(cle_publique) BETWEEN 100 AND 2000),
    empreinte    text NOT NULL CHECK (empreinte ~ '^[0-9a-f]{64}$'),
    creee_par    text DEFAULT email_courant(),
    creee_le     timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION trace_cle_jetons() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.creee_par := coalesce(email_courant(), NEW.creee_par); NEW.creee_le := now();
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS cle_jetons_trace ON cle_jetons;
CREATE TRIGGER cle_jetons_trace BEFORE INSERT OR UPDATE ON cle_jetons FOR EACH ROW EXECUTE FUNCTION trace_cle_jetons();
ALTER TABLE cle_jetons ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cle_jetons_admin ON cle_jetons;
CREATE POLICY cle_jetons_admin ON cle_jetons FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());
REVOKE ALL ON cle_jetons FROM anon;
GRANT SELECT, INSERT, UPDATE ON cle_jetons TO authenticated;

-- ------------------------------------------------------------------ connexions Pennylane (jetons chiffrés)
CREATE TABLE IF NOT EXISTS connexions_pennylane (
    dossier        text PRIMARY KEY CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    jeton_chiffre  text CHECK (jeton_chiffre IS NULL OR length(jeton_chiffre) BETWEEN 100 AND 4000),
    empreinte_cle  text CHECK (empreinte_cle IS NULL OR empreinte_cle ~ '^[0-9a-f]{64}$'),
    fin_jeton      text CHECK (fin_jeton IS NULL OR fin_jeton ~ '^[A-Za-z0-9_-]{4}$'),
    duree          text NOT NULL DEFAULT '12' CHECK (duree IN ('1', '6', '12', 'illimite')),
    expire_le      date,
    etat           text NOT NULL DEFAULT 'a_tester'
                   CHECK (etat IN ('a_tester', 'connectee', 'refusee', 'a_renouveler', 'erreur')),
    motif          text CHECK (motif IS NULL OR length(motif) <= 300),
    societe_nom    text CHECK (societe_nom IS NULL OR length(societe_nom) <= 200),
    societe_id     text CHECK (societe_id IS NULL OR length(societe_id) <= 40),
    societe_attendue text CHECK (societe_attendue IS NULL OR length(societe_attendue) <= 40),
    droits         text[] NOT NULL DEFAULT '{}',
    teste_le       timestamptz,
    enregistre_par text,
    enregistre_le  timestamptz NOT NULL DEFAULT now()
);
-- Une même société Pennylane ne peut être rattachée qu'à une seule résidence (jeton collé au mauvais endroit).
CREATE UNIQUE INDEX IF NOT EXISTS connexions_pennylane_societe ON connexions_pennylane (societe_attendue)
  WHERE societe_attendue IS NOT NULL;

-- Une personne connectée qui enregistre un jeton : auteur, date et échéance posés par la base, état remis
-- « à tester ». Les colonnes de résultat ne sont écrites que par GitHub Actions (clé secrète, hors de ce cas).
CREATE OR REPLACE FUNCTION trace_connexion_pennylane() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_user IN ('authenticated', 'anon') THEN
    NEW.enregistre_par := email_courant();
    NEW.enregistre_le := now();
    NEW.expire_le := CASE NEW.duree WHEN 'illimite' THEN NULL
                     ELSE ((now() AT TIME ZONE 'Europe/Paris')::date + make_interval(months => NEW.duree::int))::date END;
    NEW.etat := 'a_tester'; NEW.motif := NULL; NEW.teste_le := NULL;
    NEW.societe_nom := NULL; NEW.societe_id := NULL; NEW.droits := '{}';
    IF TG_OP = 'UPDATE' THEN NEW.societe_attendue := OLD.societe_attendue; ELSE NEW.societe_attendue := NULL; END IF;
  END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS connexions_pennylane_trace ON connexions_pennylane;
CREATE TRIGGER connexions_pennylane_trace BEFORE INSERT OR UPDATE ON connexions_pennylane
  FOR EACH ROW EXECUTE FUNCTION trace_connexion_pennylane();

ALTER TABLE connexions_pennylane ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS connexions_pennylane_admin ON connexions_pennylane;
CREATE POLICY connexions_pennylane_admin ON connexions_pennylane FOR ALL TO authenticated
  USING (est_administrateur() AND voit_dossier(dossier)) WITH CHECK (est_administrateur() AND voit_dossier(dossier));

REVOKE ALL ON connexions_pennylane FROM anon, authenticated;
-- Droits par colonne : jamais de lecture du jeton chiffré, jamais d'écriture des résultats du test.
GRANT SELECT (dossier, empreinte_cle, fin_jeton, duree, expire_le, etat, motif, societe_nom, societe_id,
              societe_attendue, droits, teste_le, enregistre_par, enregistre_le) ON connexions_pennylane TO authenticated;
GRANT INSERT (dossier, jeton_chiffre, empreinte_cle, fin_jeton, duree) ON connexions_pennylane TO authenticated;
GRANT UPDATE (dossier, jeton_chiffre, empreinte_cle, fin_jeton, duree) ON connexions_pennylane TO authenticated;
GRANT DELETE ON connexions_pennylane TO authenticated;

-- ------------------------------------------------------------------ synchronisations : type de demande
ALTER TABLE synchronisations ADD COLUMN IF NOT EXISTS type text NOT NULL DEFAULT 'synchro';
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'synchronisations_type') THEN
    ALTER TABLE synchronisations ADD CONSTRAINT synchronisations_type CHECK (type IN ('synchro', 'test'));
  END IF;
END
$$;

-- ===================== migrations/012_suivi_kpi_parametrable.sql =====================
-- Migration 012 : suivi KPI paramétrable (lot 20, décision 0014). SQL standard PostgreSQL, rejouable.
-- S'ajoute aux migrations 001 à 011 sans remise à zéro.
--
-- kpi_modeles       : modèles de suivi (Tourisme, Seniors, Étudiants…). Lecture : toute personne connectée ;
--                     écriture : administrateur.
-- kpi_catalogue     : données (saisies ou importées chaque mois) et indicateurs (calculés, jamais importés :
--                     facteur x somme(numérateur) / somme(dénominateur)). Le code est stable : il ne change jamais.
--                     La base refuse un indicateur qui utilise une donnée inconnue, un modèle inconnu, la
--                     désactivation d'une donnée utilisée par un indicateur actif, et la suppression d'une donnée
--                     qui a des valeurs importées (on la désactive). Lecture : connectés ; écriture : administrateur.
-- kpi_journal       : chaque création, modification ou suppression du catalogue (avant / après, auteur, date),
--                     écrit par la base seule. Lecture : administrateur.
-- residence_modele  : modèle de suivi de chaque résidence (dossier). Lecture selon le parc ; écriture admin.
-- mesures_importees : une valeur négative n'est acceptée que pour une donnée « signée » du catalogue (montants).

CREATE TABLE IF NOT EXISTS kpi_modeles (
    id      text PRIMARY KEY CHECK (id ~ '^[A-Z0-9_]{2,30}$'),
    libelle text NOT NULL CHECK (length(libelle) BETWEEN 1 AND 60),
    ordre   integer NOT NULL DEFAULT 0,
    actif   boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS kpi_catalogue (
    code              text PRIMARY KEY CHECK (code ~ '^[A-Z0-9_]{2,40}$'),
    type              text NOT NULL CHECK (type IN ('donnee', 'indicateur')),
    libelle           text NOT NULL CHECK (length(libelle) BETWEEN 1 AND 120),
    rubrique          text NOT NULL DEFAULT 'Autres' CHECK (length(rubrique) BETWEEN 1 AND 60),
    ordre             integer NOT NULL DEFAULT 0,
    unite             text NOT NULL DEFAULT 'nombre' CHECK (unite IN ('nombre', 'euro', 'pourcent', 'jours', 'ratio')),
    actif             boolean NOT NULL DEFAULT true,
    modeles           text[] NOT NULL DEFAULT '{}',
    colonne_consolide text CHECK (colonne_consolide IS NULL OR length(colonne_consolide) BETWEEN 1 AND 120),
    signe             text NOT NULL DEFAULT 'positif' CHECK (signe IN ('positif', 'signe')),
    numerateur        text[] NOT NULL DEFAULT '{}',
    denominateur      text[] NOT NULL DEFAULT '{}',
    facteur           numeric NOT NULL DEFAULT 1 CHECK (facteur <> 0),
    sens              text CHECK (sens IS NULL OR sens IN ('haut', 'bas')),
    seuil             numeric,
    description       text NOT NULL DEFAULT '' CHECK (length(description) <= 500),
    version           integer NOT NULL DEFAULT 1,
    modifie_par       text,
    modifie_le        timestamptz NOT NULL DEFAULT now(),
    CHECK (type = 'indicateur' OR (cardinality(numerateur) = 0 AND cardinality(denominateur) = 0)),
    CHECK (type = 'donnee' OR cardinality(numerateur) >= 1)
);

CREATE TABLE IF NOT EXISTS kpi_journal (
    id     bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    code   text NOT NULL,
    action text NOT NULL CHECK (action IN ('création', 'modification', 'suppression')),
    avant  jsonb,
    apres  jsonb,
    par    text,
    le     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS residence_modele (
    dossier     text PRIMARY KEY CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    modele      text NOT NULL REFERENCES kpi_modeles(id) ON UPDATE CASCADE,
    modifie_par text,
    modifie_le  timestamptz NOT NULL DEFAULT now()
);

-- Contrôles du catalogue (la base reste seule juge, quelle que soit la page).
CREATE OR REPLACE FUNCTION controle_kpi_catalogue() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE x text; utilise text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    SELECT string_agg(code, ', ') INTO utilise FROM kpi_catalogue
      WHERE type = 'indicateur' AND (OLD.code = ANY(numerateur) OR OLD.code = ANY(denominateur));
    IF utilise IS NOT NULL THEN
      RAISE EXCEPTION 'donnée % utilisée par : % (retirez-la d''abord des formules)', OLD.code, utilise USING ERRCODE = '23503';
    END IF;
    IF EXISTS (SELECT 1 FROM mesures_importees WHERE mesure = OLD.code) THEN
      RAISE EXCEPTION 'donnée % : des valeurs sont déjà importées ; désactivez-la au lieu de la supprimer', OLD.code USING ERRCODE = '23503';
    END IF;
    RETURN OLD;
  END IF;
  IF TG_OP = 'UPDATE' AND (NEW.code <> OLD.code OR NEW.type <> OLD.type) THEN
    RAISE EXCEPTION 'le code et le type d''un élément du catalogue ne changent jamais (créez-en un nouveau)' USING ERRCODE = '23514';
  END IF;
  FOREACH x IN ARRAY NEW.modeles LOOP
    IF NOT EXISTS (SELECT 1 FROM kpi_modeles WHERE id = x) THEN
      RAISE EXCEPTION 'modèle de suivi inconnu : %', x USING ERRCODE = '23503';
    END IF;
  END LOOP;
  IF NEW.type = 'indicateur' THEN
    FOREACH x IN ARRAY NEW.numerateur || NEW.denominateur LOOP
      IF NOT EXISTS (SELECT 1 FROM kpi_catalogue WHERE code = x AND type = 'donnee') THEN
        RAISE EXCEPTION 'formule de % : % n''est pas une donnée du catalogue', NEW.code, x USING ERRCODE = '23503';
      END IF;
    END LOOP;
  ELSIF TG_OP = 'UPDATE' AND OLD.actif AND NOT NEW.actif THEN
    SELECT string_agg(code, ', ') INTO utilise FROM kpi_catalogue
      WHERE type = 'indicateur' AND actif AND (NEW.code = ANY(numerateur) OR NEW.code = ANY(denominateur));
    IF utilise IS NOT NULL THEN
      RAISE EXCEPTION 'donnée % utilisée par des indicateurs actifs : %', NEW.code, utilise USING ERRCODE = '23514';
    END IF;
  END IF;
  NEW.modifie_par := coalesce(email_courant(), NEW.modifie_par);
  NEW.modifie_le := now();
  IF TG_OP = 'UPDATE' THEN NEW.version := OLD.version + 1; END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS kpi_catalogue_controle ON kpi_catalogue;
CREATE TRIGGER kpi_catalogue_controle BEFORE INSERT OR UPDATE OR DELETE ON kpi_catalogue
  FOR EACH ROW EXECUTE FUNCTION controle_kpi_catalogue();

-- Journal écrit par la base seule (personne ne peut y écrire directement).
CREATE OR REPLACE FUNCTION journal_kpi_catalogue() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO kpi_journal (code, action, avant, apres, par)
  VALUES (coalesce(NEW.code, OLD.code),
          CASE TG_OP WHEN 'INSERT' THEN 'création' WHEN 'UPDATE' THEN 'modification' ELSE 'suppression' END,
          CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END,
          CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END,
          email_courant());
  RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS kpi_catalogue_journal ON kpi_catalogue;
CREATE TRIGGER kpi_catalogue_journal AFTER INSERT OR UPDATE OR DELETE ON kpi_catalogue
  FOR EACH ROW EXECUTE FUNCTION journal_kpi_catalogue();

CREATE OR REPLACE FUNCTION trace_residence_modele() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.modifie_par := coalesce(email_courant(), NEW.modifie_par); NEW.modifie_le := now();
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS residence_modele_trace ON residence_modele;
CREATE TRIGGER residence_modele_trace BEFORE INSERT OR UPDATE ON residence_modele
  FOR EACH ROW EXECUTE FUNCTION trace_residence_modele();

-- Valeurs importées : négatives seulement pour une donnée signée (remplace la règle « CA_... » du lot 19).
CREATE OR REPLACE FUNCTION controle_signe_mesure() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NEW.valeur < 0 AND NOT EXISTS (SELECT 1 FROM kpi_catalogue WHERE code = NEW.mesure AND signe = 'signe')
     AND NEW.mesure NOT LIKE 'CA\_%' THEN
    RAISE EXCEPTION 'valeur négative refusée pour % (donnée non signée)', NEW.mesure USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$$;
ALTER TABLE mesures_importees DROP CONSTRAINT IF EXISTS mesures_importees_valeur_signe;
DROP TRIGGER IF EXISTS mesures_importees_signe ON mesures_importees;
CREATE TRIGGER mesures_importees_signe BEFORE INSERT OR UPDATE ON mesures_importees
  FOR EACH ROW EXECUTE FUNCTION controle_signe_mesure();

ALTER TABLE kpi_modeles ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_catalogue ENABLE ROW LEVEL SECURITY;
ALTER TABLE kpi_journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE residence_modele ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS kpi_modeles_lecture ON kpi_modeles;
CREATE POLICY kpi_modeles_lecture ON kpi_modeles FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS kpi_modeles_admin ON kpi_modeles;
CREATE POLICY kpi_modeles_admin ON kpi_modeles FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());
DROP POLICY IF EXISTS kpi_catalogue_lecture ON kpi_catalogue;
CREATE POLICY kpi_catalogue_lecture ON kpi_catalogue FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS kpi_catalogue_admin ON kpi_catalogue;
CREATE POLICY kpi_catalogue_admin ON kpi_catalogue FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur());
DROP POLICY IF EXISTS kpi_journal_lecture ON kpi_journal;
CREATE POLICY kpi_journal_lecture ON kpi_journal FOR SELECT TO authenticated USING (est_administrateur());
DROP POLICY IF EXISTS residence_modele_lecture ON residence_modele;
CREATE POLICY residence_modele_lecture ON residence_modele FOR SELECT TO authenticated USING (voit_dossier(dossier));
DROP POLICY IF EXISTS residence_modele_admin ON residence_modele;
CREATE POLICY residence_modele_admin ON residence_modele FOR ALL TO authenticated
  USING (est_administrateur()) WITH CHECK (est_administrateur() AND voit_dossier(dossier));

REVOKE ALL ON kpi_modeles, kpi_catalogue, kpi_journal, residence_modele FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON kpi_modeles, kpi_catalogue, residence_modele TO authenticated;
REVOKE INSERT, UPDATE, DELETE ON kpi_journal FROM authenticated;
GRANT SELECT ON kpi_journal TO authenticated;

-- Catalogue de départ (repris du consolidé KPI, lot 19) : ajouté une seule fois, jamais écrasé.
-- >>> amorce générée par interface/catalogue_kpi.py (ne pas modifier à la main)
INSERT INTO kpi_modeles (id, libelle, ordre) VALUES
  ('TOURISME', 'Tourisme (RT)', 1),
  ('SENIORS', 'Seniors', 2),
  ('ETUDIANTS', 'Étudiants', 3)
ON CONFLICT (id) DO NOTHING;
INSERT INTO kpi_catalogue (code, type, libelle, rubrique, ordre, unite, actif, modeles, colonne_consolide, signe, numerateur, denominateur, facteur, sens, seuil) VALUES
  ('LN_VENDUES', 'donnee', 'Nuitées totales', 'Hébergement', 100, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Nuitées totales', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LN_DISPONIBLES', 'donnee', 'Capacité totale (lots × jours)', 'Hébergement', 110, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Capacité totale', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LOTS_HOT', 'donnee', 'Lots hôteliers', 'Hébergement', 120, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Lots hôtelier', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LN_VENDUES_HOT', 'donnee', 'Chambres vendues hôtelières', 'Hébergement', 130, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Chambres vendues hôtelières', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LN_DISPO_HOT', 'donnee', 'Capacité hôtelière (lots × jours)', 'Hébergement', 140, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Capacité hôtelière (lots × jours)', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('NB_SEJOURS', 'donnee', 'Nombre de réservations', 'Hébergement', 150, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Nb de réservations', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('NUITEES_CLIENTS', 'donnee', 'Clients présents', 'Hébergement', 160, 'nombre', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'Clients présents', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LOTS_SEN', 'donnee', 'Lots seniors', 'Seniors', 170, 'nombre', true, ARRAY['SENIORS']::text[], 'Lots seniors', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LOTS_SEN_OCC', 'donnee', 'Lots seniors occupés', 'Seniors', 180, 'nombre', true, ARRAY['SENIORS']::text[], 'Lots seniors occupés', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('NUITEES_SEN', 'donnee', 'Nuitées seniors', 'Seniors', 190, 'nombre', true, ARRAY['SENIORS']::text[], 'Nuitées seniors', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('LN_DISPO_SEN', 'donnee', 'Capacité seniors', 'Seniors', 200, 'nombre', true, ARRAY['SENIORS']::text[], 'Capacité seniors', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_HEB_SEN', 'donnee', 'CA hébergement seniors HT', 'Seniors', 210, 'euro', true, ARRAY['SENIORS']::text[], 'CA hébergement seniors HT', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_SAP', 'donnee', 'CA SAP HT', 'Seniors', 220, 'euro', true, ARRAY['SENIORS']::text[], 'CA SAP', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_RESTO_SEN', 'donnee', 'CA restauration seniors HT', 'Seniors', 230, 'euro', true, ARRAY['SENIORS']::text[], 'CA Restauration seniors', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('COUVERTS_PDJ', 'donnee', 'Petits-déjeuners servis', 'Restauration', 240, 'nombre', true, ARRAY['TOURISME', 'SENIORS']::text[], 'Nb PDJ', 'positif', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_PDJ', 'donnee', 'CA petit-déjeuner HT', 'Restauration', 250, 'euro', true, ARRAY['TOURISME', 'SENIORS']::text[], 'CA HT PDJ', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_RESTO', 'donnee', 'CA restaurant HT', 'Restauration', 260, 'euro', true, ARRAY['TOURISME', 'SENIORS']::text[], 'CA HT RESTO', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_TOTAL', 'donnee', 'CA total résidence HT', 'Chiffre d''affaires', 270, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'CA total résidence HT', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_HOTELIER', 'donnee', 'CA total hôtelier HT', 'Chiffre d''affaires', 280, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'CA total hôtelier HT', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_HEB_HOT', 'donnee', 'CA hébergement hôtelier HT', 'Chiffre d''affaires', 290, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'CA hébergement hôtelier HT', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('CA_MEWS_SPA', 'donnee', 'CA spa HT', 'Chiffre d''affaires', 300, 'euro', true, ARRAY['TOURISME']::text[], 'CA HT SPA', 'signe', '{}'::text[], '{}'::text[], 1, NULL, NULL),
  ('TO_RES', 'indicateur', 'Taux d''occupation de la résidence', 'Hébergement', 10, 'pourcent', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'TO résidence', 'positif', ARRAY['LN_VENDUES']::text[], ARRAY['LN_DISPONIBLES']::text[], 1, 'haut', NULL),
  ('TO_HOT', 'indicateur', 'Taux d''occupation hôtelier', 'Hébergement', 20, 'pourcent', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'TO hôtelier', 'positif', ARRAY['LN_VENDUES_HOT']::text[], ARRAY['LN_DISPO_HOT']::text[], 1, 'haut', NULL),
  ('PM', 'indicateur', 'Prix moyen chambre', 'Hébergement', 30, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'PM', 'positif', ARRAY['CA_MEWS_HEB_HOT']::text[], ARRAY['LN_VENDUES_HOT']::text[], 1, 'haut', NULL),
  ('REVPAR', 'indicateur', 'RevPar', 'Hébergement', 40, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'RevPar', 'positif', ARRAY['CA_MEWS_HEB_HOT']::text[], ARRAY['LN_DISPO_HOT']::text[], 1, 'haut', NULL),
  ('REVPAC', 'indicateur', 'RevPac', 'Hébergement', 50, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'RevPac', 'positif', ARRAY['CA_MEWS_HOTELIER']::text[], ARRAY['NUITEES_CLIENTS']::text[], 1, 'haut', NULL),
  ('DMS', 'indicateur', 'Durée moyenne de séjour', 'Hébergement', 60, 'jours', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], 'DMS', 'positif', ARRAY['LN_VENDUES_HOT']::text[], ARRAY['NB_SEJOURS']::text[], 1, 'haut', NULL),
  ('TO_SEN', 'indicateur', 'Taux d''occupation seniors', 'Seniors', 70, 'pourcent', true, ARRAY['SENIORS']::text[], 'TO seniors', 'positif', ARRAY['NUITEES_SEN']::text[], ARRAY['LN_DISPO_SEN']::text[], 1, 'haut', NULL),
  ('CAPTAGE_PDJ', 'indicateur', 'Taux de captage petit-déjeuner', 'Restauration', 80, 'pourcent', true, ARRAY['TOURISME', 'SENIORS']::text[], 'Captage PDJ', 'positif', ARRAY['COUVERTS_PDJ']::text[], ARRAY['NUITEES_CLIENTS']::text[], 1, 'haut', NULL),
  ('CA_TOTAL', 'indicateur', 'CA total de la résidence', 'Chiffre d''affaires', 90, 'euro', true, ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[], NULL, 'positif', ARRAY['CA_MEWS_TOTAL']::text[], '{}'::text[], 1, 'haut', NULL)
ON CONFLICT (code) DO NOTHING;
-- <<< fin de l'amorce

-- ===================== migrations/013_modele_mixte.sql =====================
-- Migration 013 : modèle de suivi « Mixte » pour les résidences qui exercent plusieurs activités (lot 21,
-- décision 0015). SQL standard PostgreSQL, rejouable, sans remise à zéro.
--
-- Une résidence mixte suit tout ce que suivent les autres modèles d'activité : le modèle MIXTE est ajouté à
-- chaque donnée et à chaque indicateur suivi par Tourisme, Seniors ou Étudiants. On peut ensuite le retirer
-- d'un élément dans Paramètres KPI. La base journalise ces modifications (kpi_journal, auteur « système »).

INSERT INTO kpi_modeles (id, libelle, ordre) VALUES ('MIXTE', 'Mixte (plusieurs activités)', 4)
ON CONFLICT (id) DO NOTHING;

-- Données d'abord : la base refuse un indicateur suivi par un modèle qui ne suit pas ses données (contrôle de la
-- page ; la base vérifie l'existence des données).
UPDATE kpi_catalogue SET modeles = array_append(modeles, 'MIXTE')
WHERE type = 'donnee' AND NOT ('MIXTE' = ANY(modeles)) AND modeles && ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[];
UPDATE kpi_catalogue SET modeles = array_append(modeles, 'MIXTE')
WHERE type = 'indicateur' AND NOT ('MIXTE' = ANY(modeles)) AND modeles && ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[];

-- ===================== migrations/014_retrait_jetons_chiffres.sql =====================
-- Migration 014 - retrait des jetons Pennylane chiffrés dans le logiciel (décision 0017).
-- Les jetons Pennylane (lecture seule) ne sont plus saisis dans la page : ils sont rangés dans les secrets
-- GitHub du dépôt. Cette migration retire ce que le lot 19 (migration 011) avait ajouté pour eux.
-- Rejouable sans effet : tout est « IF EXISTS ». Aucune donnée comptable ni KPI n'est touchée.

-- Connexions Pennylane (jetons chiffrés) et clé publique de chiffrement.
DROP TABLE IF EXISTS connexions_pennylane;
DROP TABLE IF EXISTS cle_jetons;
DROP FUNCTION IF EXISTS trace_connexion_pennylane();
DROP FUNCTION IF EXISTS trace_cle_jetons();

-- Demandes de synchronisation : plus de demande de « test des jetons ».
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'synchronisations' AND column_name = 'type') THEN
    DELETE FROM synchronisations WHERE type = 'test';
    ALTER TABLE synchronisations DROP CONSTRAINT IF EXISTS synchronisations_type;
    ALTER TABLE synchronisations DROP COLUMN type;
  END IF;
END
$$;

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

-- ===================== scripts/lot18_residence_test.sql =====================
-- Lot 18 (décision 0011) : résidence du dossier Pennylane de test (PENNY-TEST).
-- Sur une base déjà installée : coller ce fichier dans Supabase, SQL Editor (ne supprime rien, peut être
-- relancé sans créer de doublon). Il est aussi inclus à la fin de scripts/installation_supabase.sql.
-- Gardé à part de donnees_test.sql : les huit résidences de démonstration restent la référence des tests.
-- Marquée fictive (aucune donnée confidentielle) ; hors de tout groupe : visible des seuls administrateurs.
INSERT INTO residences (id, libelle, dossier_pennylane, fictif) VALUES
  ('RES-TEST', 'Dossier Pennylane de test', 'PENNY-TEST', true)
ON CONFLICT (id) DO NOTHING;
