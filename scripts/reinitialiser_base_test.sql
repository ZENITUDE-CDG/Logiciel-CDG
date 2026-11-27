-- Remise à zéro de la BASE DE TEST Supabase (données fictives uniquement).
-- Supprime les tableaux et fonctions des lots 12 à 30, y compris ceux d'une version précédente.
-- Ne jamais exécuter sur une base contenant des données réelles.

DROP TABLE IF EXISTS ecarts_journal, ecarts_suivi, analyse_parametres, dsn_postes, dsn_journal, dsn_mois, dsn_etablissements, paquets_claude, missions_versions, missions_claude, virements_suivis, tresorerie_previsions, compta_journal, fees_clotures, ca_regles, fees_regles, fees_rubriques, residence_modele, kpi_journal, kpi_catalogue, kpi_modeles, connexions_pennylane, cle_jetons, depots_kpi, kpi_mois, pennylane_magasin, pennylane_etat, pennylane_ecritures, pennylane_lignes, lettrages_pennylane, synchronisations, parametres_import, mesures_importees, comptes_bancaires, lissages, ajustements, comptes_simules, donnees_residences, donnees_communes,
  parcs, residence_groupe, groupes, residences, profils CASCADE;

DROP FUNCTION IF EXISTS trace_ecart_suivi(), journal_ecart_suivi(), trace_analyse_parametres(), trace_dsn_poste(), trace_dsn_etablissement(), suivre_dsn_etablissement(), trace_dsn_mois(), journal_dsn_mois(), trace_mission_claude(), trace_paquet_claude(), controle_fees_rubrique(), trace_compta(), garde_cloture(), trace_virement(), journal_compta(), controle_kpi_catalogue(), journal_kpi_catalogue(), trace_residence_modele(), controle_signe_mesure(), trace_connexion_pennylane(), trace_cle_jetons(), trace_kpi(), garde_code_mews(), trace_lettrage(), trace_parametres_import(), trace_import(), gere_ajustement(boolean, text[]), voit_ajustement(boolean, text[]),
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
