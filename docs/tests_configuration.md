# Cas de test du chargeur de configuration

Version 0.1 - 13 novembre 2026. Accompagne `configuration.md` (contrôles B1 à B31, W1 à W5) et `Zenitude_Configuration_modele.xlsx`.
Toutes les données sont fictives. Les résultats attendus sont définis par le contrôle de gestion, indépendamment du code.

## Conventions

- **Base de départ** : le classeur modèle, copié, sans modification, avec deux lignes d'exemple par onglet. Il est valide. Chaque cas de test part de cette base et n'applique qu'une modification.
- **Dossiers Pennylane connus** pour les tests : `PENNY-1001`, `PENNY-1002`, `PENNY-1003`.
- **Résidences connues** : `RES-001` (Hôtellerie), `RES-002` (Seniors), `RES-003` (Mixte).
- **Colonne « Dossier à créer »** : `non` par défaut dans le modèle, `oui` seulement pour les cas qui le demandent.
- **Résultat attendu** : `REFUS` (chargement refusé, motif cité) ou `ACCEPTE` (version créée), avec avertissement éventuel.
- Chaque cas est identifié `T-<contrôle>-<a|b>` : `a` doit échouer, `b` doit réussir (cas limite proche).

## 1. Structure (B1 à B4)

| Cas | Modification de la base | Attendu |
| --- | --- | --- |
| T-B1-a | Onglet `Rubriques` renommé `Rubrique` | REFUS, onglet attendu absent |
| T-B1-b | Onglet supplémentaire `Notes` ajouté | ACCEPTE, `Notes` ignoré |
| T-B2-a | En-tête « Date d'effet » renommé « Date effet » | REFUS, en-tête inattendu, ligne 4 |
| T-B2-b | Colonnes réordonnées (même en-têtes) | ACCEPTE, lecture par en-tête |
| T-B3-a | Texte « 2026-01 » dans une date d'effet | REFUS, type incorrect, onglet et ligne |
| T-B3-b | Date saisie au format `13/11/2026` (texte reconnu) | ACCEPTE |
| T-B4-a | Ligne Rubriques avec code mais sans libellé | REFUS |
| T-B4-b | Ligne entièrement vide au milieu des données | ACCEPTE, ligne ignorée |

## 2. Référentiels et codes (B5 à B9)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B5-a | Deux lignes `RES-001` avec la même date d'effet | REFUS |
| T-B5-b | Deux lignes `RES-001` avec dates d'effet différentes (changement d'activité) | ACCEPTE |
| T-B6-a | Résidence avec dossier `PENNY-9999` (inconnu), « Dossier à créer » = non | REFUS |
| T-B6-b | Résidence `PENNY-1004` avec « Dossier à créer » = oui | ACCEPTE avec avertissement W6 |
| T-B7-a | Activité « Résidence service » absente de Listes | REFUS |
| T-B7-b | Même activité ajoutée à Listes, puis utilisée | ACCEPTE |
| T-B8-a | Deux rubriques `ASSUR` à la même date d'effet, même dossier | REFUS |
| T-B8-b | Deux rubriques `ASSUR` à des dates d'effet différentes | ACCEPTE |
| T-B9-a | Scénario `Scenarios` référence la rubrique `CA-INCONNU` | REFUS |
| T-B9-b | Seuil référence le KPI `OCC-HOT` existant | ACCEPTE |

## 3. Dates et chevauchements (B10 à B12)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B10-a | Rubrique `CA-SERV` avec fin = 2025-12-31, effet = 2026-01-01 | REFUS |
| T-B10-b | Même rubrique avec fin = 2026-01-01 = effet (jour unique) | ACCEPTE |
| T-B11-a | Deux règles `CA-HEB` actives sur `PENNY-1001` du 01/01/2026 au 31/12/2026, et une seconde du 01/06/2026 | REFUS |
| T-B11-b | Première règle finit le 31/05/2026, seconde commence le 01/06/2026 | ACCEPTE |
| T-B12-a | KPI actif sans date d'effet | REFUS |
| T-B12-b | KPI au statut « brouillon » sans date d'effet | ACCEPTE avec avertissement |

## 4. Rubriques (B13 à B15)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B13-a | Compte `6161` classé dans `ASSUR` (616) et dans `AUTRE-616` (616), même dossier, même agrégat `PL_CHARGES`, même priorité | REFUS, deux rubriques de base |
| T-B13-b | Même cas avec priorités 1 et 2 distinctes | ACCEPTE, la priorité la plus précise tranche |
| T-B13-c | Même cas avec deux agrégats de base différents (`PL_CHARGES` et `EBITDA_AJUSTE`) | ACCEPTE, un compte par agrégat |
| T-B14-a | Préfixe `616*` | REFUS, forme interdite |
| T-B14-b | Plage `616-618` | ACCEPTE |
| T-B15-a | Exception `7063` sur une ligne de préfixe `616` | REFUS, exception hors du préfixe |
| T-B15-b | Exception `6161` sur une ligne de préfixe `616` | ACCEPTE |

## 5. KPI (B16 à B19)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B16-a | Formule `RATIO([LN_VENDUES];[LN_DISPONIBLES]` (parenthèse manquante) | REFUS |
| T-B16-b | Formule `RATIO([LN_VENDUES];[LN_DISPONIBLES])` | ACCEPTE |
| T-B16-c | Fonction `MOYENNE([A])` (non autorisée) | REFUS |
| T-B16-d | Mesure `[P&L_CHARGES]` (caractère interdit) | REFUS |
| T-B17-a | `KPI-A = {KPI-B}+1` et `KPI-B = {KPI-A}*2` | REFUS, référence circulaire |
| T-B17-b | `KPI-A = {KPI-B}+1` sans retour | ACCEPTE |
| T-B18-a | `SOMME([CA_HEBERGEMENT])+{OCC-HOT}` (€ + %) | REFUS, unités incompatibles |
| T-B18-b | `RATIO([CA_HEBERGEMENT];[LN_VENDUES])` avec unité déclarée € | ACCEPTE |
| T-B19-a | KPI actif sans approbateur | REFUS |
| T-B19-b | KPI brouillon sans approbateur | ACCEPTE |

## 6. Groupes (B20 à B23)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B20-a | Groupe dynamique sans critère | REFUS |
| T-B20-b | Groupe dynamique avec un critère | ACCEPTE |
| T-B21-a | Critère `Marque = Marque Z` alors que la colonne Marque est vide | REFUS, attribut absent |
| T-B21-b | Critère `Marque = Marque B` avec colonne renseignée | ACCEPTE |
| T-B22-a | `GRP-A` composé de `GRP-B`, et `GRP-B` composé de `GRP-A` | REFUS, cycle |
| T-B22-b | `GRP-C` composé de `GRP-A` et `GRP-B` sans cycle | ACCEPTE |
| T-B23-a | Groupe manuel sans inclusion | REFUS |
| T-B23-b | Groupe manuel avec `RES-001` | ACCEPTE |

## 7. Scénarios et seuils (B24 à B27)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B24-a | Scénario `Pessimiste` non listé | REFUS |
| T-B24-b | `Pessimiste` ajouté à Listes puis utilisé | ACCEPTE |
| T-B25-a | Hypothèse sans justification | REFUS |
| T-B25-b | Hypothèse avec justification et auteur | ACCEPTE |
| T-B26-a | Valeur `dix` (texte) | REFUS |
| T-B26-b | Valeur `-0,05` | ACCEPTE |
| T-B27-a | Seuil sans indicateur | REFUS |
| T-B27-b | Seuil sur `OCC-HOT` (%) avec sens et valeur | ACCEPTE |
| T-B27-c | Seuil de fraîcheur sans fréquence de source | REFUS |

## 8. Rapports et envois (B28 à B31)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-B28-a | Section « Prévisions détaillées » non disponible dans les gabarits | REFUS |
| T-B28-b | Sections du modèle | ACCEPTE |
| T-B29-a | Format « Word » pour un gabarit PDF/PPTX/Excel | REFUS |
| T-B29-b | Format « PDF » | ACCEPTE |
| T-B30-a | Adresse `direction@@exemple` | REFUS |
| T-B30-b | Adresse externe sans périmètre de diffusion déclaré | REFUS |
| T-B30-c | Adresse valide `direction@exemple.invalid` | ACCEPTE |
| T-B31-a | Envoi automatique `oui` sans approbation | ACCEPTE, rapport chargé **inactif** |
| T-B31-b | Même rapport après approbation enregistrée | ACCEPTE, actif |

## 9. Avertissements (W1 à W5)

| Cas | Modification | Attendu |
| --- | --- | --- |
| T-W1 | KPI jamais utilisé | ACCEPTE avec avertissement W1 |
| T-W2 | Groupe dont un membre n'a pas de données sur cinq périodes | ACCEPTE avec W2 (vérifié sur données de test) |
| T-W3 | Seuil de 90 jours sur une source hebdomadaire (plus de 3 fois la période de 7 jours) | ACCEPTE avec W3 |
| T-W3-b | Seuil de 14 jours sur une source hebdomadaire | ACCEPTE |
| T-W4 | Règle dont la fin est dans 20 jours | ACCEPTE avec W4 |
| T-W5 | Scénario Optimiste identique à la Référence | ACCEPTE avec W5 |
| T-W6 | Dossier déclaré « à créer » (même cas que T-B6-b) | ACCEPTE avec W6 |

## 10. Contrôles de publication (P1 à P5)

Ces cas ne testent pas le chargement mais la publication. Ils utilisent un jeu de données fictif.

| Cas | Situation | Attendu |
| --- | --- | --- |
| T-P1-a | Compte `6251` mouvementé, aucune rubrique | Publication bloquée, compte listé comme non classé |
| T-P1-b | Même compte classé ou exclu explicitement | Publication possible |
| T-P2-a | Mesure `CA_SERVICES` absente pour mars 2026 | KPI « non calculable », motif, pas de zéro |
| T-P3-a | Mois en cours affiché comme « clôturé » | Refusé ; statut « provisoire » attendu |
| T-P4-a | Écriture définitive arrivée sur une FNP estimée, sans rapprochement | Anomalie signalée, montant non doublé |
| T-P5-a | Rapport avec blocage « oui » et période non validée | Envoi suspendu, aucun envoi silencieux |

## 11. Tests de retour arrière et d'immuabilité

- **T-V-1** : charger la version 1, puis la version 2 ; revenir à la version 1 ; les publications créées sous la version 2 conservent la version 2.
- **T-V-2** : un retour arrière ne modifie aucune ligne de données importées (comparaison par empreinte).
- **T-V-3** : le même fichier chargé deux fois produit un rapport identique et ne crée pas de doublon de version.
- **T-V-4** : le déposant tente d'approuver sa propre configuration → refusé.

## 12. Critères de réussite

- 100 % des cas `a` sont refusés avec le motif attendu (code du contrôle et ligne).
- 100 % des cas `b` sont acceptés sans erreur.
- Aucun cas ne produit de version partiellement appliquée.
- Les tests passent sans service d'IA et sans connexion à Pennylane (données de test uniquement).

## 13. Mise en œuvre

Le dossier `tests/fixtures/configuration/` contient le modèle copié ainsi que, pour chaque cas, le classeur modifié (`T-B13-a.xlsx`, etc.). Un fichier `tests/attendus.csv` liste pour chaque cas : identifiant, résultat attendu, code de contrôle, ligne. Les fixtures sont générées par un script à partir de la base, pour ne pas les maintenir à la main.

Les cas ci-dessus sont des spécifications. Les fichiers de fixtures ne sont pas encore générés : cette étape viendra avec le développement du chargeur.
