# Lot 21 - Mise en route (sans rien installer)

Allègement des pages d'import et modèle Mixte (décision 0015). La base n'est PAS remise à zéro.

## 1. GitHub : fichiers du lot
- Déposer les fichiers de l'archive (glisser-déposer, en respectant les dossiers).
- **Supprimer deux fichiers devenus inutiles** (ouvrir le fichier dans GitHub, menu « … » en haut à droite,
  **Delete file**, puis **Commit changes**) :
  - `interface/generer_modele_import.py`
  - `modeles/Zenitude_Import_KPI_modele.xlsx`
  (S'ils restent, rien ne casse : ils ne sont simplement plus utilisés.)
- Vérifier : **Actions**, « Tests et publication » avec deux coches vertes.

## 2. Supabase : migration 013
**SQL Editor, New query** : coller tout `migrations/013_modele_mixte.sql`, **Run** (« Success. No rows returned »).
Le modèle « Mixte (plusieurs activités) » est créé et ajouté à toutes les données et tous les indicateurs.

## 3. Dans le logiciel
- Recharger sans le cache (Ctrl+F5).
- **Paramètres KPI** : attribuer le modèle Mixte aux résidences qui exercent plusieurs activités ; retirer Mixte
  des éléments qu'elles ne doivent pas suivre (bouton **Modifier**).
