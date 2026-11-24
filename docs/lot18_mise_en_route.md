# Lot 18 - Mise en route (sans rien installer)

Tout se fait dans le navigateur, dans cet ordre. La base Supabase n'est PAS remise à zéro : les
ajustements et lissages déjà saisis sont conservés.

## 1. GitHub : fichiers du lot 18
Déposer les fichiers de l'archive, puis créer à la main les fichiers dont le nom commence par un point
(le dépôt par glisser-déposer les ignore) : **Add file, Create new file**, nom
`.github/workflows/synchro-pennylane-test.yml`, contenu copié depuis l'archive ; puis ouvrir
`.github/workflows/tests-et-publication.yml`, crayon (Edit), remplacer tout le contenu par celui de
l'archive, **Commit changes**.

Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes.

## 2. Supabase : ajouter la résidence de test
**SQL Editor, New query** : coller tout `scripts/lot18_residence_test.sql`, cliquer **Run**.
Résultat attendu : une ligne `RES-TEST | Dossier Pennylane de test | PENNY-TEST | true`.
Ne pas utiliser `installation_supabase.sql` (il remet la base à zéro).

## 3. GitHub : synchroniser
Onglet **Actions**, « Synchro Pennylane test », **Run workflow**, choisir le mode :
- `valides` : écritures validées seulement (par défaut) ;
- `tous` : écritures validées et brouillard.

Le journal de l'étape « Lire Pennylane, calculer et publier » affiche : statuts des écritures et nombre de
lignes, lignes reprises et écartées, comptes, comptes de tiers, groupes de lettrage, équilibre, comptes
classés provisoirement, puis « publié : ... RES-TEST ». Aucun montant.

Si un statut est signalé « inconnu, traité comme non validé », noter son nom : il faudra l'ajouter à la
liste des statuts validés ou brouillard du connecteur.

## 4. Vérifier sur le site
Se connecter en administrateur, choisir « Dossier Pennylane de test ». Le nombre de comptes doit
correspondre à « Test balance Pennylane » sur la même période et le même mode.

## En cas de problème
- « secret PENNYLANE_TOKEN_PILOTE absent » : le secret n'existe pas ou a un autre nom.
- « jeton refusé (401) » : jeton expiré ou supprimé dans Pennylane ; en créer un et le remplacer (Update).
- « dossier PENNY-TEST calculé mais absent de la base » : l'étape 2 n'a pas été faite.
- 0 ligne reprise en mode `valides` : regarder les statuts affichés ; relancer en mode `tous` pour comparer.
