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
