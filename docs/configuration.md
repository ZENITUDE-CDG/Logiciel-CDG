# Configuration métier : format du classeur et contrôles de chargement

Version 0.1 - 13 novembre 2026. Document à valider par le contrôle de gestion avant tout développement du chargeur.
Référence : `Zenitude_Configuration_modele.xlsx` (neuf onglets) et `ZENITUDE_Cadrage_Claude_Code.md` v0.8.

Toutes les données citées en exemple sont fictives.

---

## 1. Principe

Le classeur Excel est une **entrée de données**, jamais un programme. Le logiciel :

1. lit les valeurs de chaque onglet (les formules Excel du classeur ne sont pas évaluées, les cellules calculées de la colonne Contrôle sont ignorées) ;
2. valide la structure et les règles décrites ci-dessous ;
3. calcule l'impact par rapport à la version en vigueur ;
4. n'applique la configuration qu'après validation explicite.

Une configuration partiellement valide n'est jamais appliquée. Une version appliquée n'est jamais modifiée : toute correction donne une nouvelle version.

---

## 2. Format commun

- Première ligne de données : ligne 5 de chaque onglet (titre en ligne 1, légende en ligne 2, en-têtes en ligne 4).
- Les colonnes sont identifiées par leur **en-tête exact**. Un en-tête renommé, absent ou dupliqué bloque le chargement.
- Lignes vides ignorées. Une ligne partiellement remplie est une erreur.
- Encodage UTF-8 à l'export ; séparateur de liste dans les formules : `;`.
- Dates : type date Excel, jamais du texte. Format accepté à la lecture : `jj/mm/aaaa` ou `aaaa-mm-jj`.
- Nombres : décimal avec `,` ou `.` selon le paramètre régional, converti en décimal interne sans arrondi.
- Pourcentages : stockés en fraction (`0,03` = 3 %), conformément au document de cadrage.
- Identifiants (codes RES, KPI, rubriques, groupes, scénarios) : `[A-Z0-9_-]`, 1 à 40 caractères, insensibles à la casse à la lecture, stockés en majuscules. Accents interdits dans les codes.

---

## 3. Grammaire des formules KPI

### 3.1 Éléments

| Élément | Forme | Exemple |
| --- | --- | --- |
| Nombre | chiffres, décimal | `100`, `0.5` |
| Mesure | `[CODE]` où CODE est un agrégat de base connu | `[CA_HEBERGEMENT]` |
| Référence à un KPI | `{CODE_KPI}` (un KPI peut en utiliser un autre) | `{OCC-HOT}` |
| Opérateurs arithmétiques | `+ - * /` et parenthèses | `([A]+[B])/2` |
| Comparaison (dans SI uniquement) | `= <> < > <= >=` | `[A]>0` |
| Fonctions | voir 3.2 | `RATIO([A];[B])` |

Les mesures valides sont exactement les valeurs de la colonne **Agrégat de base** de l'onglet Rubriques, plus le catalogue de mesures fourni par le logiciel (à compléter, voir 9).

### 3.2 Fonctions

| Fonction | Signature | Comportement |
| --- | --- | --- |
| `SOMME(x)` | un argument, une mesure ou une expression | somme sur le périmètre et la période ; une absence de donnée rend le résultat « non calculable » |
| `RATIO(n; d)` | deux arguments | `n / d` calculé sur sommes, jamais moyenne de ratios ; `d = 0` donne « non calculable » avec motif |
| `MOYENNE_PONDEREE(x; p)` | valeurs et poids | somme(x·p) / somme(p) |
| `DERNIERE(x)` | une mesure | dernière valeur connue sur la période, avec sa date |
| `SI(cond; a; b)` | condition puis deux branches | `b` obligatoire ; une absence dans `cond` rend « non calculable » |

Pas d'autre fonction. Pas de boucle, pas de référence de cellule, pas de fonction définie par l'utilisateur.

### 3.3 Règles d'évaluation

- **Absence de donnée** : jamais zéro par défaut. Toute opération avec une absence donne « non calculable » et un motif (« donnée manquante : CA_SERVICES, résidence RES-002, mars 2026 »).
- **Division par zéro** : « non calculable », motif « dénominateur nul ».
- **Unités** : `€ + %` ou `€ + ETP` est refusé. Un ratio entre deux unités différentes doit déclarer son unité dans la colonne Unité. Les multiplications et divisions sont autorisées entre unités, le résultat prend l'unité déclarée.
- **Arrondi** : aucun arrondi intermédiaire. L'arrondi est appliqué une seule fois, à l'affichage, selon la règle déclarée dans la colonne Agrégation si elle la précise (sinon 2 décimales en interne, 0 à l'affichage pour les €).
- **Périmètre** : une formule est évaluée sur le périmètre demandé par l'appelant (résidence, groupe, lot). Les agrégats groupe sont calculés à partir des numérateurs et dénominateurs, jamais à partir de KPI déjà arrondis.

### 3.4 Exemples

```
OCC-HOT     RATIO([LN_VENDUES];[LN_DISPONIBLES])
RESULTAT    [CA_HEBERGEMENT]+[CA_SERVICES]-[PL_CHARGES]
REV-PAR     RATIO([CA_HEBERGEMENT];[LN_DISPONIBLES])
ALERTE-XX   SI({OCC-HOT}<0,6;1;0)
```

Note : l'exemple `RESULTAT-EXP` du modèle contient `[P&L_CHARGES]`. Le caractère `&` n'est pas autorisé dans un identifiant : la mesure devra s'appeler `PL_CHARGES`. Le modèle est corrigé en conséquence (voir 9).

### 3.5 Validation d'une formule

Au chargement, la formule est analysée (analyse syntaxique puis résolution des noms). Erreurs bloquantes : syntaxe invalide, parenthèses non équilibrées, fonction inconnue, mesure inconnue, KPI référencé inexistant, référence circulaire, unités incompatibles, `SI` sans branche `b`.

---

## 4. Contrôles bloquants (chargement refusé)

Chaque contrôle indique l'onglet, la ligne et le motif.

### 4.1 Structure

- B1 : onglet attendu absent ou renommé ; onglet supplémentaire non reconnu (un onglet de notes nommé `Notes` est toléré et ignoré).
- B2 : en-tête absent, renommé ou dupliqué.
- B3 : type de valeur incorrect (texte dans une date, lettres dans un nombre).
- B4 : colonne obligatoire vide sur une ligne non vide.

### 4.2 Référentiels et codes

- B5 : code de résidence en double à la même date d'effet.
- B6 : dossier Pennylane (`Referentiel`, colonne C) absent de la liste des dossiers connus du logiciel et non déclaré « à créer » (colonne « Dossier à créer (oui / non) » = `non`). Un dossier déclaré « à créer » est accepté avec l'avertissement W6.
- B7 : valeur hors de la liste de l'onglet Listes (activité, statut, unité, agrégation, scénario, format, fréquence).
- B8 : code de rubrique, KPI, groupe ou scénario en double pour la même date d'effet.
- B9 : référence vers un code inexistant (rubrique dans Scenarios ou Seuils, KPI dans Rapports ou Seuils, groupe dans Rapports, résidence dans Groupes ou Scenarios).

### 4.3 Dates et chevauchements

- B10 : date de fin antérieure à la date d'effet.
- B11 : deux règles dont les périodes se chevauchent et qui visent le même objet : même code de rubrique, dossiers identiques (ou l'une des deux lignes à `*`) et plages de comptes qui se recouvrent ; même code de KPI ; même scénario, poste et résidence dans Scenarios.
- B12 : date d'effet absente sur une règle active.

### 4.4 Rubriques (règle centrale)

- B13 : un compte est classé dans **plus d'une rubrique de base** : deux lignes de Rubriques avec le même agrégat de base, le même dossier (valeur identique, `*` compris), la même priorité, des plages de comptes qui se recouvrent et des périodes qui se chevauchent. Une ligne à dossier précis et une ligne à `*` ne sont pas en conflit : la règle la plus précise l'emporte. Le logiciel ne tranche jamais par ordre de ligne.
- B14 : préfixe ou plage mal formé (`616-618` attendu pour une plage ; `616*` refusé, le préfixe seul suffit).
- B15 : exception (colonne F) qui n'est pas couverte par le préfixe de la même ligne.

### 4.5 KPI

- B16 : formule invalide selon 3.5.
- B17 : référence circulaire entre KPI (`A` utilise `B` qui utilise `A`, directement ou non).
- B18 : unités incompatibles (addition d'une somme en € et d'un pourcentage).
- B19 : KPI au statut « actif » sans approbateur renseigné.

### 4.6 Groupes

- B20 : groupe dynamique sans critère.
- B21 : critère sur un attribut absent du référentiel (ex. `Marque = X` alors que la colonne Marque est vide pour toutes les résidences concernées). Le critère est refusé, il n'est jamais ignoré.
- B22 : groupe composé qui référence un groupe qui le contient (cycle).
- B23 : groupe manuel sans membre.

### 4.7 Scénarios et seuils

- B24 : scénario absent de la liste (Référence, Optimiste, Défavorable) ; un scénario supplémentaire doit être ajouté à Listes avant usage.
- B25 : hypothèse sans justification ou sans auteur.
- B26 : valeur absente ou non numérique.
- B27 : seuil absent, indicateur absent, seuil de fraîcheur sans ancienneté ou sans fréquence de source, ou seuil non numérique.

### 4.8 Rapports et envois

- B28 : section inconnue ou non disponible dans les gabarits.
- B29 : format non pris en charge pour ce gabarit.
- B30 : destinataire d'une adresse non valide (format), ou marqué « externe » sans périmètre de diffusion déclaré.
- B31 : envoi automatique (`oui`) sans approbation enregistrée : le rapport est chargé mais **inactif**. Ce n'est pas une erreur bloquante pour le reste de la configuration.

---

## 5. Contrôles de publication (bloquent une publication, pas le chargement)

Ces contrôles dépendent des données, pas seulement du classeur.

- P1 : compte mouvementé dans Pennylane sans rubrique ni exclusion explicite pour le dossier et la période. Le compte reste « non classé », la donnée ne peut pas être publiée comme validée.
- P2 : KPI dont une mesure source est absente pour la période demandée.
- P3 : période partielle (mois en cours, exercice non clos) affichée comme « clôturée ».
- P4 : ajustement de gestion dont l'écriture définitive est arrivée sans rapprochement.
- P5 : rapport dont la période n'est pas validée et dont la règle de blocage est « oui ».

---

## 6. Avertissements (non bloquants, affichés dans le rapport de chargement)

- W1 : KPI jamais utilisé dans un rapport ou un seuil.
- W2 : groupe dont un membre n'a pas de donnée sur les cinq dernières périodes.
- W3 : seuil d'ancienneté supérieur à 3 fois la période de la fréquence de la source (quotidienne : 1 jour ; hebdomadaire : 7 jours ; mensuelle : 31 jours). Le seuil est accepté mais jugé trop large pour détecter une donnée périmée.
- W4 : règle dont la date de fin est dans moins de 30 jours.
- W5 : valeur de scénario Optimiste ou Défavorable identique à la Référence.
- W7 : KPI au statut « brouillon » sans date d'effet.
- W6 : résidence rattachée à un dossier déclaré « à créer » dans Pennylane (non encore connu du logiciel). À retirer dès que le dossier existe.

---

## 7. Procédure de chargement

1. **Dépôt** : fichier `.xlsx` (ou export CSV par onglet) déposé par un utilisateur habilité (rôle « responsable de configuration », attribué par le porteur du projet ou Benjamin).
2. **Lecture** : copie du fichier source conservée telle quelle, avec son empreinte SHA-256.
3. **Validation** : contrôles 4 à 6. Résultat : `refusé` (au moins une erreur bloquante) ou `valide` (avertissements éventuels).
4. **Aperçu des impacts** : différences avec la version en vigueur (règles ajoutées, modifiées, archivées) ; KPI, rubriques, groupes et rapports impactés ; nombre de lignes de données dont le classement change ; liste des publications qui conservent leur ancienne version.
5. **Validation humaine** : un second utilisateur habilité approuve (les deux administrateurs de référence peuvent tous deux approuver). Le déposant ne peut pas approuver seul sa propre configuration.
6. **Application** : nouvelle version créée, horodatée, reliée à la version précédente. Les publications antérieures conservent leur version de configuration.
7. **Retour arrière** : possible à tout moment vers une version antérieure. Il ne modifie ni les données importées ni les saisies.

Le rapport de chargement est conservé avec la version. Il indique la date, l'auteur, l'empreinte du fichier, le nombre de lignes lues par onglet et la liste complète des erreurs et avertissements.

---

## 8. Ce que le classeur ne fait pas

- Il ne saisit pas les données comptables ou opérationnelles.
- Il ne contient pas de macro et n'exécute aucune formule Excel.
- Il ne crée pas de connexion vers Pennylane ou une autre source.
- Il ne définit pas de nouvel écran, de nouvelle source ou de nouvelle fonction de calcul : ces éléments relèvent du développement (voir tableau « Frontière entre configuration et code » du cadrage).

---

## 9. Points ouverts avant développement

0. **Colonnes différées** : destinataire externe, périmètre de diffusion et approbation des envois ne sont pas ajoutés au classeur pour l'instant (décision du 13 novembre 2026). Les contrôles B30 (partie externe) et B31 restent à implémenter à ce moment-là.

*Ajouté le 13 novembre 2026 : colonne « Fréquence de la source » dans l'onglet Seuils (quotidienne, hebdomadaire, mensuelle), obligatoire avec le seuil d'ancienneté (B27), et base du contrôle W3.*
1. **Catalogue des mesures** : les noms `LN_VENDUES`, `LN_DISPONIBLES`, `CA_HEBERGEMENT`, `CA_SERVICES`, `PL_CHARGES` utilisés dans les exemples n'existent pas encore dans la colonne Agrégat de base. Le catalogue doit être établi avec le contrôle de gestion, avec pour chaque mesure : code, unité, source, règle d'absence.
2. **Identifiants** : confirmer la règle `[A-Z0-9_-]` ; le `&` de `P&L` est exclu. Le modèle xlsx est corrigé en `PL_` (voir ci-dessous).
3. **Fonctions KPI** : valider la liste de 3.2 (cinq fonctions). Une fonction manquante ne se rajoute pas sans révision de ce document.
4. **Dossiers Pennylane** : *tranché le 13 novembre 2026* : un dossier non connu est refusé (B6) sauf s'il est déclaré « à créer », auquel cas la résidence est acceptée avec l'avertissement W6. Le cas d'un dossier fermé reste à traiter.
5. **Arrondis** : règle par défaut (2 décimales en interne, 0 pour les €) à confirmer par la DAF.
6. **Approbation** : confirmer que deux personnes doivent approuver une configuration, et que le déposant ne peut pas approuver seul.
7. **Seuils de fraîcheur** : *confirmés le 13 novembre 2026* : 45 jours pour la comptabilité, 2 jours pour les données d'exploitation.

---

## 10. Ce qui reste à décider par le développement

- Format de stockage interne de la configuration (base relationnelle normalisée recommandée, fichier source conservé à côté).
- Bibliothèque d'analyse des formules : écrire un analyseur simple pour la grammaire ci-dessus est plus sûr qu'une évaluation de type `eval`. Interdit : `eval`, `exec`, toute évaluation de texte fourni par l'utilisateur.
- Tests : un fichier de configuration de référence fictif, avec pour chaque contrôle B1 à B31 un cas qui doit échouer et un cas qui doit passer.


---

## 11. Décisions d'implémentation (lot 1, phase test)

- **Dossiers connus** (B6) : la liste vient du fichier `zenitude/config/dossiers_connus_test.txt` (données fictives). Elle sera remplacée par la liste issue du connecteur Pennylane.
- **Mesures** : le catalogue provisoire (`zenitude/config/formules.py`) contient les mesures des exemples. Il doit être validé par le contrôle de gestion (point 9.1).
- **Unités** : seules les additions et soustractions sont contrôlées. Un ratio ou une division prend une unité dérivée, déclarée dans la colonne Unité du KPI.
- **Références en cascade** : si un onglet est absent ou si un en-tête manque, les contrôles qui en dépendent ne sont pas exécutés, pour ne pas multiplier les constats.
- **Date de référence** : le contrôle W4 utilise le 13 novembre 2026 par défaut, paramétrable.

- **Aperçu des impacts** (lot 2) : comparaison par clé métier (Rubriques : code, dossier, préfixe, agrégat, date d'effet ; KPI : code et date d'effet ; etc.). Un changement de clé apparaît comme un retrait suivi d'un ajout. Un changement de statut vers « archivé » est signalé à part.

- **Versions** (lot 4) : une seule approbation distincte du déposant suffit pour appliquer. La spec §7 mentionne « un second utilisateur » ; la règle « deux approbateurs » n'est pas imposée et reste à trancher.
- **Publication** (lot 5) : compte de résultat calculé avec la version courante ; refusée si P1 échoue (compte non classé). Instantané figé et vérifiable.
