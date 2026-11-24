-- Lot 18 (décision 0011) : ajoute la résidence du dossier Pennylane de test dans une base déjà installée.
-- À coller dans Supabase, SQL Editor. Ne supprime rien, peut être relancé sans créer de doublon.
-- Marquée fictive (aucune donnée confidentielle) ; hors de tout groupe : visible des seuls administrateurs.
INSERT INTO residences (id, libelle, dossier_pennylane, fictif) VALUES
  ('RES-TEST', 'Dossier Pennylane de test', 'PENNY-TEST', true)
ON CONFLICT (id) DO NOTHING;

SELECT id, libelle, dossier_pennylane, fictif FROM residences WHERE id = 'RES-TEST';
