# Lot 13 - Mise en route (sans rien installer)

Tout se fait dans le navigateur, dans cet ordre.

## 1. Supabase : base remise à zéro
**SQL Editor, New query** : coller tout `scripts/installation_supabase.sql`, cliquer **Run**.
Résultat attendu : « Success. No rows returned ». Le script remet la base de test à zéro (résidences,
groupes, parcs, ajustements) et recrée les huit résidences de démonstration. Les comptes de connexion
(Authentication, Users) ne sont pas touchés.

## 2. GitHub : clé secrète pour la publication
1. Supabase, **Project Settings, API Keys** : copier une clé secrète (`sb_secret_...`).
2. GitHub, dépôt, **Settings, Secrets and variables, Actions, New repository secret** :
   nom `SUPABASE_SECRET_KEY`, valeur = la clé copiée. Ne la coller nulle part ailleurs.

## 3. GitHub : fichiers du lot 13
Déposer les fichiers, puis créer à la main les deux fichiers dont le nom commence par un point
(le dépôt par glisser-déposer les ignore) : **Add file, Create new file**, nom
`.github/workflows/tests-et-publication.yml`, puis `.gitignore`, contenu copié depuis l'archive.

## 4. Vérifier
- Onglet **Actions** : « Tests et publication » doit montrer deux coches vertes (tests, puis publication).
  Pour republier à la main : « Tests et publication », **Run workflow**.
- Site : `https://zenitude-cdg.github.io/Logiciel-CDG/` (1 à 2 minutes après le dépôt).
- Raphael voit les huit résidences ; Benjamin ne voit que les trois résidences seniors (« Mon parc »).
- Ajustements : un ajustement créé par l'un apparaît chez l'autre (s'il a accès aux résidences) après
  rechargement de la page.

## En cas de problème
- « Données pas encore publiées » : la publication n'a pas tourné ou a échoué (onglet Actions).
- Croix rouge sur « publication » avec « SUPABASE_SECRET_KEY absent » : le secret n'est pas créé (étape 2).
- « aucune résidence de la base ne correspond » : l'installation SQL (étape 1) n'a pas été lancée.
- « Aucune résidence dans votre parc » : attribuer des résidences ou un groupe dans Administration.
