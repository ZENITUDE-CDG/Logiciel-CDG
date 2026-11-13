# 0002 - Calcul des ajustements dans la page, pendant la phase de test

Date : 13 novembre 2026

## Contexte

Le contrôle de gestion veut des tableaux de bord plus proches de la réalité économique : créer ou ajuster
des comptes comptables, créer des provisions (saisies, ou calculées à partir de comptes ou de données
externes, par exemple 5 % du CA ou 5 € par nuitée), choisir une période libre (réglette) sur plusieurs
exercices. Tous les tableaux de bord doivent tenir compte de ces ajustements.

Le site de la phase test est statique (GitHub Pages) : il n'y a pas de serveur. Jusqu'au lot 8, tous les
chiffres étaient précalculés par le moteur Python et la page ne faisait que les afficher
(CLAUDE.md : « Aucune formule officielle recopiée dans le navigateur »). Or un ajustement est créé par
l'utilisateur après la génération de la page, et une période libre ne peut pas être précalculée.

## Décision

Pour la phase de test uniquement, la page contient un petit calculateur (`interface/gabarit.html`,
section « Lot 9 ») qui recalcule le tableau EBITDA, les SIG et les KPI à partir de montants mensuels par
compte et par résidence fournis par le générateur (`calcul` dans les données de la page).

Garde-fous :

- Le moteur Python reste la référence officielle. Sans ajustement, la page doit donner exactement ses
  chiffres : `tests/test_site_ajustements.py` compare plus de 15 000 valeurs (EBITDA, SIG, KPI, tous
  périmètres et périodes) dans un navigateur.
- Aucun `eval`, aucune formule libre : une règle de provision est un objet structuré composé de termes
  (montant fixe, pourcentage de comptes, montant par donnée externe) ou d'une saisie mensuelle. Le texte
  saisi n'est jamais interprété (invariant 6).
- Une donnée externe absente rend l'ajustement « non calculable » et propage « non calculable » aux lignes
  et KPI concernés, jamais zéro (invariants 1 et 2). Un mois sans écriture pour une résidence n'est pas ajusté.
- Un compte simulé sans ligne dans un tableau est signalé « non classé » ; sans agrégat de base, il rend
  les KPI comptables non calculables (invariant 3, contrôle P1).
- Le pourcentage s'applique à la comptabilité réelle (hors ajustements) : pas de dépendance circulaire.
- Les montants d'ajustement sont arrondis au centime par résidence et par mois.
- Les publications figées (onglet Compte de résultat) ne sont pas modifiées par les ajustements (invariant 5).
- Le générateur refuse de produire la page si une rubrique sort de ce que la page sait rejouer
  (rubrique propre à un dossier, plage de comptes, exceptions, dates de fin).
- Les ajustements sont enregistrés dans le navigateur (export et import JSON). Données fictives uniquement
  (invariant 8) : ne pas y saisir de donnée réelle.

## Hors périmètre

- Pas de persistance partagée, pas de droits, pas de validation à deux personnes des ajustements.
- Ce calculateur ne vaut pas pour la production : le backend reprendra les mêmes règles et la même
  structure d'ajustement ; le calculateur de la page sera alors supprimé (point ouvert 12).

## Approbations

| Instance | Statut |
| --- | --- |
| Porteur du projet | Approuvé pour la phase de test (13 novembre 2026) |
| Contrôle de gestion | À tracer |
| DAF | À tracer |
| DSI | À tracer |
