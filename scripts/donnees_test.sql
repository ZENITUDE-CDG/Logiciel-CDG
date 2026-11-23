-- Données de départ de la phase test (lot 12). Tout est fictif sauf les deux adresses
-- autorisées par la décision 0004. Peut être relancé sans créer de doublons.
--
-- Démonstration (décision 0006) : Raphael est administrateur et voit tout ;
-- Benjamin est collaborateur, son parc est le groupe pilote : il ne voit que la résidence pilote.

INSERT INTO profils (email, nom, role, fictif) VALUES
  ('raphael.bracq@zenitude-groupe.com',  'Raphael Bracq',    'administrateur', false),
  ('benjamin.gagneur@zenitude-groupe.com', 'Benjamin Gagneur', 'collaborateur',  false)
ON CONFLICT (email) DO NOTHING;

INSERT INTO residences (id, libelle, dossier_pennylane, fictif) VALUES
  ('RES-901', 'Résidence pilote (fictif)',    'PENNY-9001', true),
  ('RES-902', 'Résidence hors parc (fictif)', 'PENNY-9002', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO groupes (id, libelle, fictif) VALUES
  ('GRP-PILOTE', 'Groupe pilote (fictif)', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO residence_groupe (residence_id, groupe_id) VALUES ('RES-901', 'GRP-PILOTE')
ON CONFLICT DO NOTHING;

INSERT INTO parcs (utilisateur_email, groupe_id)
SELECT 'benjamin.gagneur@zenitude-groupe.com', 'GRP-PILOTE'
WHERE NOT EXISTS (SELECT 1 FROM parcs
                  WHERE utilisateur_email = 'benjamin.gagneur@zenitude-groupe.com'
                    AND groupe_id = 'GRP-PILOTE');
