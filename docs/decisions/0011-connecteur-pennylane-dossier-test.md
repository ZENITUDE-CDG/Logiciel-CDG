# 0011 - Lot 18 : connecteur Pennylane sur le dossier de test

Date : 24 novembre 2026
Statut : approuvé par le porteur du projet (24 novembre 2026). Aucune autre approbation requise : le
dossier de test ne contient aucune donnée confidentielle.

## Contexte
CLAUDE.md interdisait toute connexion réelle à Pennylane. Le porteur du projet a créé dans Pennylane un
jeton en lecture seule sur un dossier de test (pas une résidence en activité), rangé dans les secrets
GitHub (`PENNYLANE_TOKEN_PILOTE`). Trois workflows manuels ont validé la connexion, la balance d'un mois et
la structure des données, sans afficher aucune valeur.

## Décisions
1. **Connexion autorisée pour ce seul dossier**, en lecture seule, jeton dans les secrets GitHub uniquement.
   Liste blanche dans le connecteur : `PENNY-TEST`. La limite de CLAUDE.md reste valable pour tout autre
   dossier.
2. **Connecteur séparé du modèle métier** (`zenitude/connecteurs/pennylane.py`) : il traduit les données
   Pennylane au format des fichiers du moteur (`ecritures.csv`, `exercices.csv`) et ne calcule rien.
   Bibliothèque standard uniquement (aucune nouvelle dépendance).
3. **Résidence `RES-TEST`** (dossier `PENNY-TEST`), marquée `fictif = true`, hors de tout groupe : visible
   des seuls administrateurs. Publiée avec la démonstration ; les huit résidences de démonstration ne
   changent pas (test).
4. **Aucune valeur comptable dans le dépôt, les journaux, les artefacts ou un service d'IA** (invariant 8) :
   les fichiers sont fabriqués dans un dossier temporaire du runner, les journaux n'affichent que des
   nombres de lignes, des statuts et des contrôles oui / non.
5. **Classement provisoire** des comptes de classes 6 et 7 du dossier de test non couverts par les
   rubriques : préfixe du PCG de référence, marqué « Provisoire lot 18 », ajouté à une copie temporaire de
   la configuration (jamais au classeur du dépôt). À valider par le contrôle de gestion.
6. **Écritures reprises** : « valides » (validées seulement, par défaut) ou « tous » (validées et
   brouillard), choisi au lancement de « Synchro Pennylane test ». Le paramètre dans la page (Import et
   paramètres) arrive au lot 18b. Le mode est conservé avec les données publiées.
7. **Garde-fous inchangés** : toute résidence marquée réelle reste refusée par la publication. Le dépôt
   étant public, le branchement d'une résidence réelle exige une nouvelle décision (dépôt privé ou autre
   hébergement, validé par la DSI).

## Conséquences
- La publication automatique (« Tests et publication ») relit aussi le dossier de test, en mode
  « valides » ; une erreur Pennylane ne l'empêche pas de publier la démonstration (avertissement).
- Les écritures du dossier de test antérieures au premier mois de la démonstration ne sont pas reprises
  (frise, trésorerie et dates d'effet des rubriques) : elles sont comptées dans le journal.
- Le total « Groupe Zenitude » des administrateurs inclut le dossier de test.
