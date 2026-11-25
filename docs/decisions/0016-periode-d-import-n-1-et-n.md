# 0016 - Lot 22 : période d'import = exercice N-1 complet + exercice N

Date : 25 novembre 2026
Statut : approuvé par le porteur du projet (25 novembre 2026).

## Contexte
Au lot 18b, la période d'import se choisissait mois par mois, sans aller au-delà du mois en cours. Le porteur du
projet veut au moins un exercice complet de comparaison, et reprendre les écritures passées d'avance.

## Décisions
1. **Règle unique**, sans choix de dates dans la page : exercice précédent complet (N-1) + exercice en cours (N),
   jusqu'à la fin de N. Calculée par le connecteur pour chaque dossier d'après ses exercices Pennylane réels
   (`periode_regle`) : exercices décalés et exercices courts respectés (jamais supposés janvier-décembre ni de douze
   mois). N = exercice qui contient la date du jour, sinon le plus récent commencé ; sans exercice précédent : N seul.
2. **Écritures anticipées** (datées après le jour de la synchronisation, dans N) : reprises dans les chiffres et
   comptées à part (`rapport["anticipees"]` : nombre de lignes et mois, sans montant), affichées dans la page.
3. Les mois enregistrés par le lot 18b (`parametres_import.mois_debut`, `mois_fin`) ne sont plus utilisés. Une
   demande portant explicitement des mois (appel direct de la fonction serveur) reste acceptée et prime sur la règle.
4. Lecture par modifications (lot 18d) conservée : la base est préparée avec la période déjà lue ; si la règle
   demande plus large (nouvel exercice ouvert), relecture complète automatique avec ce motif.
5. Phase test : la frise du site commence au premier mois du jeu de démonstration (octobre 2025) ; les lignes
   antérieures restent non reprises et comptées (affichées dans la page). Pour le dossier de test, N-1 commence
   exactement à cette date. Pour les résidences réelles (étape 2 de la décision 0013), la frise suivra le début de
   N-1 de chaque dossier.
6. Le dernier mois importé du site reste celui de la démonstration (`DERNIER_MOIS_IMPORTE`) : les écritures
   anticipées apparaissent dans les mois « projection » des tableaux, jusqu'au module Budgets.

## Pistes écartées
Historique de plusieurs exercices (soldes mensuels par compte pour N-2 et avant) : non retenu à ce stade ; à
reconsidérer si une comparaison sur plus d'un exercice devient nécessaire.
