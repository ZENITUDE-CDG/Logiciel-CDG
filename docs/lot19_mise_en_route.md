# Lot 19 - Mise en route (sans rien installer)

Dépôt du consolidé KPI et jetons Pennylane par dossier (décision 0013). Tout se fait dans le navigateur, dans cet
ordre. La base n'est PAS remise à zéro.

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

## 4. Créer la clé de chiffrement des jetons (une seule fois)
1. Ouvrir le site, se connecter en administrateur, **Import et paramètres**, **Import comptable**.
2. Bloc « Connexions Pennylane » : **Créer la clé de chiffrement**. Une fenêtre affiche la clé privée.
3. **Copier la clé privée**. Dans GitHub : **Settings**, **Secrets and variables**, **Actions**,
   **New repository secret**. Nom : `PENNYLANE_CLE_PRIVEE` ; valeur : la clé entière, lignes
   `-----BEGIN PRIVATE KEY-----` et `-----END PRIVATE KEY-----` comprises ; **Add secret**.
4. Revenir sur le site, cocher la case, **Enregistrer la clé publique**. Fermer la fenêtre efface la clé privée
   de la page : elle n'existe plus que dans GitHub.

Si la clé privée est perdue : **Remplacer la clé**, puis ressaisir tous les jetons.

## 5. Enregistrer un jeton (par résidence)
1. Dans Pennylane, dossier de la résidence : **Paramètres**, **Connectivité**, **Développeurs**,
   **Générer un jeton API**. Nom : `Logiciel CDG` ; droits : **Lecture seule** ; durée : 12 mois (conseillé).
   Copier le jeton (Pennylane ne le montre qu'une fois).
2. Dans le logiciel, sur la ligne de la résidence : **Saisir le jeton**, coller, choisir la même durée,
   **Chiffrer et enregistrer**. Le jeton est chiffré dans le navigateur avant l'envoi et ne sera plus affiché.
3. Un test part aussitôt (moins d'une minute) : la ligne affiche la société Pennylane et « connectée », ou
   « refusée » avec le motif. Vérifier que la société affichée est bien celle de la résidence.

Commencer par le dossier de test (il remplace alors le secret `PENNYLANE_TOKEN_PILOTE`, qui reste en secours),
puis deux ou trois vraies résidences. **Pour les vraies résidences, seul le test est fait** : leur comptabilité ne
sera lue qu'après approbation de l'étape 2 de la décision 0013 (données réelles dans la base).

## 6. Déposer le consolidé KPI
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
- Test des jetons « en échec : secret GitHub PENNYLANE_CLE_PRIVEE absent » ou « ne correspond pas » : étape 4.3
  (recopier la clé entière, ou remplacer la clé et ressaisir les jetons).
- « jeton avec des droits d'écriture » : recréer le jeton dans Pennylane en **Lecture seule** (le logiciel a
  effacé l'ancien).
- « société déjà rattachée à la résidence … » : jeton collé sur la mauvaise ligne ; il a été effacé.
- Dépôt KPI refusé : la première erreur est affichée (colonne manquante, mois illisible, ligne en double). Corriger
  dans l'outil KPI, puis redéposer. Rien n'est enregistré tant qu'une erreur reste.
