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
- Phase test, lots 12 et 13 (décisions 0004, 0006 et 0007) : écart accepté. Site GitHub Pages + base de test Supabase, droits vérifiés dans PostgreSQL par des règles par ligne (`migrations/003_droits.sql`), sans serveur applicatif. Pour l'invariant 9, la base tient lieu de serveur pendant la phase test ; à réexaminer avant toute mise en production. Les chiffres sont calculés par le moteur Python dans GitHub Actions et publiés dans la base (lot 13) ; la page en ligne ne contient aucune donnée.
- Backend Python / Django, PostgreSQL, traitements d'import et de calcul en arrière-plan.
- Frontend React / TypeScript. Metabase possible pour les tableaux de bord (à décider).
- Modules : données certifiées, connecteur Pennylane, configuration, moteur de KPI, clôture, budgets, rapports, administration.
- Le moteur de KPI est appelé par tous les écrans et exports. Aucune formule officielle recopiée dans le navigateur. Exception phase test : le calculateur d'ajustements et de lissages de la page (lots 9 et 14, `docs/decisions/0002-calcul-ajustements-navigateur.md`), comparé au moteur par `tests/test_site_ajustements.py` ; le détail des calculs (lot 14) refait des sommes d'écritures pour expliquer un montant et affiche le rapprochement avec le moteur, sans le remplacer.
- Connecteurs séparés du modèle métier : changer de source ne réécrit pas le P&L.
- Cache et précalculs : clés incluant scénario, version et périmètre de droits.

## Commandes
- Installation : `pip install -r requirements.txt`.
- Tests : `python -m pytest` (341 tests : 70 cas de configuration, 9 du lot 2, 9 du lot 3, 11 du lot 4, 7 du lot 5, 15 du lot 6, 5 du lot 7, 2 du lot 9, 110 du lot 11, 20 du lot 12, 39 du lot 13, 18 du lot 14, 21 du lot 15, 5 du lot 16 ; les tests de page des lots 9, 11, 13 à 15 demandent Playwright et Chromium, sinon ils sont ignorés ; ceux des lots 12 à 15 sur la base demandent PostgreSQL (`ZENITUDE_ENV=test` et `DATABASE_URL`, migrations appliquées), sinon ils sont ignorés).
- Tests et publication automatiques : `.github/workflows/tests-et-publication.yml`. À chaque dépôt, toute la suite tourne sur GitHub (onglet Actions) avec une base PostgreSQL temporaire créée depuis `migrations/` (aucun secret, Supabase jamais touché). Puis, sur main seulement et si les tests passent, `python interface/publier_supabase.py` publie les chiffres dans la base de test avec le secret GitHub `SUPABASE_SECRET_KEY` (décision 0007). Essai sans envoi : `python interface/publier_supabase.py --essai <dossier>`.
- Installation de la base de test : `python scripts/assembler_installation.py` régénère `scripts/installation_supabase.sql` (remise à zéro + migrations + données de départ) ; un test vérifie qu'il est à jour.
- Versions : `python -m zenitude.config versions <dossier> deposer|approuver|appliquer|revenir|publier|statut ...`.
- Configuration de test complète : `python tests/generer_config_complete.py config_modele/Zenitude_Configuration_modele.xlsx tests/fixtures tests/fixtures/ecritures_synthetiques.csv`.
- Écritures synthétiques : `python tests/generer_ecritures.py tests/fixtures`.
- Validation d'un classeur : `python -m zenitude.config check <fichier.xlsx> [--md|--json]`.
- Aperçu des impacts entre deux versions : `python -m zenitude.config impact <ancien.xlsx> <nouveau.xlsx> [--json]`.
- Génération des fixtures : `python tests/generer_fixtures.py config_modele/Zenitude_Configuration_modele.xlsx tests_out`.
- Mesures d'exploitation synthétiques (lot 6) : `python tests/generer_mesures.py tests/fixtures`.
- Configuration de test avec les six KPI (lot 6) : `python tests/generer_config_kpi.py tests/fixtures/config_complete_v1.xlsx tests/fixtures/config_kpi_lot6.xlsx`.
- KPI d'un dossier : `python -m zenitude.kpi calcul <store> <dossier> <ecritures.csv> <exercices.csv> <mesures.csv> [--du AAAA-MM --au AAAA-MM] [--json]`.
- Site (lot 7) : `python interface/generer_demo.py` puis `python interface/generer_site.py` (écrit `index.html` à la racine, affiché par GitHub Pages ; depuis le lot 13, sans aucune donnée). Démonstration complète à ouvrir en local : `python interface/generer_site.py demo.html`.
- Modèle d'import des KPI (lot 15) : `python interface/generer_modele_import.py` (écrit `modeles/Zenitude_Import_KPI_modele.xlsx`) ; un test vérifie qu'il est à jour.
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
- Ne pas déployer. Ne pas configurer de connexion réelle à Pennylane. Seule exception : le site GitHub Pages, la base de test Supabase et la publication des chiffres fictifs par GitHub Actions (décisions 0004, 0006 et 0007).
- Aucune clé secrète Supabase (« secret » / « service_role »), aucun mot de passe de base dans le dépôt. Seule la clé publique figure dans `app/config.js` (décision 0006). La clé secrète n'existe que dans les secrets GitHub (`SUPABASE_SECRET_KEY`, décision 0007) ; un test vérifie qu'aucune clé secrète n'est versionnée.


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


## Lot 10 - STATUT : réalisé (site : menu latéral et fiche résidence)
- Les barres du haut (sections et sous-onglets) sont remplacées par un menu latéral à gauche : logo, bouton Périmètre, sections (Tableaux de bord, Résidence, Ajustements, Import et paramètres, Budgets, Rapports) avec leurs pages dépliées sous la section active, puis utilisateur, thème et déconnexion en bas.
- Le menu se réduit en icônes seules (bouton chevron en haut du menu) ; le choix est mémorisé dans le navigateur (`zen-menu-reduit`). Sur écran étroit (900 px et moins) il devient un tiroir ouvert par le bouton de la barre du haut.
- Nouvelle section « Résidence » : sur une résidence, fiche complète (identité du référentiel : code, dossier Pennylane, société, activité, région, marque, dates ; indicateurs du dernier mois importé ; exercices et écritures ; résultat de l'exercice publié ; groupes d'appartenance ; ajustements actifs ; couverture des données). Sur un groupe, liste des résidences du périmètre : un clic ouvre la fiche.
- `generer_site.py` exporte en plus pour chaque résidence : société, marque, date d'ouverture, date d'effet, statut (colonnes déjà présentes dans l'onglet Referentiel).
- La réglette de période reste figée en haut de page quand on fait défiler (Synthèse, Indicateurs, Comptes et provisions, Écarts) : la période se lit et se modifie à tout moment.
- Aucun changement du moteur, de la configuration ni des calculs.


## Lot 11 - STATUT : réalisé (compte de résultat PCG et onglet Trésorerie)
- Référentiel : règlement ANC 2014-03 modifié par ANC 2022-06, **système de base** (art. 821-2), applicable aux exercices ouverts à compter du 1er janvier 2025. Le système développé n'existe plus ; les transferts de charges (791, 796, 797) sont supprimés. Détail et rattachements à valider : `docs/compte_resultat_pcg.md`.
- `zenitude/comptes/pcg.py` : compte de résultat en liste, un compte dans un seul poste (préfixe le plus long), compte non classé = résultat bloqué, absence d'écriture = non calculable, N-1 « n.d. ». Figé dans l'instantané de publication (`compte_resultat`, avec rapprochement sur le résultat du lot 5). Page « Compte de résultat » : liste des publications, détail du modèle ANC, cumul des résidences de même exercice (jamais d'exercices décalés additionnés).
- `zenitude/comptes/tresorerie.py` : position (comptes 51 et 53), créances (411, 413, 416, 418) et dettes (401, 403) avec lettrage, échéance (pièce + 30, 45, 60 jours ou échéance de la pièce), balance âgée, à-nouveaux. Définitions : `docs/tresorerie.md`. Sans lettrage : non calculable. Échéance absente : « échéance inconnue ».
- Section « Trésorerie » du site (position, créances, dettes) : la page additionne les agrégats par dossier fournis par le moteur (décision `docs/decisions/0003-tresorerie-et-compte-de-resultat-pcg.md`), taux = ratio de sommes. Les ajustements du lot 9 ne s'appliquent pas à la trésorerie.
- Écritures : trois colonnes facultatives `tiers`, `lettrage`, `echeance` (changement de contrat, voir `docs/tresorerie.md`). Jeu de démonstration étendu (règlements fictifs jusqu'à octobre 2026, à-nouveaux, un acompte non affecté, un dossier sans échéance) ; les écritures de classes 6 et 7, les mesures et la configuration sont inchangées.
- Limites : N-1 non importé ; lettrage partiel traité comme pièce ouverte ; pas de prévision de trésorerie (module Budgets) ; colonnes tiers, lettrage, échéance à confirmer dans l'extraction Pennylane réelle ; règlement ANC 2026-03 non analysé ; rattachements 708, 709, 608, 648, 649 provisoires.


## Lot 12 - STATUT : réalisé (utilisateurs, rôles, parcs, connexion provisoire)
Décisions : `docs/decisions/0004`, `0005` (dépendances), `0006` (site GitHub Pages et Supabase).
- Base : `migrations/001_profils.sql` (profils : adresse, nom, rôle administrateur / collaborateur / lecture, actif), `002_residences_groupes_parcs.sql` (résidences = dossiers Pennylane, groupes, appartenance, parcs : une résidence ou un groupe par ligne), `003_droits.sql` (règles par ligne). SQL standard PostgreSQL ; rejouables.
- Identité : adresse e-mail du jeton de connexion (`request.jwt.claims`), fonction `email_courant()`. Le passage à Microsoft 365 ne change que les pages de connexion.
- Droits : administrateur voit et gère tout ; collaborateur lit et modifie les résidences de son parc ; lecture seule lit son parc. Donner un groupe donne les résidences ajoutées plus tard. Un compte sans profil actif et une personne non connectée ne voient rien. Création d'utilisateurs, groupes, résidences et parcs : administrateur seulement.
- Site : `connexion.html` (connexion par e-mail et mot de passe), `espace.html` (mon parc, changement de mot de passe), `administration.html` (utilisateurs, rôles, état actif, parcs, résidences, groupes, affectations). Code commun dans `app/` (`config.js`, `zenitude.js`, `style.css`) ; `app/garde.js` renvoie le tableau de bord vers la connexion (confort, ignoré en `file://`).
- Tableau de bord (`interface/gabarit.html`, donc `index.html`) : en ligne, l'utilisateur affiché est celui de la vraie connexion (session `zenitude-session`) et « Se déconnecter » ferme la session (`connexion.html?deconnexion=1`). En `file://` (tests de page des lots 9 et 11), la connexion factice du lot 8 est conservée.
- Données de départ : `scripts/donnees_test.sql` (depuis le lot 13 : Raphael administrateur, Benjamin collaborateur avec le groupe GRP-SENIORS, les huit résidences de démonstration RES-001 à RES-008 ; RES-901 et RES-902 supprimées). Installation Supabase en un collage : `scripts/installation_supabase.sql` (remise à zéro + migrations + données), assemblé à partir des fichiers ci-dessus : le régénérer si l'un d'eux change.
- Tests : `tests/lot12/test_lot12_droits.py` (20 tests : trois profils, lecture, modification, administration, intégrité, démonstration des deux parcs).
- Règle : toute nouvelle table reçoit ses règles par ligne et ses tests de droits dans le même commit. Les calculs restent dans le moteur Python, jamais dans la base.
- Nettoyage (23 novembre 2026) : supprimés `maquette/` (remplacée par le site, lot 7), l'archive `zenitude-pilotage-depot-git.zip`, l'ancienne migration `001_utilisateurs.sql`, l'ancien test `tests/lot12/test_droits.py` et un doublon de la décision 0004 ; ajoutés `.gitignore` et `.github/workflows/tests.yml`.
- Limites : le tableau de bord n'est pas encore filtré par parc (données fictives intégrées à la page) ; pas de mot de passe oublié ; comptes de connexion créés dans Supabase par un administrateur.


## Lot 13 - STATUT : réalisé (chiffres depuis la base, ajustements partagés, lissage)
Décision : `docs/decisions/0007-publication-et-ajustements-partages.md`. Mise en route : `docs/lot13_mise_en_route.md`.
- Publication : `interface/publier_supabase.py` calcule tout avec le moteur (`generer_site.construire`), découpe le résultat en une partie commune (paramètres, KPI, lignes EBITDA et SIG, modèle PCG, classement des comptes, libellés des groupes de configuration : aucune donnée de résidence) et une partie par résidence (référentiel, compte de résultat figé, trésorerie, couverture, exercices, montants mensuels par compte, exploitation, volumes), puis les écrit dans `donnees_communes` et `donnees_residences`. Lancée par GitHub Actions sur main après les tests. Refuse une résidence marquée réelle ; ne publie que pour les résidences créées dans la base.
- Base : `migrations/004_donnees_ajustements.sql` : `donnees_communes`, `donnees_residences` (lecture selon le parc, écriture par le rôle de service seulement, `CHECK (fictif)`), `comptes_simules`, `ajustements` (portée « toutes les résidences » ou liste de dossiers, contenu structuré, actif, révision, auteur et dernier modificateur tracés par la base). Fonctions `voit_dossier`, `modifie_dossier`, `voit_ajustement`, `gere_ajustement`.
- Droits des ajustements : lecture si toutes leurs résidences sont dans le parc (ou portée « toutes ») ; collaborateur : création, modification, suppression sur ses résidences ; « toutes les résidences » : administrateur seulement ; lecture seule : rien. Comptes simulés : création par administrateur et collaborateur, suppression par l'administrateur ou l'auteur.
- Page en ligne (`index.html`) : aucune donnée intégrée. Script de démarrage en fin de `gabarit.html` : connexion, lecture de la base, `assemblerDonnees` (recompose les données du site pour les seules résidences visibles, même résultat que le générateur), puis lancement du code de l'application (`<script type="text/plain" id="code-application">`). Périmètre « Groupe Zenitude » pour l'administrateur, « Mon parc » sinon ; groupes de configuration et groupes créés dans Administration. En `file://` avec données intégrées (tests, démonstration locale), fonctionnement inchangé (ajustements dans le navigateur).
- Ajustements en ligne : enregistrés dans la base, actifs dès leur création, rechargés après chaque écriture ; boutons masqués selon les droits (la base reste seule juge). Import en ligne : ajoute, ne remplace jamais.
- Lissage par compte : remplacé au lot 14 par le lissage d'écritures (Lissage de postes).
- Tests : `tests/test_lot13_publication.py` (15 : découpage sans fuite, garde-fous, requêtes, installation à jour, aucune clé secrète versionnée, page en ligne sans données), `tests/lot13/test_lot13_droits.py` (19, base PostgreSQL), `tests/test_lot13_page.py` (5, navigateur : assemblage identique au générateur, assemblage restreint au parc, démarrage en ligne avec base simulée, lissage).
- Nettoyage : `.gitignore` et le workflow (supprimés ou jamais versionnés par le dépôt par glisser-déposer) recréés ; `requirements.txt` complété (`psycopg[binary]`).
- Limites : calculateur d'ajustements dans la page (décision 0002) ; publications figées sans ajustements ; pas d'historique des publications dans la base ; pas de validation à deux personnes (choix du porteur du projet).


## Lot 14 - STATUT : réalisé (détail des calculs, lissage de postes, compte, logo)
Décision : `docs/decisions/0008-detail-des-calculs-et-lissage-de-postes.md`. Mise en route : `docs/lot14_mise_en_route.md`.
- Écritures : `generer_site._ecritures_detail` ajoute `ecritures` aux données du site (par dossier : identifiant pièce-rang, date, journal, pièce, compte, libellé, montant en centimes crédit - débit, tiers, lettrage, échéance) ; publiées dans la partie de chaque résidence. La frise (`calcul.mois`) va jusqu'à décembre de l'année suivante ; `calcul.fin_donnees` = dernier mois avec écritures.
- Détail des calculs (`interface/gabarit.html`, « Lot 14 : détail des calculs ») : attribut `data-x` (type de montant et paramètres) sur tous les montants des tableaux, cartes et graphiques ; un seul écouteur ouvre le panneau. Types : `lig` (ligne EBITDA ou SIG), `taux`, `cpt` (compte : écritures + ajustements + lissages), `kpi`, `mes` (mesure), `cr` et `crc` (compte de résultat publié), `pub` (résultat du lot 5), `tr` (position de trésorerie), `tt` (créances et dettes, mêmes règles que `tresorerie.py`), `aj` (ajustement). Rapprochement affiché avec les montants du moteur. Export CSV des écritures.
- Lissage de postes (Ajustements) : une résidence, un exercice (N-1, N, N+1) ; tableau par compte (réalisé et lissé E-1, E, E+1, interrupteur par compte) ; fenêtre des écritures du compte (lissée oui ou non, période de début et de fin, parts par mois, masquer les lissées, lisser toutes les écritures). Répartition à parts égales au centime, jusqu'à la fin de la frise, y compris sur des mois sans écriture ; total conservé ; écriture modifiée ou supprimée = lissage signalé et non appliqué. En ligne : table `lissages` (`migrations/005_lissages.sql`) ; en local : navigateur (`zen-lissages`).
- Compte : clic sur le nom et l'adresse en bas à gauche (`#lien-compte`) ; bouton flottant supprimé de `app/garde.js` ; « Mon compte ». Logo de Mon compte et d'Administration : `index.html#choix` ouvre le choix des résidences.
- Tests : `tests/test_lot14_page.py` (12 : toutes les pages de trois périmètres, valeur du détail = valeur affichée et rapprochements exacts ; écritures = soldes du moteur ; compte de résultat publié poste par poste ; trésorerie, créances et dettes sur trois modes d'échéance ; parcours jusqu'aux écritures ; lissage sur l'exercice suivant ; écriture modifiée ; lissage par l'écran ; enregistrement dans la base simulée ; compte et logo), `tests/lot14/test_lot14_droits.py` (6, base PostgreSQL).
- Limites : nombres de lignes (contrôle, imports) non détaillés ; calcul des lissages dans la page (décision 0002).


## Lot 15 - STATUT : réalisé (comptes bancaires, équilibre financier, EBITDA du groupe, import des KPI)
Décision : `docs/decisions/0009-tresorerie-equilibre-ebitda-import-kpi.md`. Mise en route : `docs/lot15_mise_en_route.md`.
- Moteur (`zenitude/comptes/tresorerie.py`) : virements internes (`pieces_internes`) exclus des encaissements et décaissements ; `banques` par compte de disponibilités et par mois (solde, encaissements, décaissements, virements internes reçus et émis) ; `bilan` par arrêté (capitaux, résultat non affecté, ressources et emplois stables, FRNG, stocks, créances, dettes, BFR, disponibilités, concours, TN, écart de contrôle). Publiés avec la trésorerie de chaque résidence. Définitions : `docs/tresorerie.md`.
- Démonstration : compte secondaire 5122 (fournisseur FOU003 payé dessus), virements internes mensuels depuis le 512.
- Pages : Trésorerie, « Comptes bancaires » (administrateurs en ligne ; paramètres libellé, rôle, minimum dans `comptes_bancaires` ; virement conseillé ; export CSV) et « Analyse du solde » (N et N-1, par compte) ; Tableaux de bord, « FRNG, BFR et TN » ; graphiques de la synthèse sur la période de la réglette. Tout montant reste cliquable (types `tr` avec `cpt` et `vir`, `bil`, `bilc`).
- Tableau EBITDA : `LIGNES_EBITDA` et `RATIOS_EBITDA` de `generer_site.py`, modèle de gestion du groupe (règles : `=compte` exact, `préfixe:MOT` sur le libellé du compte, préfixe le plus long ; même règle en Python et dans la page) ; KPI en tête ; éléments hors CR et résultat net (un test vérifie que le résultat net du tableau est le résultat comptable).
- Import des KPI (Données externes) : catalogue `IMPORT_KPI` (`generer_site.py`), modèle Excel et CSV pré-rempli, contrôle complet tout ou rien (`validerImport`), Excel lu par SheetJS chargé à la demande, CSV lu sans bibliothèque ; table `mesures_importees` (administrateurs) ; valeurs appliquées aux KPI de la page (`appliquerMesures`).
- Base : `migrations/006_kpi_et_comptes_bancaires.sql` (règles par ligne, traces d'auteur posées par la base).
- Tests : `tests/test_lot15.py` (8), `tests/lot15/test_lot15_droits.py` (4), `tests/test_lot15_page.py` (9).
- Limites : moteur Python sans les KPI importés ; colonnes du dossier KPI non reprises tant que les KPI ne sont pas validés ; ratios par chambre du modèle CR non repris ; mots-clés inactifs sans libellé de compte ; N-1 non disponible sans historique.


## Lot 16 - STATUT : réalisé (ruban supérieur : exercice de référence et périmètre)
Un ruban bleu (`--bleu-fonce` de la charte) reste en haut de chaque page, avec deux boutons : l'exercice de référence (N en cours, N+1, N-1 quand ils existent) et le périmètre (résidence ou groupe), qui quitte le haut du menu latéral. L'exercice fixe la période de la réglette sur chaque page ; la réglette permet ensuite de l'affiner (le ruban l'indique : « Période modifiée »). Exercices lus dans `D.imports`, jamais supposés janvier-décembre ; pour un groupe, de la première à la dernière date des exercices de même rang (exercices décalés signalés). Un changement de périmètre reprend l'exercice choisi, sauf si la réglette a été réglée à la main. Le raccourci « Exercice de la résidence » de la réglette est retiré (le ruban le remplace). Tests : `tests/test_lot16_page.py`.
