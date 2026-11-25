# Lot 23 - Retour au jeton dans les secrets GitHub (décision 0017)

Retire les jetons Pennylane chiffrés du logiciel. La base n'est PAS remise à zéro ; aucune donnée comptable ni KPI
n'est touchée.

## 1. GitHub : déposer les fichiers de l'archive
Glisser-déposer les fichiers de l'archive dans le dépôt (garder les dossiers), puis supprimer les fichiers retirés :
- `zenitude/connecteurs/jetons.py`
- `tests/test_lot19_jetons.py`
- `tests/test_lot19_page.py`

Les fichiers dont le nom commence par un point ne passent pas par le glisser-déposer : ouvrir chacun dans GitHub
(crayon, Edit), remplacer tout le contenu par celui de l'archive, **Commit changes** :
- `.github/workflows/synchro-pennylane-test.yml`
- `.github/workflows/tests-et-publication.yml`

Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes.

## 2. Supabase : migration 014
**SQL Editor, New query** : coller tout `migrations/014_retrait_jetons_chiffres.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». Elle supprime les tables `connexions_pennylane` et `cle_jetons`
et la colonne `synchronisations.type`. Elle peut être relancée sans effet.
(Ne pas utiliser `installation_supabase.sql`, qui remet tout à zéro.)

## 3. Supabase : mettre à jour la fonction serveur
**Edge Functions**, `lancer-synchro`, **Code** : remplacer tout le code par le contenu de
`supabase/functions/lancer-synchro/index.ts`, **Deploy**. Les secrets et le réglage JWT ne changent pas.

## 4. GitHub : le jeton Pennylane
Dans Pennylane, dossier de test : **Paramètres**, **Connectivité**, **Développeurs**, **Générer un jeton API**,
profil **Lecture seule**. Dans GitHub : **Settings**, **Secrets and variables**, **Actions**, secret
`PENNYLANE_TOKEN_PILOTE` (**Update** s'il existe déjà), coller le jeton.
Le secret `PENNYLANE_CLE_PRIVEE` n'est plus utilisé : le supprimer.

## 5. Vérifier
Site, **Import comptable**, **Synchroniser**. L'historique doit passer à « terminée » et le bandeau afficher
« Connexion Pennylane active (lecture seule) » avec la date de synchronisation.

## En cas de problème
- « secret PENNYLANE_TOKEN_PILOTE absent » : le secret n'existe pas ou a un autre nom.
- « jeton refusé (401) » : jeton expiré ou supprimé dans Pennylane ; en créer un et mettre à jour le secret.
- « accès interdit (403) » : le jeton n'a pas les droits de lecture nécessaires ; le recréer en **Lecture seule**.
