# Lot 12 - Mise en route (sans rien installer)

Tout se fait dans le navigateur : Supabase, puis GitHub.

## 1. Supabase (projet de test)
1. **Authentication, Sign In / Providers** : désactiver « Allow new users to sign up » (inscriptions libres), enregistrer.
2. **Authentication, Users, Add user, Create new user** : `raphael.bracq@zenitude-groupe.com`, un mot de passe,
   cocher « Auto Confirm User ». Recommencer pour `benjamin.gagneur@zenitude-groupe.com`.
3. **SQL Editor, New query** : coller tout `scripts/installation_supabase.sql`, cliquer **Run**.
   Résultat attendu : « Success. No rows returned ». Le script remet la base de test à zéro : il peut être relancé.
4. **Project Settings, API Keys** : copier la clé **publishable** (ou « anon public »).
   Jamais la clé **secret** / « service_role ».

## 2. Avant le dépôt
Ouvrir `app/config.js` avec le Bloc-notes, remplacer `COLLER_ICI_LA_CLE_PUBLIQUE` par la clé copiée
(garder les guillemets), enregistrer.

## 3. GitHub
1. Dépôt, **Add file, Upload files** : faire glisser tout le contenu du dossier de mise à jour
   (dossiers et fichiers), puis **Commit changes** sur `main`.
2. Ouvrir `index.html`, crayon (modifier), chercher `<head>` (Ctrl+F) et ajouter juste en dessous :
   `<script src="app/garde.js"></script>` puis **Commit changes**.
3. Même opération dans `interface/gabarit.html` (sinon la ligne disparaît à la prochaine régénération du site).

## 4. Vérifier
- Onglet **Actions** : la ligne « Tests » doit avoir une coche verte (2 à 3 minutes).
- Site : `https://zenitude-cdg.github.io/Logiciel-CDG/connexion.html` (1 à 2 minutes après le dépôt).
- Démonstration : Raphael voit RES-901 et RES-902 et le menu Administration ; Benjamin ne voit que RES-901.

## En cas de problème
- « Configuration incomplète » : la clé n'est pas dans `app/config.js`.
- « Adresse ou mot de passe incorrect » : vérifier le compte dans Authentication, Users.
- « Accès non attribué » : l'adresse n'est pas dans Administration, ou l'accès est désactivé.
- Croix rouge dans Actions : ouvrir la ligne, copier le message d'erreur et le transmettre.
