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
