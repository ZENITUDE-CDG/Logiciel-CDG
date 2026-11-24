-- Lot 18 (décision 0011) : résidence du dossier Pennylane de test (PENNY-TEST).
-- Sur une base déjà installée : coller ce fichier dans Supabase, SQL Editor (ne supprime rien, peut être
-- relancé sans créer de doublon). Il est aussi inclus à la fin de scripts/installation_supabase.sql.
-- Gardé à part de donnees_test.sql : les huit résidences de démonstration restent la référence des tests.
-- Marquée fictive (aucune donnée confidentielle) ; hors de tout groupe : visible des seuls administrateurs.
INSERT INTO residences (id, libelle, dossier_pennylane, fictif) VALUES
  ('RES-TEST', 'Dossier Pennylane de test', 'PENNY-TEST', true)
ON CONFLICT (id) DO NOTHING;
