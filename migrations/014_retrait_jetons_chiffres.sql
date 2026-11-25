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
