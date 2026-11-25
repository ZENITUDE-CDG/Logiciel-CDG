-- Migration 013 : modèle de suivi « Mixte » pour les résidences qui exercent plusieurs activités (lot 21,
-- décision 0015). SQL standard PostgreSQL, rejouable, sans remise à zéro.
--
-- Une résidence mixte suit tout ce que suivent les autres modèles d'activité : le modèle MIXTE est ajouté à
-- chaque donnée et à chaque indicateur suivi par Tourisme, Seniors ou Étudiants. On peut ensuite le retirer
-- d'un élément dans Paramètres KPI. La base journalise ces modifications (kpi_journal, auteur « système »).

INSERT INTO kpi_modeles (id, libelle, ordre) VALUES ('MIXTE', 'Mixte (plusieurs activités)', 4)
ON CONFLICT (id) DO NOTHING;

-- Données d'abord : la base refuse un indicateur suivi par un modèle qui ne suit pas ses données (contrôle de la
-- page ; la base vérifie l'existence des données).
UPDATE kpi_catalogue SET modeles = array_append(modeles, 'MIXTE')
WHERE type = 'donnee' AND NOT ('MIXTE' = ANY(modeles)) AND modeles && ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[];
UPDATE kpi_catalogue SET modeles = array_append(modeles, 'MIXTE')
WHERE type = 'indicateur' AND NOT ('MIXTE' = ANY(modeles)) AND modeles && ARRAY['TOURISME', 'SENIORS', 'ETUDIANTS']::text[];
