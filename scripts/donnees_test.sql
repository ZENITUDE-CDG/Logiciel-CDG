-- Données de départ de la phase test (lots 12 et 13). Tout est fictif sauf les deux adresses
-- autorisées par la décision 0004. Peut être relancé sans créer de doublons.
--
-- Résidences : les huit résidences de démonstration (interface/demo, generer_demo.py), dont les
-- chiffres sont publiés par GitHub Actions (décision 0007). Les résidences de test RES-901 et
-- RES-902 du lot 12 sont supprimées (nettoyage du 23 novembre 2026).
--
-- Démonstration : Raphael est administrateur et voit tout ; Benjamin est collaborateur, son parc
-- est le groupe des résidences seniors : il ne voit que RES-003, RES-004 et RES-005.
--
-- Lot 18 (décision 0011) : RES-TEST = dossier Pennylane de test (PENNY-TEST), sans donnée confidentielle,
-- marqué fictif ; hors de tout groupe, donc visible des seuls administrateurs.

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
  ('RES-008', 'Les Hauts de Loire (fictif)',     'DEMO-2008', true),
  ('RES-TEST', 'Dossier Pennylane de test',      'PENNY-TEST', true)
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
