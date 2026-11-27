# 0022 - Analyse des écarts (lots 28 à 30)

Date : 27 novembre 2026
Statut : décidé par le porteur du projet (27 novembre 2026), phase test, données fictives.

## Contexte

Le contrôle de gestion veut une base commune pour comprendre les évolutions et les écarts d'une résidence ou d'un
groupe : évolution des coûts par nature, mais aussi effets volume et prix, fournisseurs, anomalies de saisie,
cohérence entre la comptabilité, les KPI et la paie, comparaison des résidences. Chaque écart doit pouvoir être
expliqué, commenté et suivi jusqu'à sa correction. Les trois lots ont été demandés en une seule livraison.

## Décision

1. **Nouvelle section « Analyse des écarts »**, juste après Tableaux de bord : Écarts à expliquer, Coûts par
   nature, Cascade de l'EBITDA, CA : volume et prix, Fournisseurs, Anomalies et cut-off, Cohérence compta et KPI,
   Cohérence compta et paie (administrateurs : données de paie), Comparaison des résidences, Seuils et références.
2. **Références de comparaison** : même période N-1, période précédente de même durée, moyenne des 12 mois précédents
   ramenée à la durée de la période (facteur appliqué et arrondi ligne de base par ligne de base, avant les totaux).
   Le budget viendra avec le module Budgets.
3. **Une absence n'est jamais zéro** : une résidence n'entre dans les écarts que si sa comptabilité couvre tous les
   mois de la période et de la référence (sinon elle est listée « hors des écarts » avec le motif). Dans un mois
   couvert, une ligne sans écriture vaut zéro. Une donnée d'exploitation manquante rend l'effet concerné non
   calculable. Ratios sur des sommes (invariant 4).
4. **Écarts repérés** (21 codes, règles dans `docs/analyse_ecarts.md`) : chaque écart au-delà des seuils (montant ET
   pourcentage) devient un constat avec une clé stable (code, résidence, objet, période, référence), un effet signé
   sur l'EBITDA (positif = favorable) et sa priorité (effet décroissant).
5. **Calcul** : référence Python `zenitude/analyse/ecarts.py` ; la page refait exactement le même calcul
   (`anCalculer`, comme la décision 0002) et ajoute la vue ajustée et la cohérence avec la paie. Les écarts ne sont
   jamais stockés : ils sont recalculés à chaque affichage à partir des chiffres publiés.
6. **Suivi** (migration 019, `ecarts_suivi`) : statut (à analyser, expliqué, à corriger, corrigé), commentaire et
   montant au moment du commentaire (un montant qui a changé depuis est signalé). Lecture : résidences du parc ;
   écriture : administrateur ou collaborateur sur son parc ; lecture seule : rien ; suppression : administrateur.
   Auteur, date et historique (`ecarts_journal`) posés par la base.
7. **Seuils** (`analyse_parametres`) : une seule ligne, modifiée par les administrateurs, contrôlée par la base.
   Par défaut : 10 % et 2 000 €, 2 écarts-types, 3 fois la médiane, 15 % de variation des ratios, 2 % de tolérance
   de rapprochement, 60 % pour une charge à étaler, 6 mois d'historique.
8. **Paquet d'écarts pour Claude** (lot 30) : CSV des écarts avec leurs commentaires, postes, cascade, volume et prix,
   fournisseurs, cohérence, comparaison ; LISEZ-MOI et MISSION ; référence PQ et empreinte SHA-256 dans le journal des
   paquets (niveau « ecarts »). Aucune écriture comptable ni donnée de paie dans ce paquet.

## Conséquences

- Les contrôles C02 à C05 du socle (lot 25) sont repris avec les mêmes règles (A6, A7, F4, F5) pour être suivis.
- Les anomalies (A1 à A4) et les rapprochements (R1) portent sur la comptabilité importée, même en vue ajustée.
- Le rapprochement du CA avec Mews (R1) suppose les données CA_MEWS_TOTAL, CA_MEWS_RESTO et CA_MEWS_PDJ importées.
- La cohérence avec la paie suit les droits de la paie (administrateurs) et n'est pas rejouée en Python.
- Limites : pas de comparaison au budget ; contrats fournisseurs (Zeendoc) non reliés ; ratios et seuils à recaler
  sur les données réelles ; découpage des lignes du CR de gestion à valider (point ouvert n° 10).
