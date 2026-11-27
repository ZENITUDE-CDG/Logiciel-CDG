# Lot 26 - DSN et indicateurs sociaux (décision 0020)

Ajoute la section **Social** (tableau de bord social, effectifs et mouvements, absentéisme, paie et comptabilité)
et la page **Import et paramètres, Import DSN**, réservées aux administrateurs. La base n'est PAS remise à zéro.

## 1. GitHub : déposer les fichiers de l'archive
Glisser-déposer le contenu de l'archive dans le dépôt en gardant les dossiers (nouveaux dossiers
`zenitude/social/`, `tests/lot26/` et `interface/demo/dsn/`), puis **Commit changes**.
Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes (la suite reconstruit sa propre base
avec la migration 017).

## 2. Supabase : migration 017
**SQL Editor, New query** : coller tout `migrations/017_dsn.sql`, **Run**. Résultat attendu : « Success. No rows
returned ». Elle crée `dsn_etablissements`, `dsn_mois` et `dsn_journal` et peut être relancée sans effet.
(Ne pas utiliser `installation_supabase.sql`, qui remet tout à zéro.)

## 3. Essayer avec les DSN fictives
1. **Import et paramètres, Import DSN, Choisir les fichiers…** : sélectionner les 13 fichiers de
   `interface/demo/dsn/` (à télécharger depuis le dépôt ou l'archive).
2. Rattacher chaque SIRET à sa résidence (le SIRET fictif `9990020XX00011` correspond à `DEMO-20XX`), puis
   **Enregistrer**.
3. Ouvrir **Social**. Anomalies volontaires à retrouver dans « Paie et comptabilité » : écart de 1 234,56 € pour
   Les Tilleuls en juin 2026, DSN manquante pour Les Marronniers en février 2026 ; dans les alertes, un salarié sans
   quotité (Le Jardin des Sciences, mars 2026).

## 4. Avec Silae
Exporter les DSN mensuelles déposées (fichier .dsn ou .txt), un ou plusieurs mois, et les déposer de la même façon.
Seuls les totaux sont enregistrés. **Avant tout fichier réel : accord DSI et DAF** (données de paie), puis
vérification des codes de `docs/dsn.md` sur un premier fichier.

## En cas de problème
- « Migration 017 non appliquée » : refaire l'étape 2, puis recharger la page.
- Section Social absente : le compte n'est pas administrateur.
- Ligne « Refusé » : le motif est affiché (DSN non mensuelle, annulation, fractionnée, montant illisible…).
- « Avertissement » sur le nombre de rubriques : fichier peut-être tronqué, le réexporter depuis Silae.
