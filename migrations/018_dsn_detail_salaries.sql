-- Migration 018 : détail pseudonymisé par salarié et référentiel des postes (lot 27, décision 0021).
-- SQL standard PostgreSQL, rejouable. S'ajoute aux migrations 001 à 017 sans remise à zéro.
--
-- dsn_mois.contenu peut désormais porter une ligne par salarié (contenu.salaries) : identifiant pseudonyme
-- (empreinte tronquée), emploi, niveau, statut, contrat, sexe, âge, ancienneté en mois, ETP, brut, heures, primes,
-- net. Jamais de nom, prénom, NIR, matricule ni date de naissance : la base refuse une ligne qui en contient.
-- Taille maximale d'un mois relevée (grands établissements).
--
-- dsn_postes : rattachement d'un libellé d'emploi de la paie à un poste standard et à une famille.
-- Droits : administrateurs (lecture et écriture), comme toutes les données de paie.

ALTER TABLE dsn_mois DROP CONSTRAINT IF EXISTS dsn_mois_contenu_check;
ALTER TABLE dsn_mois DROP CONSTRAINT IF EXISTS dsn_mois_contenu_controle;
ALTER TABLE dsn_mois ADD CONSTRAINT dsn_mois_contenu_controle CHECK (
  jsonb_typeof(contenu) = 'object' AND contenu ? 'effectif_fin' AND contenu ? 'brut'
  AND NOT (contenu ?| ARRAY['nir', 'nom', 'prenoms', 'nom_famille', 'matricule', 'individus'])
  AND NOT jsonb_path_exists(contenu, '$.salaries[*] ? (exists(@.nir) || exists(@.nom) || exists(@.prenoms) || exists(@.matricule) || exists(@.naissance))')
  AND octet_length(contenu::text) <= 3000000);

CREATE TABLE IF NOT EXISTS dsn_postes (
    emploi      text PRIMARY KEY CHECK (length(emploi) <= 200),
    poste       text NOT NULL CHECK (length(btrim(poste)) BETWEEN 1 AND 120),
    famille     text NOT NULL CHECK (famille IN ('Direction', 'Réception', 'Hébergement et ménage', 'Restauration', 'Maintenance',
                                                 'Soins et animation', 'Commercial', 'Administratif', 'Autre')),
    modifie_par text,
    modifie_le  timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION trace_dsn_poste() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  NEW.modifie_par := coalesce(email_courant(), NEW.modifie_par);
  NEW.modifie_le := now();
  IF TG_OP = 'INSERT' OR (NEW.poste, NEW.famille) IS DISTINCT FROM (OLD.poste, OLD.famille) THEN
    INSERT INTO dsn_journal (action, siret, detail, par)
    VALUES ('référentiel', '-', NEW.emploi || ' → ' || NEW.poste || ' (' || NEW.famille || ')', NEW.modifie_par);
  END IF;
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS dsn_postes_trace ON dsn_postes;
CREATE TRIGGER dsn_postes_trace BEFORE INSERT OR UPDATE ON dsn_postes FOR EACH ROW EXECUTE FUNCTION trace_dsn_poste();

ALTER TABLE dsn_postes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dsn_postes_admin ON dsn_postes;
CREATE POLICY dsn_postes_admin ON dsn_postes FOR ALL TO authenticated USING (est_administrateur()) WITH CHECK (est_administrateur());
GRANT SELECT, INSERT, UPDATE, DELETE ON dsn_postes TO authenticated;
