# 0006 - Exécution du lot 12 : site GitHub Pages et base de test Supabase

Date : 23 novembre 2026
Statut : approuvé par le porteur du projet (23 novembre 2026) ; à faire approuver comme la décision 0004

## Contexte
La décision 0004 prévoyait l'exécution sur poste de travail (point 7). Le porteur du projet
préfère ne rien installer en local pendant la phase test : GitHub, Supabase et le logiciel seulement.

## Décisions
1. **Remplace le point 7 de la décision 0004.** Le logiciel tourne sur le site GitHub Pages du dépôt.
   La base est le projet Supabase de test. Rien n'est exécuté sur un poste de travail.
2. **Clé publique visible.** Sans serveur, la page doit contenir l'adresse du projet Supabase et sa clé
   publique (« publishable » / « anon »), dans `app/config.js`. Cette clé est faite pour être visible :
   elle ne donne que ce que les règles de la base autorisent (`migrations/003_droits.sql`), prouvé par
   les tests. La clé secrète (« secret » / « service_role ») et le mot de passe de la base ne sont
   jamais dans le dépôt. Écart accepté à la consigne « aucune clé dans un fichier versionné ».
3. **Identité = adresse e-mail du jeton de connexion**, lue par la base avec le réglage standard
   `request.jwt.claims`. Avec Microsoft 365, le jeton contiendra la même adresse : seules les
   pages de connexion changeront.
4. **Comptes de connexion créés par un administrateur dans Supabase** (Authentication, Users, Add user),
   inscriptions libres désactivées. Le logiciel (page Administration) gère le rôle, l'état actif et
   le parc. Un compte de connexion sans accès actif dans le logiciel ne voit rien.
5. **Droits vérifiés dans la base** pour toutes les lectures et écritures (décision 0004, point 3).
   Les pages n'ajoutent que du confort (masquer un lien, empêcher un administrateur de se retirer
   son propre rôle). La garde du tableau de bord (`app/garde.js`) est un confort d'affichage :
   le tableau de bord actuel (`index.html`) contient des données fictives intégrées à la page, il
   n'est pas filtré par parc.
6. **Démonstration** : Raphael Bracq administrateur (voit tout), Benjamin Gagneur collaborateur avec le
   groupe pilote pour parc (ne voit que la résidence pilote). `scripts/donnees_test.sql`.
7. **Tests automatiques sur GitHub Actions** (`.github/workflows/tests.yml`), à chaque dépôt, sur une
   base PostgreSQL temporaire construite à partir de `migrations/`. Ils ne touchent jamais Supabase
   et n'utilisent aucun secret.

## Limites connues
- L'écran de connexion factice du lot 8 reste dans `index.html` tant que `interface/gabarit.html`
  n'est pas repris (prochain lot) : après la vraie connexion, il suffit de le passer.
- Les tests de page des lots 9 et 11 ouvrent la page en local (`file://`) : la garde ne s'y applique pas.
- Pas de mot de passe oublié (envoi de mail hors périmètre) : un administrateur réinitialise le mot de
  passe dans Supabase.
- Dépôt public : décision DSI toujours attendue (décision 0004).

## Approbations
| Instance | Statut |
| --- | --- |
| Porteur du projet | Approuvé le 23/11/2026 |
| Benjamin Gagneur | À tracer |
| Contrôle de gestion | À tracer |
| DAF | À tracer |
| DSI | À tracer (clé publique dans la page, site public) |
