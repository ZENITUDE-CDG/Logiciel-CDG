# Lot 19 - Mise en route (sans rien installer)

Dépôt du consolidé KPI (décision 0013). Les jetons Pennylane chiffrés dans le logiciel (étapes 4 et 5 de la version
d'origine) ont été retirés : voir `docs/lot23_mise_en_route.md` (décision 0017). La base n'est PAS remise à zéro.

## 1. GitHub : fichiers du lot
Déposer les fichiers de l'archive. Les fichiers dont le nom commence par un point ne passent pas par le
glisser-déposer : les ouvrir dans GitHub (crayon, Edit), remplacer tout le contenu par celui de l'archive,
**Commit changes** :
- `.github/workflows/synchro-pennylane-test.yml`
- `.github/workflows/tests-et-publication.yml`

Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes.

## 2. Supabase : migration 011
**SQL Editor, New query** : coller tout `migrations/011_kpi_consolide_et_connexions.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». (Ne pas utiliser `installation_supabase.sql`, qui remet tout à zéro.)

## 3. Supabase : mettre à jour la fonction serveur
**Edge Functions**, `lancer-synchro`, **Code** (ou *Edit*) : remplacer tout le code par le contenu de
`supabase/functions/lancer-synchro/index.ts`, **Deploy**. Les secrets et le réglage JWT du lot 18b ne changent pas.

## 4. Déposer le consolidé KPI
1. **Import et paramètres**, **Données externes**, choisir le périmètre dans le ruban (un groupe ou une
   résidence), **Choisir le fichier…**, sélectionner `Consolide_KPI_<année>.xlsx`.
2. L'aperçu indique les valeurs nouvelles, modifiées et identiques, les valeurs écartées, les ratios à vérifier
   et les statuts des mois.
3. **Résidences du fichier non rattachées** : choisir la résidence du logiciel en face de chaque nom, puis
   **Enregistrer les rattachements** (une seule fois : le code Mews est retenu).
4. **Groupes du fichier** (facultatif) : **Créer ou mettre à jour les groupes** (segments, régions, RM).
5. **Importer**. Les tableaux de bord en tiennent compte aussitôt ; la grille « Suivi des mois » et l'historique
   des dépôts se mettent à jour.

Phase test : seules les résidences présentes dans la base sont importées. Les résidences réelles n'y sont pas
encore (étape 2 de la décision 0013) ; ne pas rattacher de vraies résidences à des résidences de démonstration.

## En cas de problème
- « Migration 011 non appliquée » : étape 2.
- Dépôt KPI refusé : la première erreur est affichée (colonne manquante, mois illisible, ligne en double). Corriger
  dans l'outil KPI, puis redéposer. Rien n'est enregistré tant qu'une erreur reste.
