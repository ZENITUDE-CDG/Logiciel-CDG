-- Migration 010 : écritures Pennylane conservées compressées (lot 18d, vitesse). SQL standard, rejouable.
--
-- Mesuré le 25 novembre 2026 sur le dossier de test : 35 863 lignes, une ligne de table par écriture,
-- 26 à 57 s pour relire, 32 à 55 s pour écrire. Les écritures sont désormais conservées en quelques morceaux
-- compressés (environ 1 Mo pour 36 000 lignes) : une ou deux requêtes.
-- pennylane_magasin : morceaux numérotés à partir de 0 ; pennylane_etat.morceaux en donne le nombre attendu
-- (des morceaux manquants provoquent une relecture complète). Aucun accès depuis la page.

CREATE TABLE IF NOT EXISTS pennylane_magasin (
    dossier  text NOT NULL CHECK (dossier ~ '^[A-Z0-9_-]+$'),
    morceau  integer NOT NULL CHECK (morceau >= 0),
    donnees  text NOT NULL,
    PRIMARY KEY (dossier, morceau)
);
ALTER TABLE pennylane_etat ADD COLUMN IF NOT EXISTS morceaux integer;
ALTER TABLE pennylane_magasin ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pennylane_magasin FROM anon, authenticated;

-- Tables d'une ligne par écriture (migration 009), remplacées par pennylane_magasin. L'état est effacé :
-- la synchronisation suivante fait une lecture complète et remplit pennylane_magasin.
DROP TABLE IF EXISTS pennylane_lignes, pennylane_ecritures;
DELETE FROM pennylane_etat;
