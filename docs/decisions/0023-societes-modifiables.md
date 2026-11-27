# 0023 - Sociétés, noms et codes des autres outils, classements (lot 31)

Date : 27 novembre 2026
Statut : décidé par le porteur du projet (27 novembre 2026), phase test, données fictives.

## Contexte

La page « Résidence » affichait une fiche en lecture seule, tirée de la configuration publiée. Le contrôle de gestion
veut gérer les sociétés dans le logiciel (ajout, modification, archivage), retrouver une société sous tous les noms ou
codes qu'elle porte dans les autres outils (Pennylane « YTR », Mews « TRT »…) pour ne plus perdre d'information sur un
nom différent, créer ses propres classements de groupes, voir les exercices proches et les derniers ajustements.

## Décision

1. **« Résidence » devient « Société »** (menu, titres, ruban). Une société reste une ligne de `residences`, un
   dossier Pennylane. Les identifiants techniques (`residence`, `RES-…`) ne changent pas.
2. **Fiche modifiable** (migration 020) : nom d'usage, raison sociale, SIREN, activité, région, marque, date
   d'ouverture. Un champ vide garde la valeur de la configuration publiée ; une valeur identique à la configuration
   n'est pas recopiée. Activité et région modifiées recomposent aussitôt les périmètres par activité et par région.
3. **Droits** : création, archivage, dossier Pennylane et code Mews réservés aux administrateurs ; les autres champs
   et les noms et codes : administrateur ou collaborateur sur une société de son parc (comme le lot 12) ; lecture
   seule : rien. Contrôlé par la base (`trace_societe`, règles par ligne).
4. **Archivage** au lieu de la suppression : la société sort des listes de choix ; ses chiffres restent dans les
   totaux des groupes et son historique est conservé. Restauration possible.
5. **Noms et codes dans les autres outils** (`residence_identifiants`) : un libellé (outil) et un code. Un même code
   d'un même outil ne désigne qu'une société (sans tenir compte des majuscules). Ils servent à la recherche des
   sociétés et à reconnaître la société dans le modèle Excel des KPI.
6. **Classements** (`classements`) : créés par les administrateurs (RM, gamme, propriétaire…). Exclusif par défaut :
   une société dans un seul groupe du classement. Supprimer un classement garde ses groupes, sans classement.
   Activité et région restent des classements tirés des fiches. Les groupes de la configuration publiée ne se
   modifient pas dans la page.
7. **Groupes** : création, nom, classement, membres et suppression par les administrateurs. Un groupe présent dans le
   parc d'un utilisateur ne se supprime pas (le retirer d'abord dans Administration), pour qu'aucun accès ne
   disparaisse sans le voir.
8. **Exercices** : N-2 à N+2 toujours affichés (N = exercice en cours du ruban), avec la durée réelle ; une ligne
   indique un exercice pas encore ouvert dans Pennylane ou non importé ; les autres derrière « Voir plus ».
9. **Ajustements actifs** : les cinq dernières modifications (provisions, ajustements, lissages) avec date et auteur.
10. **Journal** `societes_journal`, écrit par la base : toute création, modification, archivage, suppression, avec
    l'auteur et les valeurs avant / après. Lisible selon le parc.

## Conséquences

- Migration 020 à appliquer dans Supabase ; sans elle, la page reste en lecture avec un bandeau.
- Une société créée dans la page n'a de chiffres qu'après la publication suivante, une fois son dossier Pennylane
  rattaché et calculé ; elle apparaît « En attente de données ».
- Démonstration locale : tout est gardé dans le navigateur (`zen-societes`).
