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
