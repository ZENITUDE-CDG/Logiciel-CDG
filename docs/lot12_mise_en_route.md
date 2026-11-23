# Lot 12 - Mise en route (sans rien installer)

Tout se fait dans le navigateur. La clé publique Supabase est déjà dans `app/config.js`.

## 1. Supabase (projet de test)
1. **Authentication, Sign In / Providers** : désactiver « Allow new users to sign up » (inscriptions libres).
2. **Authentication, Users, Add user, Create new user** : `raphael.bracq@zenitude-groupe.com`, un mot de passe,
   cocher « Auto Confirm User ». Recommencer pour `benjamin.gagneur@zenitude-groupe.com`.
3. **SQL Editor, New query** : coller tout `scripts/installation_supabase.sql`, cliquer **Run**.
   Résultat attendu : « Success. No rows returned ». Le script remet la base de test à zéro : il peut être relancé.

## 2. Vérifier
- GitHub, onglet **Actions** : la ligne « Tests » doit avoir une coche verte (2 à 3 minutes après un dépôt).
- Site : `https://zenitude-cdg.github.io/Logiciel-CDG/connexion.html` (1 à 2 minutes après le dépôt).
- Démonstration : Raphael voit RES-901 et RES-902 et le menu Administration ; Benjamin ne voit que RES-901.
- Tableau de bord : depuis « Mon espace », lien « Tableau de bord » ; le nom affiché est celui de la personne
  connectée ; « Se déconnecter » ramène à l'écran de connexion.

## En cas de problème
- « Configuration incomplète » : la clé n'est pas dans `app/config.js`.
- « Adresse ou mot de passe incorrect » : vérifier le compte dans Authentication, Users.
- « Accès non attribué » : l'adresse n'est pas dans Administration, ou l'accès est désactivé.
- Croix rouge dans Actions : ouvrir la ligne, copier le message d'erreur et le transmettre.

Ne jamais modifier un fichier `.js` par double-clic sous Windows (il s'exécute au lieu de s'ouvrir) :
modifier sur GitHub avec le crayon, ou clic droit, Ouvrir avec, Bloc-notes.
