# 0017 - Retour au jeton Pennylane dans les secrets GitHub (retrait des jetons chiffrés du logiciel)

Date : 25 novembre 2026
Statut : décidé par le porteur du projet (25 novembre 2026). Remplace la partie « jetons Pennylane par dossier »
de la décision 0013 ; le dépôt du consolidé KPI et le reste de la décision 0013 ne changent pas.

## Contexte

Le lot 19 avait ajouté un mécanisme pour saisir les jetons Pennylane dans la page : clé RSA créée dans le
navigateur, jeton chiffré avant l'envoi, table `connexions_pennylane`, test des jetons par GitHub Actions. Lors de
la mise en service sur le dossier de test, ce mécanisme s'est révélé trop compliqué à mettre en route (droits de
la table, clé privée à copier, contrôle des droits du jeton refusant un jeton aux droits d'export). Le porteur
du projet préfère la méthode du lot 18, plus simple.

## Décision

1. Le jeton Pennylane en lecture seule est rangé dans les **secrets GitHub** du dépôt (`PENNYLANE_TOKEN_PILOTE`
   pour le dossier de test), comme au lot 18. Il n'est plus saisi dans le logiciel.
2. Sont retirés : le bloc « Connexions Pennylane » de la page Import comptable, la clé de chiffrement, le test
   des jetons, le secret `PENNYLANE_CLE_PRIVEE`, la dépendance `cryptography`, le module
   `zenitude/connecteurs/jetons.py`, les tables `connexions_pennylane` et `cle_jetons`, la colonne
   `synchronisations.type` (migration 014).
3. Conservés : la synchronisation lancée depuis la page (décision 0012), la règle N-1 + N (décision 0016), le
   consolidé KPI et le catalogue KPI.
4. Le logiciel ne vérifie plus lui-même que le jeton est en lecture seule : cette garantie repose sur la
   création du jeton dans Pennylane (profil « Lecture seule ») et sur le fait que le connecteur n'émet que des
   requêtes GET (testé : `tests/test_lot18_connecteur.py`).

## Conséquences

- Un jeton par dossier reste nécessaire pour le parc (pas d'espace cabinet). Avec cette méthode, chaque jeton est
  un secret GitHub à créer à la main, ce qui est faisable pour quelques résidences mais lourd pour une centaine ;
  à reconsidérer avant d'étendre au parc (étape 2 de la décision 0013, toujours à approuver).
- Aucun jeton, chiffré ou non, ne transite plus par le navigateur ni par la base.
