# 0012 - Lot 18b : synchronisation Pennylane lancée depuis la page

Date : 24 novembre 2026
Statut : approuvé par le porteur du projet (24 novembre 2026), option « lancement immédiat ».

## Contexte
Au lot 18, la synchronisation du dossier Pennylane de test se lançait depuis l'onglet Actions de GitHub.
Le porteur du projet veut la piloter depuis la page Import comptable : période d'import, masquage des
écritures en brouillard, bouton Synchroniser pour une résidence ou pour toutes les résidences d'un groupe.
La page est un site statique public : elle ne peut détenir aucune clé capable de lancer GitHub.

Deux options ont été présentées : une file d'attente relevée par un workflow planifié (délai de quelques
minutes, rien de nouveau à installer) ou un lancement immédiat par une fonction serveur Supabase (une clé
GitHub de plus à gérer). Le porteur du projet a choisi le lancement immédiat.

## Décisions
1. **Fonction serveur Supabase `lancer-synchro`** (`supabase/functions/lancer-synchro/index.ts`) : vérifie la
   session et le rôle administrateur actif, contrôle la demande (dossiers connus, mois AAAA-MM, début <= fin),
   refuse une deuxième synchronisation tant qu'une autre est en attente ou en cours (30 minutes), enregistre
   les paramètres et la demande, puis lance le workflow « Synchro Pennylane » avec le numéro de la demande.
2. **Secrets de la fonction, dans Supabase uniquement** : `CLE_SECRETE_SUPABASE` (clé secrète du projet) et
   `GITHUB_JETON_SYNCHRO`, jeton GitHub à granularité fine limité au dépôt Logiciel-CDG et au seul droit
   « Actions : lecture et écriture », avec une date d'expiration. Origines autorisées : le site GitHub Pages.
3. **Migration 007** : `parametres_import` (période et brouillard par résidence ; lecture selon le parc,
   écriture administrateur) et `synchronisations` (journal des demandes ; lecture administrateur ; aucune
   écriture depuis la page : seules la fonction et GitHub Actions écrivent, avec la clé secrète).
4. **Workflow « Synchro Pennylane »** (`synchro-pennylane-test.yml`, nom de fichier conservé) : reçoit le numéro
   de la demande, la passe à « en cours », lit Pennylane avec la période et le mode demandés, recalcule,
   publie, puis la passe à « terminée » ou « échec » avec un résultat par résidence sans montant (sauf les
   sommes du brouillard, affichées dans la page). Une demande ne reste jamais « en cours » après une erreur.
5. **Publication automatique** : relit la période et le brouillard de `parametres_import` ; même file que la
   synchronisation (une seule écriture à la fois dans la base).
6. **Groupes** : la demande porte sur toutes les résidences du périmètre choisi ; seules les résidences
   connectées (aujourd'hui, le dossier de test) sont lues, les autres sont signalées « non connectée ».
   Garde-fous inchangés : liste blanche du connecteur, résidence réelle refusée par la publication.

## Conséquences
- La page fonctionne avant l'application de la migration 007 (historique vide) et sans la fonction (message
  d'erreur clair au clic).
- Le jeton GitHub expire : le renouveler et mettre à jour le secret de la fonction.
- Les tests de la fonction (`controler_test.ts`) se lancent avec Deno, hors GitHub Actions ; le reste du lot
  est couvert par pytest (connecteur, publication, droits, page).
