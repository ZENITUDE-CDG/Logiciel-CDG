# Lot 25 - Socle de données et missions Claude (décision 0019)

Ajoute dans Rapports les pages « Paquet pour Claude » et « Missions Claude ». La base n'est PAS remise à zéro ;
aucune donnée existante n'est touchée.

## 1. GitHub : déposer les fichiers de l'archive
Glisser-déposer le contenu de l'archive dans le dépôt en gardant les dossiers (nouveaux dossiers
`zenitude/socle/` et `tests/lot25/`), puis **Commit changes**. Aucun fichier ne commence par un point.

Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes (la suite reconstruit sa propre base
de test avec la migration 016 ; 483 tests).

## 2. Supabase : migration 016
**SQL Editor, New query** : coller tout `migrations/016_socle_claude.sql`, **Run**. Résultat attendu : « Success. No
rows returned ». Elle crée `missions_claude`, `missions_versions` et `paquets_claude`. Elle peut être relancée sans
effet. (Ne pas utiliser `installation_supabase.sql`, qui remet tout à zéro.)

## 3. Créer les missions
**Rapports, Missions Claude, Nouvelle mission** (administrateurs) :
- **Code** stable en majuscules (exemple `NORMATIF-BUDGET`) et **catégorie** (Budget, Analyse, Négociation,
  Contrôle…) ;
- **Consignes** : la méthode et les hypothèses (taux, scénarios, règles de retraitement), sans aucun chiffre réel ;
- **Livrables** : les documents attendus, leurs noms de fichiers et leur plan type.
Le guide `docs/missions_claude.md` explique comment transformer un prompt existant en mission.

## 4. Utiliser
1. Choisir le périmètre (ruban : une résidence ou un groupe) et la période (réglette).
2. **Rapports, Paquet pour Claude** : niveau (complet ou synthèse), mission, **Télécharger le paquet**.
3. Ouvrir une conversation Claude, joindre le .zip, écrire « Exécute MISSION.md » (ou coller la mission avec
   **Copier le message pour Claude**), ajouter si besoin les pièces que le paquet ne contient pas (fichier de
   CA budgété, baux…).
4. Une fois le document produit, **Noter le document** sur la ligne du paquet (lien SharePoint ou nom du fichier).

## En cas de problème
- « Migration 016 non appliquée » ou missions vides en ligne : refaire l'étape 2, puis recharger la page.
- Le téléchargement s'arrête avec une erreur de droits : le paquet contient une résidence hors de votre parc.
- Paquet trop volumineux pour Claude : prendre le niveau synthèse ou réduire la période.
