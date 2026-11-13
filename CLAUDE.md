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
- Le moteur de KPI est appelé par tous les écrans et exports. Aucune formule officielle recopiée dans le navigateur. Exception phase test : le calculateur d'ajustements de la page (lot 9, `docs/decisions/0002-calcul-ajustements-navigateur.md`), comparé au moteur par `tests/test_site_ajustements.py`.
- Connecteurs séparés du modèle métier : changer de source ne réécrit pas le P&L.
- Cache et précalculs : clés incluant scénario, version et périmètre de droits.

## Commandes
- Installation : `pip install -r requirements.txt`.
- Tests : `python -m pytest` (128 tests : 70 cas de configuration, 9 du lot 2, 9 du lot 3, 11 du lot 4, 7 du lot 5, 15 du lot 6, 5 du lot 7, 2 du lot 9 ; ces deux derniers demandent Playwright et Chromium, sinon ils sont ignorés).
- Versions : `python -m zenitude.config versions <dossier> deposer|approuver|appliquer|revenir|publier|statut ...`.
- Configuration de test complète : `python tests/generer_config_complete.py config_modele/Zenitude_Configuration_modele.xlsx tests/fixtures tests/fixtures/ecritures_synthetiques.csv`.
- Écritures synthétiques : `python tests/generer_ecritures.py tests/fixtures`.
- Validation d'un classeur : `python -m zenitude.config check <fichier.xlsx> [--md|--json]`.
- Aperçu des impacts entre deux versions : `python -m zenitude.config impact <ancien.xlsx> <nouveau.xlsx> [--json]`.
- Génération des fixtures : `python tests/generer_fixtures.py config_modele/Zenitude_Configuration_modele.xlsx tests_out`.
- Mesures d'exploitation synthétiques (lot 6) : `python tests/generer_mesures.py tests/fixtures`.
- Configuration de test avec les six KPI (lot 6) : `python tests/generer_config_kpi.py tests/fixtures/config_complete_v1.xlsx tests/fixtures/config_kpi_lot6.xlsx`.
- KPI d'un dossier : `python -m zenitude.kpi calcul <store> <dossier> <ecritures.csv> <exercices.csv> <mesures.csv> [--du AAAA-MM --au AAAA-MM] [--json]`.
- Site (lot 7) : `python interface/generer_demo.py` puis `python interface/generer_site.py` (écrit `index.html` à la racine, affiché par GitHub Pages).
- Lot 8 (site) : soldes intermédiaires de gestion (`LIGNES_SIG` dans `interface/generer_site.py`, préfixe de compte le plus long, calculés en Python comme le tableau EBITDA) affichés dans la Synthèse d'activité avec un sélecteur EBITDA / SIG ; charte allégée dans `interface/gabarit.html`. Découpage SIG provisoire, à valider par le contrôle de gestion.
- Vue groupe : `python -m zenitude.kpi groupe <store> <ecritures.csv> <mesures.csv> --du AAAA-MM --au AAAA-MM (--dossiers A,B | --activite Seniors) [--json]`.

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


## Lot 6 - STATUT : réalisé (six premiers KPI, vue groupe)
- Module `zenitude/kpi/` : moteur d'évaluation des formules de l'onglet KPI (arbre syntaxique, sans `eval`), appelé par la ligne de commande et destiné à tous les écrans et exports.
- Six KPI de test (`tests/fixtures/config_kpi_lot6.xlsx`, définitions à valider par le contrôle de gestion) : TO-SEN (taux d'occupation), PRIX-MOYEN, REVPAR, REVPAC, DMS (durée moyenne de séjour), CAPTAGE-PDJ.
- Mesures comptables (agrégats de base des Rubriques) calculées par mois à partir des écritures ; mesures d'exploitation (LN_VENDUES, LN_DISPONIBLES, NB_SEJOURS, NUITEES_CLIENTS, COUVERTS_PDJ) lues dans `tests/fixtures/mesures_exploitation.csv` (fictif ; plus tard Mews ou saisie).
- Absence de donnée (ligne absente ou valeur vide, mois sans écriture) : « non calculable » avec mesure, dossier et mois. Dénominateur nul : « non calculable ». Compte non classé (P1) : toutes les mesures comptables du dossier sont non calculables.
- Vue groupe : mesures sommées sur tous les dossiers puis formule appliquée (ratio de sommes). Période obligatoire (exercices décalés). Périmètre par liste de dossiers ou par activité (onglet Referentiel).
- Seuls les KPI au statut « actif » et en vigueur sur la période sont calculés. Le résultat cite la version et l'empreinte de la configuration.
- Limites : MOYENNE_PONDEREE et DERNIERE rendent « non calculable » (grain fin non disponible) ; pas de groupes de l'onglet Groupes (dynamiques, composés) ; pas de publication figée des KPI ; pas de rapport PDF/PPTX ; le modèle `Zenitude_Configuration_modele.xlsx` n'est pas modifié.


## Lot 7 - STATUT : réalisé (site de démonstration)
- `index.html` à la racine : application de pilotage affichée par GitHub Pages (tableau de bord, résidences, compte de résultat, données, configuration ; budgets et rapports annoncés).
- Généré par `interface/generer_site.py` à partir du gabarit `interface/gabarit.html`. Tous les chiffres sont calculés par le moteur réel (lots 5 et 6) puis intégrés à la page : le navigateur affiche, il ne calcule aucune formule.
- Jeu de démonstration distinct des fixtures de test : `interface/demo/` (huit résidences fictives, exercices octobre-septembre et civils, une valeur absente volontaire en août 2026 pour Le Belvédère), produit par `interface/generer_demo.py`.
- Correction du lot 5 : la publication ne retient que les écritures datées dans l'exercice publié.
- Après toute modification du moteur, de la configuration de démonstration ou du gabarit, régénérer `index.html` et le committer.
- Limites : site statique (pas de saisie, pas de dépôt de configuration, pas d'authentification) ; le dossier `maquette/` est remplacé par ce site et peut être supprimé.


## Lot 8 - STATUT : réalisé (charte Zenitude et parcours de connexion)
- Charte graphique Zenitude appliquée au gabarit : bleu foncé #0F506C, bleu clair #007298, gris #333E48, orange #DE7233 (accent), police Montserrat ; logo `interface/logo_zenitude.png` intégré à la page par `generer_site.py`.
- Parcours en trois écrans : connexion (e-mail + mot de passe, factice), choix du périmètre (groupes et résidences), application.
- Le périmètre se change uniquement par le logo Zenitude (retour à la liste) ou le bouton Périmètre (menu déroulant). Il n'y a plus d'onglet Résidences.
- Tableaux de bord : synthèse (6 KPI, graphiques mensuels, tableau jusqu'à l'EBITDA avec colonnes Réalisé / Projection et totaux), indicateurs hôteliers, compte de résultat, contrôle des données.
- Import et paramètres : import comptable Pennylane (factice), données externes, plan comptable, journaux, sections analytiques, paramètres KPI.
- Présentation EBITDA provisoire dans `LIGNES_EBITDA` (`generer_site.py`) : à reporter dans l'onglet Rubriques et à valider par le contrôle de gestion. La projection reprend les écritures fictives tant que le module Budgets n'existe pas.
- Limites : l'authentification n'est pas réelle (point ouvert n° 7) ; pas de connexion Pennylane.


## Lot 9 - STATUT : réalisé (site : thème, période libre, ajustements)
- Thème d'affichage Clair (défaut), Sombre, Auto : bouton à côté de « Se déconnecter », choix mémorisé dans le navigateur.
- Réglette de période : plage libre de mois sur toutes les données de démonstration (octobre 2025 à décembre 2026), raccourcis (dernier mois importé, 12 derniers mois, année, exercice de la résidence, toute la période), clic sur un mois (Maj + clic pour étendre). Elle pilote la Synthèse, les Indicateurs, les Comptes et provisions et les Écarts. Les graphiques montrent toute la frise avec la période en surbrillance ; les tableaux EBITDA et SIG ont une colonne par mois de la période, un total « Réalisé » et un total de période.
- Ajustements (section « Ajustements ») : comptes simulés (exemple 70610000P, classés par le plus long préfixe commun avec les comptes réels) et provisions ou ajustements de compte, par résidence ou pour toutes. Règle = somme de termes (montant fixe par mois, pourcentage d'un ou plusieurs comptes, montant par donnée externe) ou saisie mensuelle pour une résidence. Période d'application optionnelle. Commutateur Réel / Ajusté sur tous les tableaux de bord, page Écarts Réel → Ajusté, export et import JSON.
- Calculateur dans la page (décision 0002) : `generer_site.py` fournit `calcul` (montants mensuels par compte crédit - débit, couverture, données d'exploitation, rubriques, libellés PCG) et les règles des lignes EBITDA et SIG ; `gabarit.html` rejoue les mêmes règles que le moteur Python.
- Limites : ajustements enregistrés dans le navigateur seulement ; la page ne rejoue que les rubriques « tous dossiers, préfixe, sans exception ni date de fin » (le générateur refuse le reste) ; MOYENNE_PONDEREE et DERNIERE restent non calculables ; les publications figées ne tiennent pas compte des ajustements ; pas de validation à deux personnes des ajustements.
