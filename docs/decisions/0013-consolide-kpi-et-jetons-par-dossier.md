# 0013 - Lot 19 : dépôt du consolidé KPI et jetons Pennylane par dossier

Date : 25 novembre 2026
Statut : étape 1 approuvée par le porteur du projet (25 novembre 2026). Étape 2 (données réelles) : **à approuver**
par la DSI et la DAF avant toute mise en œuvre.

## Contexte

Le porteur du projet veut éviter de passer dossier par dossier chaque mois : synchroniser Pennylane et déposer
les KPI pour tout un groupe de résidences en une fois, tout en gardant la possibilité de le faire pour une seule
résidence. Zenitude n'a pas d'espace cabinet Pennylane (pas de jeton cabinet) : il faut un jeton par dossier, soit
une centaine. Les KPI sont déjà consolidés chaque mois par l'outil KPI (Excel) dans `Consolide_KPI_<année>.xlsx`,
dont l'onglet « Données KPI » contient une ligne par résidence et par mois (2019 à aujourd'hui).

## Décisions

### KPI : dépôt du consolidé tel quel

1. La page Données externes reconnaît le consolidé (en-tête « Résidence (nom Mews) ») et lit son onglet
   « Données KPI ». Le modèle de saisie du lot 15 reste accepté, inchangé.
2. Seules les résidences du **périmètre choisi** (groupe ou résidence) sont importées ; les autres lignes sont
   comptées et ignorées. Un même fichier sert donc au groupe comme à la résidence.
3. Rattachement : nom Mews exact, puis code avant « - » (`XYZ - Résidence…`), puis premier mot collé au tiret
   (`ABCZS- …`), comparés au code Mews de la résidence (`residences.code_mews`), à son code, à son dossier et à son
   nom. Les résidences non rattachées sont listées dans l'aperçu, où un administrateur les rattache.
4. On importe les **quantités et montants de base** (22 mesures, `IMPORT_KPI` de `generer_site.py`), jamais les
   ratios : un ratio de groupe est un rapport de sommes (invariant 4). Correspondance avec les mesures du moteur :
   `LN_VENDUES` = Nuitées totales, `LN_DISPONIBLES` = Capacité totale, `NB_SEJOURS` = Nb de réservations,
   `NUITEES_CLIENTS` = Clients présents, `COUVERTS_PDJ` = Nb PDJ (définitions des KPI du moteur toujours à valider
   par le contrôle de gestion, point ouvert 11). Les autres mesures (lots, capacités et nuitées hôtelières et
   seniors, CA Mews, CA SAP, restauration seniors) sont conservées pour les tableaux de bord et le futur contrôle du
   CA Mews / Pennylane.
5. Les huit ratios du fichier (TO hôtelier, PM, RevPar, RevPac, DMS, captage PDJ, TO seniors, TO résidence) sont
   recalculés et comparés (écart > 0,1 % signalé, jamais corrigé). Définitions vérifiées sur le fichier réel du
   porteur du projet : concordance sur plus de 99,9 % des lignes (vérification faite hors dépôt).
6. **Règle d'erreur différente du lot 15.** Une erreur de structure (colonne manquante, mois illisible, même
   résidence et même mois deux fois) refuse tout le dépôt. Une valeur illisible ou une **quantité négative** est
   écartée, listée, et le reste est importé : le fichier réel contient une centaine de valeurs négatives anciennes,
   qui bloqueraient tout l'historique avec la règle « tout ou rien ». Les montants `CA_...` peuvent être négatifs
   (avoirs). Une cellule vide n'est jamais un zéro et ne supprime pas une valeur déjà importée.
7. Statut de chaque mois (Complet, Estimé, Anomalie, Ancien fichier), source et détail conservés (`kpi_mois`),
   affichés dans la grille « Suivi des mois » et dans le détail des calculs. Historique des dépôts (`depots_kpi`).
8. Seules les valeurs nouvelles ou modifiées sont envoyées ; un second dépôt identique n'écrit rien.
9. Groupes du fichier : segment, région, RM et regroupement du dernier mois de chaque résidence rattachée, proposés
   à la création (identifiants `GR-SEG-`, `GR-REG-`, `GR-RM-`, `GR-RGP-`). La mise à jour retire une résidence
   d'un ancien groupe de même type ; les groupes créés à la main ne sont jamais touchés.
10. Lectures par pages de 1 000 lignes (`lireTout`) : la base plafonne chaque réponse, ce qui aurait tronqué sans
    message les mesures importées de tout le parc.

### Pennylane : un jeton par dossier, chiffré

11. Le jeton n'est **pas** rangé dans les secrets GitHub (une centaine de secrets, saisie à la main, limite du
    dépôt). Il est saisi dans la page Import comptable, **chiffré dans le navigateur** (WebCrypto : RSA-OAEP 3072
    SHA-256 + AES-GCM 256) avec la clé publique du logiciel, puis enregistré (`connexions_pennylane`).
12. La paire de clés est créée une fois dans le navigateur d'un administrateur. La clé publique est rangée dans la
    base (`cle_jetons`) ; la clé privée est affichée une seule fois, n'est enregistrée nulle part, et se colle dans
    le secret GitHub `PENNYLANE_CLE_PRIVEE`. Remplacer la clé oblige à ressaisir les jetons (signalé).
13. Droits par colonne : une personne connectée ne peut **jamais relire** `jeton_chiffre`, ni écrire l'état du
    test ; seul GitHub Actions (clé secrète) lit le jeton chiffré et seul lui le déchiffre. Le chiffrement ne
    dépend pas de Supabase : les jetons chiffrés déménagent tels quels vers un autre serveur.
14. Test d'un jeton (demande de type `test` de la fonction `lancer-synchro`, même workflow) : `GET /me` seulement
    (identité de la société, aucune donnée comptable). Refusé et **effacé** si un droit n'est pas en lecture seule,
    si la société est déjà rattachée à une autre résidence (index unique) ou diffère de celle déjà rattachée à
    cette résidence. La première société acceptée est figée sur la résidence (`societe_attendue`).
15. Échéance calculée par la base à partir de la durée choisie (1, 6, 12 mois, illimitée), alerte à 30 jours ;
    un jeton refusé par Pennylane pendant une synchronisation passe « à renouveler ».
16. Dépendance ajoutée : `cryptography` (Python, GitHub Actions uniquement) pour déchiffrer.

### Garde-fous conservés (étape 2 à approuver)

17. Rien ne change pour les données réelles : la base n'accepte que des résidences « fictives » dans
    `donnees_residences`, et le connecteur ne lit que le dossier de test (`DOSSIERS_AUTORISES`). Après ce lot, les
    jetons de vraies résidences peuvent être **enregistrés et testés** (identité de la société seulement), mais leur
    comptabilité n'est pas lue : la synchronisation les indique « non lue ». Le dossier de test utilise le jeton
    du logiciel s'il est connecté, sinon le secret `PENNYLANE_TOKEN_PILOTE` (inchangé).
18. **Étape 2, à approuver** : faire entrer des données réelles dans la base (créer les résidences réelles, lever
    la contrainte « fictif », étendre la liste des dossiers lus aux connexions testées, synchroniser plusieurs
    dossiers à la suite). Elle touche l'invariant 8 et la décision 0004 (phase test). Les KPI réels suivent la même
    règle : les résidences réelles n'existent pas encore dans la base de test.

## Conséquences

- Migration 011 (sans remise à zéro), fonction `lancer-synchro` à redéployer, secret GitHub `PENNYLANE_CLE_PRIVEE`
  à créer : voir `docs/lot19_mise_en_route.md`.
- Le modèle de saisie du lot 15 est inchangé (les mesures du consolidé n'y figurent pas, `modele: False`).
