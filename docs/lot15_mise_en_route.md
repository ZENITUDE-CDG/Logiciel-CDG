# Lot 15 - Mise en route (sans rien installer)

1. Supabase, **SQL Editor** : coller `migrations/006_kpi_et_comptes_bancaires.sql`, **Run**. Rien n'est effacé.
   (Sur une base vide ou pour tout remettre à zéro : `scripts/installation_supabase.sql`, lots 12 à 15.)
2. GitHub : déposer **tout** le contenu du dossier de l'archive, fichiers à la racine compris (`index.html`,
   `CLAUDE.md`...) et le nouveau dossier `modeles`. Le dépôt relance les tests puis la publication.
3. Vérifier : onglet Actions, deux coches vertes ; puis sur le site (Ctrl + F5) :
   - Trésorerie, **Comptes bancaires** (administrateurs) et **Analyse du solde** ;
   - Tableaux de bord, **FRNG, BFR et TN** ;
   - Synthèse : graphiques limités à la période de la réglette, tableau EBITDA au format du groupe ;
   - Import et paramètres, **Données externes** : télécharger le modèle, le remplir, l'importer.
