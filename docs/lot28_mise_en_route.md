# Lots 28 à 30 - Analyse des écarts (décision 0022)

Ajoute la section **Analyse des écarts** (après Tableaux de bord) : dix pages, suivi des écarts, seuils, paquet
d'écarts pour Claude. Règles : `docs/analyse_ecarts.md`. La base n'est PAS remise à zéro.

## 1. GitHub
Déposer le contenu de l'archive en gardant les dossiers (nouveaux : `zenitude/analyse/`, `tests/lot28/`), puis
**Commit changes**. Vérifier les deux coches vertes dans Actions.

## 2. Supabase : migration 019
**SQL Editor** : coller tout `migrations/019_analyse_ecarts.sql`, **Run** (« Success. No rows returned »). Rejouable.
Sans elle, les pages s'affichent mais les statuts, commentaires et seuils ne s'enregistrent pas (bandeau en haut de
« Écarts à expliquer »).

## 3. Essai
1. Choisir un groupe, puis **Analyse des écarts, Écarts à expliquer**.
2. **Comparer à** : sur la démonstration (comptabilité depuis octobre 2025), prendre « Période précédente » ou une
   période à partir d'octobre 2026 pour N-1.
3. Cliquer un effet : calcul, éléments, écritures. **Commenter** : statut et commentaire, gardés et historisés.
4. **Seuils et références** (administrateurs) : régler les seuils et la référence proposée.
5. **Télécharger le paquet d'écarts** : le joindre à Claude avec la mission « Commentaire des écarts »
   (exemple dans `docs/missions_claude.md`, à enregistrer dans Missions Claude). Le document produit se note dans
   Rapports, Paquet pour Claude.

## 4. Données utiles
- Nuitées vendues, logements-nuits disponibles, clients présents, petits-déjeuners : effets volume et prix, coûts
  unitaires (Données externes).
- CA_MEWS_TOTAL, CA_MEWS_RESTO, CA_MEWS_PDJ : rapprochement du CA comptable avec Mews.
- DSN importées : cohérence compta et paie (administrateurs).
