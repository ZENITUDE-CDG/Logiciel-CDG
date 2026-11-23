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
