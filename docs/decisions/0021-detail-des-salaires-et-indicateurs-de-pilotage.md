# 0021 - Détail des salaires et indicateurs de pilotage

Date : 27 novembre 2026
Statut : décidé par le porteur du projet (27 novembre 2026), phase test, données fictives. Complète la décision 0020.

## Contexte

Les totaux par établissement (décision 0020) ne suffisent pas pour analyser les salaires par poste, niveau et
ancienneté, contrôler la paie salarié par salarié, ni préparer un budget de masse salariale par poste. Le contrôle de
gestion a besoin d'indicateurs de productivité croisant la paie et la comptabilité (CA, EBITDA, valeur ajoutée par ETP).

## Décision

1. **Détail pseudonymisé par salarié.** Chaque DSN importée garde, en plus des totaux, une ligne par salarié :
   identifiant pseudonyme (empreinte SHA-256 tronquée du SIREN et du NIR, ou du matricule), libellé d'emploi, PCS,
   statut conventionnel, niveau (rubrique S21.G00.40.041), convention collective, cadre, contrat, sexe, âge en
   années, ancienneté en mois, présence, ETP, brut, heures, heures supplémentaires, primes, net. **Jamais de nom,
   prénom, NIR, matricule ni date de naissance** : la base refuse une ligne qui en contient. Le fichier DSN reste lu
   sur le poste et n'est jamais envoyé.
2. Il s'agit de données personnelles **pseudonymisées**, pas anonymes (un salarié seul sur son poste reste
   reconnaissable par son salaire). Accès réservé aux administrateurs, comme toute la paie. **Avant tout fichier
   réel : validation par la DSI, la DAF et le référent RGPD** (registre des traitements, information des salariés,
   durée de conservation).
3. **Référentiel des postes** : un libellé d'emploi de la paie est rattaché à un poste standard et à une famille
   (administrateurs, journalisé). Sans règle, le poste proposé est le libellé sans accents ni « H/F » et la famille
   est déduite de mots-clés.
4. **Nouvelles pages** (Social) : Rémunérations, Productivité, Contrôles de paie, Base budget ; Référentiel des
   postes dans Import et paramètres. Chaque valeur renvoie à son calcul.
5. **Règles** : salaire temps plein = somme des bruts ÷ somme des ETP des salariés présents tout le mois ; ratios
   de productivité = sommes de numérateurs ÷ sommes de dénominateurs sur les mois où les deux existent (invariant 4) ;
   coût employeur = brut × (1 + comptes 645 et 647 ÷ comptes 641) de la résidence et du mois.
6. **Base budget** : chiffres réels seulement (effectif et ETP de fin de période, salaire de base du mois, variables
   moyens, taux de charges réel). Les hypothèses restent dans le budget ou les missions (décision 0019).

## Conséquences

- Les DSN importées avant ce lot n'ont pas le détail : il faut les réimporter.
- Le SMIC est une table datée dans la page (`DSN_SMIC`) à tenir à jour ; les seuils des contrôles sont dans
  `DSN_SEUILS`.
- La rubrique de niveau (S21.G00.40.041) et les libellés d'emploi dépendent du paramétrage Silae : à vérifier sur un
  premier fichier réel.
