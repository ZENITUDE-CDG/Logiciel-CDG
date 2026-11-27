# 0020 - DSN et indicateurs sociaux

Date : 27 novembre 2026
Statut : décidé par le porteur du projet (27 novembre 2026), phase test, données fictives.

## Contexte

La paie est produite dans Silae. Chaque mois, la DSN (déclaration sociale nominative) décrit, pour chaque
établissement, les salariés, leurs contrats, leurs rémunérations, leurs arrêts de travail et leurs fins de contrat.
C'est la source la plus fiable pour les effectifs, les mouvements et l'absentéisme, et un point de contrôle de la
paie comptabilisée dans Pennylane. Aucun fichier réel n'était disponible pour le développement : la lecture suit la
norme NEODeS et sera ajustée sur le premier fichier Silae.

## Décision

1. **Le fichier ne quitte pas le poste.** La DSN est nominative (noms, NIR, salaires individuels). Elle est lue
   dans le navigateur de la personne qui l'importe ; seuls des **totaux par établissement (SIRET) et par mois** sont
   enregistrés. Pour suivre un arrêt de travail d'une DSN à l'autre, une **clé anonyme** (empreinte tronquée,
   sans nom ni NIR) et ses dates sont gardées. La base refuse un contenu portant un nom, un NIR ou un matricule.
2. **Réservé aux administrateurs** : import, consultation et journal (données de paie). La section Social et la
   page Import DSN sont masquées pour les autres profils ; la base filtre de son côté.
3. **Rattachement** : chaque SIRET est rattaché une fois à une résidence (dossier Pennylane) ; le changer déplace tous
   ses mois. Une résidence peut avoir plusieurs SIRET (sommés).
4. **Remplacement** : un nouvel import du même SIRET et du même mois remplace le précédent (DSN « annule et
   remplace » ou correction). Le journal garde chaque import, remplacement, suppression et rattachement.
5. **Refus** : un fichier illisible est refusé en entier ; une déclaration non mensuelle, d'annulation (type 04) ou
   fractionnée est refusée seule, avec son motif.
6. **Indicateurs** : effectif et ETP fin de mois, entrées et sorties par motif, turnover, structure (contrats, âges,
   ancienneté, femmes, cadres), masse salariale brute, net versé, heures rémunérées et supplémentaires, jours
   d'arrêt par motif et taux d'absentéisme. Croisés avec Pennylane et l'exploitation : charges de personnel / CA,
   coût mensuel par ETP, charges par nuitée vendue, rapprochement brut DSN ↔ comptes 641 (tolérance 1 %, 1 €
   minimum). Ratios calculés sur des sommes, sur les seuls mois où les deux termes existent (invariant 4) ; une
   donnée absente est « non calculable », jamais zéro (invariant 1).
7. **Calcul** : référence Python `zenitude/social/dsn.py` ; la page refait la même lecture (même résultat à l'octet
   près, vérifié par `tests/test_lot26_page.py`). Montants en centimes, heures en centièmes, ETP en millièmes.

## Conséquences

- Les codes de la norme utilisés (motifs d'arrêt et de fin de contrat, types de rémunération, natures de contrat)
  sont à confirmer sur un premier fichier Silae ; ils sont regroupés dans `docs/dsn.md` et au début des deux
  implémentations.
- Les comptes de comparaison (641 pour le brut, 64 pour les charges de personnel) sont à valider par le contrôle
  de gestion, notamment le traitement des provisions de congés payés.
- L'import de DSN réelles, même agrégées, n'aura lieu qu'avec l'accord de la DSI et de la DAF (invariant 8).
