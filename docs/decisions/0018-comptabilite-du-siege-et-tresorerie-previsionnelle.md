# 0018 - Comptabilité du siège (CA et FEES à refacturer) et trésorerie prévisionnelle

Date : 25 novembre 2026
Statut : décidé par le porteur du projet (25 novembre 2026), phase test, données fictives.

## Contexte

Les comptables reportent chaque mois à la main le CA de chaque résidence dans un fichier Excel à part, qui
calcule les FEES refacturés par le siège (droit de marque, management fees et leur répartition : compta,
communication, commercial, gérance, suivi d'exploitation). Les taux diffèrent selon les résidences et évoluent ;
une évolution ne doit pas réécrire l'historique. Côté trésorerie, le trésorier manque d'une vue simple des soldes,
des flux prévus et des virements de compte à compte à faire entre les comptes des résidences.

## Décision

1. **Section Comptabilité** du menu, juste avant Trésorerie : Chiffre d'affaires, Paramétrage des FEES, FEES à
   refacturer.
2. **CA** : somme en crédit − débit des comptes retenus, lue dans les écritures importées de Pennylane. Par défaut
   tous les comptes 7 ; règle du groupe modifiable, et règle propre possible par résidence (préfixes inclus et
   exclus). Mois sans écriture : non calculable, jamais zéro.
3. **Rubriques** : base CA (comptée dans le total refacturé) ou répartition d'une rubrique de base CA (un seul
   niveau ; détaille le total sans s'y ajouter). Code stable ; ajout, renommage, ordre, désactivation par un
   administrateur. Contrôle « répartition = 100 % » affiché.
4. **Règles datées** : chaque taux (%) ou montant brut mensuel (€) est une version avec un mois d'effet, pour le
   groupe ou une résidence ; « revenir à la règle du groupe » est aussi une version. La règle de la résidence
   l'emporte ; sans règle : « non paramétré », jamais zéro. Arrondi au centime, demi-centime loin de zéro ; une
   répartition porte sur le montant arrondi de sa rubrique.
5. **Clôture** d'un mois et d'une résidence : instantané figé (CA, règle de CA, règles et montants), que la base
   refuse de modifier. Rouvrir = supprimer l'instantané. Un CA modifié après clôture est signalé.
6. **Journal** (`compta_journal`) écrit par la base pour les rubriques, règles, règles de CA et clôtures.
7. **Droits** : paramétrage, clôtures, prévisions et virements réservés aux administrateurs ; les autres profils
   lisent la comptabilité de leur parc. La page Prévisions et virements est réservée aux administrateurs.
8. **Trésorerie, Prévisions et virements** : solde comptable de chaque compte à la date du jour ; flux prévus sur
   un horizon (7 à 90 jours) = pièces clients et fournisseurs ouvertes à leur échéance (compte principal ; pièces
   échues ignorées sauf choix contraire) + prévisions saisies (ponctuelles ou mensuelles) + virements marqués
   faits pas encore comptabilisés ; solde projeté et point bas. Virements proposés **dans une même résidence
   seulement** (jamais entre résidences, qui sont des sociétés distinctes) : combler les comptes dont le point bas
   passe sous le minimum, puis remonter vers le principal l'excédent au-dessus du plafond (nouveau `solde_max`).
9. **Calcul dans la page** (comme la décision 0002) : la référence est `zenitude/comptabilite/fees.py` ; un test
   compare la page et Python sur toutes les résidences et tous les mois de la démonstration.

## Conséquences

- Migration 015 (`fees_rubriques`, `fees_regles`, `ca_regles`, `fees_clotures`, `compta_journal`,
  `tresorerie_previsions`, `virements_suivis`, `comptes_bancaires.solde_max`), sans remise à zéro.
- Rubriques et règles de départ = tableau du siège (management fees 8 %, répartition 40 / 20 / 20 / 15 / 5 %,
  droit de marque non paramétré), effet janvier 2025, à ajuster dans la page.
- Limites : le solde « actuel » est le solde comptable (écritures importées), pas le solde bancaire Pennylane
  en temps réel ; les FEES ne sont pas encore reportés en décaissements prévus des résidences ; pas d'export
  vers Pennylane des écritures de refacturation ; un virement marqué fait est supposé comptabilisé dès qu'une
  écriture du compte débité est datée du même jour ou après.
