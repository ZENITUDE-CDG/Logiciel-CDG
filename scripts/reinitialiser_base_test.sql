-- Remise à zéro de la BASE DE TEST Supabase (données fictives uniquement).
-- Supprime les tableaux et fonctions des lots 12 et 13, y compris ceux d'une version précédente.
-- Ne jamais exécuter sur une base contenant des données réelles.

DROP TABLE IF EXISTS ajustements, comptes_simules, donnees_residences, donnees_communes,
  parcs, residence_groupe, groupes, residences, profils CASCADE;

DROP FUNCTION IF EXISTS gere_ajustement(boolean, text[]), voit_ajustement(boolean, text[]),
  modifie_dossier(text), voit_dossier(text), ajustements_trace(),
  voit_groupe(text), voit_residence(text), modifie_residence(text),
  est_administrateur(), role_courant(), email_courant(), utilisateur_courant() CASCADE;

-- Rôle d'une version précédente du lot 12, devenu inutile.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_utilisateur') THEN
    BEGIN
      EXECUTE 'REVOKE ALL ON SCHEMA public FROM app_utilisateur';
      EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_utilisateur';
      EXECUTE 'DROP ROLE app_utilisateur';
    EXCEPTION WHEN others THEN
      RAISE NOTICE 'Rôle app_utilisateur non supprimé : %', SQLERRM;
    END;
  END IF;
END
$$;
