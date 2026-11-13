# CLAUDE.md - Pilotage Zenitude

## Statut du projet
- Cadrage : `ZENITUDE_Cadrage_Claude_Code.md` v0.8. **Ne développe pas tant que le cadrage n'est pas approuvé** par le contrôle de gestion, la DAF et la DSI. Si l'approbation n'est pas tracée dans `docs/decisions/`, demande-la avant tout code applicatif.
- Configuration : `docs/configuration.md` (format du classeur, grammaire des formules, contrôles B1 à B31).
- Tests : `tests/attendus.csv` et `tests/fixtures/`, générés par `tests/generer_fixtures.py`.
- Équipe : deux personnes (porteur du projet et Benjamin), sans développeur dédié. Code simple, documenté, testé.

## Décisions prises (13 novembre 2026)
- Pas de studio sans code : la configuration métier est un classeur Excel (`Zenitude_Configuration_modele.xlsx`).
- Dossier Pennylane inconnu : refusé (B6), sauf déclaré « à créer » (colonne Referentiel), accepté avec avertissement W6.
- Seuils de fraîcheur : 45 jours pour la comptabilité, 2 jours pour l'exploitation. Fréquence de la source obligatoire avec le seuil (B27) ; seuil supérieur à 3 fois la période de la fréquence = avertissement W3.
- Colonnes différées : destinataire externe, périmètre de diffusion et approbation des envois. B30 (partie externe) et B31 ne sont pas implémentés pour l'instant.
- Cas non tranchés (ne pas implémenter) : T-B30-b, T-B31-a, T-B31-b, T-W2 (marqués A_DEFINIR dans `attendus.csv`).

## Périmètre
- Hôtellerie, seniors, étudiants, résidences mixtes. Un dossier comptable Pennylane par résidence.
- Pennylane est la seule source externe obligatoire. Les autres sources sont différées : ne pas les implémenter.
- Exercices réels Pennylane, dont un exercice de neuf mois et des exercices décalés. Ne jamais supposer janvier-décembre, ni douze mois par exercice, ni proratiser un exercice court.
- CA distingué par comptes. Charges non ventilées par analytique. Aucune marge par activité sans coûts attribuables.
- Prévisions de ventes produites par le revenue management : consommées, jamais recalculées ici. Les simulations du contrôle de gestion sont étiquetées et séparées.
- Trois scénarios initiaux : Référence, Optimiste, Défavorable. Scénario, version et budget approuvé sont trois objets distincts.

## Invariants (ne jamais enfreindre)
1. Une absence de donnée n'est jamais zéro. Elle produit « non calculable » avec un motif.
2. Une division par zéro produit « non calculable ».
3. Un compte appartient à une seule rubrique de base pour un agrégat donné. Un conflit bloque le chargement ; ne jamais trancher par ordre de ligne.
4. Une moyenne de ratios n'est jamais un ratio groupe. Les ratios se calculent sur sommes de numérateurs et dénominateurs compatibles.
5. Une publication conserve sa version de configuration, ses données et ses formules. Une modification crée une révision, jamais une réécriture.
6. Aucune formule Excel, macro ni `eval`/`exec` sur du texte fourni par un utilisateur. La configuration est lue comme des données.
7. Une configuration partiellement valide n'est jamais appliquée.
8. Aucune donnée réelle, aucun secret, aucun export financier réel dans le dépôt, les fixtures, les logs ou tout service d'IA. Données synthétiques uniquement, marquées « fictif ».
9. Les droits sont vérifiés côté serveur : recherches, agrégats, exports, favoris, tâches automatiques.
10. Le produit fonctionne sans IA. Aucune dépendance à un service d'IA dans les parcours livrés.
11. Les identifiants sont en `[A-Z0-9_-]`. Le caractère `&` est interdit (utiliser `PL_`).

## Architecture (proposition à valider avec la DSI)
- Backend Python / Django, PostgreSQL, traitements d'import et de calcul en arrière-plan.
- Frontend React / TypeScript. Metabase possible pour les tableaux de bord (à décider).
- Modules : données certifiées, connecteur Pennylane, configuration, moteur de KPI, clôture, budgets, rapports, administration.
- Le moteur de KPI est appelé par tous les écrans et exports. Aucune formule officielle recopiée dans le navigateur.
- Connecteurs séparés du modèle métier : changer de source ne réécrit pas le P&L.
- Cache et précalculs : clés incluant scénario, version et périmètre de droits.

## Commandes
- Installation : `pip install -r requirements.txt`.
- Tests : `python -m pytest` (106 tests : 70 cas de configuration, 9 du lot 2, 9 du lot 3, 11 du lot 4, 7 du lot 5).
- Versions : `python -m zenitude.config versions <dossier> deposer|approuver|appliquer|revenir|publier|statut ...`.
- Configuration de test complète : `python tests/generer_config_complete.py config_modele/Zenitude_Configuration_modele.xlsx tests/fixtures tests/fixtures/ecritures_synthetiques.csv`.
- Écritures synthétiques : `python tests/generer_ecritures.py tests/fixtures`.
- Validation d'un classeur : `python -m zenitude.config check <fichier.xlsx> [--md|--json]`.
- Aperçu des impacts entre deux versions : `python -m zenitude.config impact <ancien.xlsx> <nouveau.xlsx> [--json]`.
- Génération des fixtures : `python tests/generer_fixtures.py config_modele/Zenitude_Configuration_modele.xlsx tests_out`.

## Règles de modification
- Un changement de format de classeur est un changement de contrat : mettre à jour `docs/configuration.md`, les fixtures et `attendus.csv` dans le même commit.
- Ajouter un contrôle = ajouter son cas `a` et son cas `b` dans `attendus.csv`.
- Une formule KPI ne s'ajoute pas hors de la grammaire documentée sans révision de `docs/configuration.md`.
- Ne jamais modifier une fixture pour faire passer un test. Si un résultat attendu semble faux, le signaler au contrôle de gestion.
- Un message d'erreur de chargement cite toujours l'onglet, la ligne, le code du contrôle et le motif.

## Premier lot (lecture et validation, sans Pennylane) - STATUT : réalisé
Prérequis : cadrage approuvé pour la phase test, tracé dans `docs/decisions/0001-approbation-cadrage-test.md`.
État : chargeur, contrôles B1 à B31 (sauf B30 partie externe et B31), W1 à W7, CLI et suite de 70 cas au vert.
1. Créer le squelette du dépôt : `docs/`, `tests/fixtures/`, `zenitude/config/`, et un environnement Python avec `openpyxl` et `pytest`.
2. Lire le classeur (neuf onglets, en-têtes par nom) et produire une structure de données typée par onglet. Refuser un onglet ou un en-tête inattendu (B1, B2) avant toute autre validation.
3. Implémenter les contrôles B1 à B31 et W1 à W6, dans l'ordre de `docs/configuration.md`. Chaque contrôle renvoie son code, l'onglet, la ligne et un motif.
4. Analyser les formules KPI selon la grammaire de `docs/configuration.md` §3, sans `eval` ni `exec`.
5. Produire le rapport de chargement : lignes lues par onglet, erreurs, avertissements, empreinte SHA-256 du fichier.
6. Faire passer tous les cas de `tests/attendus.csv` dont le résultat est REFUS ou ACCEPTE (y compris les avertissements attendus).
7. Ne pas implémenter les cas `A_DEFINIR`. Ne pas implémenter P1 à P5, ni les envois, ni Pennylane.

Critère de fin du lot : `pytest` passe, aucun cas d'un autre lot n'est touché, et le rapport de chargement du modèle ne contient aucune erreur.

## Limites d'accès
- Ne pas lire ni écrire hors du dépôt.
- Ne pas installer de dépendance non listée sans l'indiquer dans `docs/decisions/`.
- Ne pas déployer. Ne pas configurer de connexion réelle à Pennylane.


## Lot 2 - STATUT : réalisé
Rapport de chargement exportable (Markdown, JSON) et aperçu des impacts entre deux versions, clé par règle datée. Une version refusée est signalée et ne peut pas être appliquée.
Non réalisé : impact sur les données (nombre de lignes reclassées, KPI recalculés) qui exige des données de test ; application et retour arrière de version (lot 3).


## Lot 3 - STATUT : partiellement réalisé
- Référentiel de comptes : PCG officiel (`config_modele/pcg_reference.csv`), numéros et libellés généraux à vérifier contre l'extrait Pennylane.
- Écritures synthétiques équilibrées sur trois dossiers fictifs (exercice décalé, exercice de neuf mois).
- Contrôle P1 (comptes de classe 6 et 7 mouvementés non classés) implémenté comme fonction ; **non encore branché à une publication** (il n'y a pas encore de publication).
- Non réalisé : application d'une version à un jeu de données, retour arrière, figement des publications.


## Lot 4 - STATUT : réalisé
Dépôt (classeur valide uniquement, doublons refusés), approbation (le déposant ne peut pas approuver, une seule approbation par personne), application (version approuvée et fichier inchangé), retour arrière (version déjà remplacée seulement). L'aperçu des impacts est figé au dépôt. Chaque action est journalisée. Les publications gardent la version utilisée à leur création.
Limites : stub de publication (lot 5) ; un seul rédacteur à la fois, sans verrou inter-processus ; une seule approbation suffit (la règle des deux approbateurs de la spec n'est pas imposée, à trancher).


## Lot 5 - STATUT : réalisé (périmètre restreint)
- Compte de résultat par dossier et exercice : CA hébergement, CA services, charges de classe 6, résultat. Montants en Decimal, arrondis au centime en fin de calcul, aucune annualisation.
- Contrôle P1 branché : publication refusée tant qu'un compte de classe 6 ou 7 n'est pas classé ; le refus est journalisé avec la liste des comptes.
- Instantané figé (JSON + empreinte) : version de configuration, empreinte de la configuration, rubriques utilisées, empreinte des données. Vérifiable et détecte toute modification.
- Limites : pas de KPI, pas de vue groupe, pas de rapport PDF/PPTX ; une publication par dossier et exercice ; classement par période d'exercice (pas au jour près) ; les comptes du modèle `Zenitude_Configuration_modele.xlsx` restent incomplets (P1 refuse), la configuration complète est générée pour les tests.
