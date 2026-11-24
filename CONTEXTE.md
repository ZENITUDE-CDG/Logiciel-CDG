# Contexte pour reprise du projet

Ce fichier résume l'état du projet pour une nouvelle conversation ou un nouveau contributeur.
À lire avant CLAUDE.md.

## Où en est-on (23 novembre 2026)

- Phase : **test uniquement**. Données fictives. Pennylane : seul le dossier de test `PENNY-TEST` est lu, en lecture seule (lot 18, décision 0011). Pas d'envoi de mail. Site GitHub Pages et base de test Supabase (décisions 0004, 0006, 0007) ; rien en local. Les chiffres sont calculés par GitHub Actions et publiés dans la base ; la page en ligne ne contient aucune donnée.
- Cadrage : ZENITUDE v0.8 approuvé pour la phase test (`docs/decisions/0001-approbation-cadrage-test.md`).
  Approbations DAF, contrôle de gestion et DSI : **non tracées**.
- Équipe : deux personnes (porteur du projet et Benjamin), développement avec Claude Code.

## Ce qui est fait

| Lot | Contenu | Tests |
| --- | --- | --- |
| 1 | Chargeur et validateur du classeur de configuration (contrôles B1 à B31, W1 à W7) | 70 cas |
| 2 | Rapport de chargement (Markdown, JSON) et aperçu des impacts entre versions | 9 |
| 3 | Référentiel PCG, écritures synthétiques équilibrées, contrôle P1 (comptes non classés) | 9 |
| 4 | Dépôt, approbation, application, retour arrière de version, journal | 11 |
| 5 | Compte de résultat par dossier et exercice, instantané figé, P1 bloquant | 7 |
| 6 | Moteur de KPI (TO, prix moyen, RevPAR, RevPAC, DMS, captage PDJ) et vue groupe | 15 |
| 7 | Site de démonstration (`index.html`, GitHub Pages) calculé par le moteur réel | 5 |
| 8 | Charte Zenitude, connexion, choix du périmètre, tableau EBITDA, onglet Import et paramètres | - |
| 9 | Thème clair / sombre / auto, réglette de période libre, ajustements (comptes simulés, provisions), vue Réel / Ajusté | 2 (navigateur) |
| 10 | Menu latéral réductible (remplace les barres du haut), page Résidence (fiche complète) | - |
| 12 | Utilisateurs, rôles (administrateur, collaborateur, lecture seule), parcs (résidences et groupes), droits vérifiés dans la base, vraie connexion, écran d'administration | 20 (base PostgreSQL, GitHub Actions) |
| 11 | Compte de résultat PCG (système de base, ANC 2022-06) figé dans la publication ; section Trésorerie (position, créances, dettes) ; colonnes tiers, lettrage, échéance | 110 |
| 15 | Comptes bancaires par résidence (trésorier) et analyse du solde N / N-1 ; FRNG, BFR, TN ; graphiques liés à la réglette ; tableau EBITDA du modèle de gestion du groupe ; import des KPI mensuels (modèle Excel, tout ou rien) | 21 |
| 14 | Clic sur tout montant : formule, éléments et écritures d’origine (rapprochés avec le moteur) ; lissage de postes écriture par écriture comme Waibi (exercice suivant compris) ; compte ouvert par l’adresse en bas à gauche ; logo vers le choix des résidences depuis toute page | 18 |
| 18a | Connecteur Pennylane (lecture seule) sur le dossier de test : écritures publiées comme résidence RES-TEST, visible des administrateurs ; synchronisation manuelle avec choix du mode (validées / validées et brouillard) | 17 |
| 18b | Synchronisation lancée depuis la page Import comptable (résidence ou groupe), période d'import, masquage du brouillard, historique | 17 |
| 13 | Chiffres publiés dans la base par GitHub Actions et lus selon le parc (compte de résultat, tableaux de bord, trésorerie) ; ajustements et comptes simulés partagés dans la base, actifs dès leur création ; lissage ; nettoyage des résidences de test (huit résidences de démonstration) | 39 |

Site (`index.html`, lot 7) : application de pilotage affichée par GitHub Pages, sur huit résidences fictives (`interface/demo/`). Charte graphique Zenitude appliquée (lot 8). Depuis le lot 12, on y entre par `connexion.html` (vraie connexion, base de test Supabase).

## Décisions prises

- Pas de studio sans code : la configuration métier est un classeur Excel.
- Dossier Pennylane inconnu : refusé, sauf déclaré « à créer » (accepté avec avertissement W6).
- Seuils de fraîcheur : 45 jours (comptabilité), 2 jours (exploitation). Fréquence de la source obligatoire.
- Comptes : Plan comptable général officiel (libellés à vérifier contre l'extrait Pennylane).
- Une seule approbation distincte du déposant suffit pour appliquer une version (règle à confirmer).
- Une règle datée est une version : changer une date d'effet crée un retrait et un ajout.
- Lot 12 : Supabase comme base de test, droits par règles par ligne dans PostgreSQL, SQL standard migrable (`docs/decisions/0004`, `0005`, `0006`). Identité par l'adresse e-mail du jeton ; comptes créés dans Supabase par un administrateur ; clé publique visible dans `app/config.js`.
- Phase test : le calcul des ajustements se fait dans la page (`docs/decisions/0002-calcul-ajustements-navigateur.md`), le moteur Python reste la référence et un test compare les deux.
- Lot 15 (`docs/decisions/0009`) : virements internes exclus des flux ; vue bancaire réservée aux administrateurs ; import des KPI réservé aux administrateurs, tout ou rien ; EBITDA au format du groupe (structure seulement du fichier réel fourni, aucun montant).
- Lot 17 (`docs/decisions/0010`) : menu latéral réordonné (Résidence en haut) ; export Excel de chaque page de données : tableaux, données des graphiques, détail des calculs et écritures comptables.
- Lot 16 : ruban bleu en haut de chaque page (exercice de référence + résidence ou groupe) ; l'exercice fixe la période de la réglette, le périmètre quitte le menu latéral.
- Lot 14 (`docs/decisions/0008`) : détail des écritures publié par résidence ; lissage comme Waibi (répartition possible sur l'exercice suivant, mois sans écriture compris).
- Lot 18b (`docs/decisions/0012`) : fonction serveur Supabase `lancer-synchro` (jeton GitHub limité aux Actions du dépôt, dans les secrets Supabase) ; tables `parametres_import` et `synchronisations`.
- Lot 18 (`docs/decisions/0011`) : connexion Pennylane autorisée pour le seul dossier de test, lecture seule, liste blanche ; classement provisoire des comptes non classés du dossier de test ; aucune valeur dans les journaux.
- Lot 13 (`docs/decisions/0007`) : publication par GitHub Actions avec la clé secrète dans les secrets GitHub ; ajustements partagés, actifs dès leur création, sans validation à deux personnes ; lissage ; base de test = huit résidences de démonstration (Benjamin : groupe GRP-SENIORS).

## Points ouverts

1. Libellés PCG et sous-comptes réels : à remplacer par l'extrait Pennylane anonymisé.
2. Catalogue des mesures KPI (`LN_VENDUES`, `CA_HEBERGEMENT`, etc.) : à valider par le contrôle de gestion.
3. Colonnes différées : destinataire externe, périmètre de diffusion, approbation des envois (B30 partie externe, B31).
4. Cas non tranchés (`A_DEFINIR` dans `tests/attendus.csv`) : T-B30-b, T-B31-a, T-B31-b, T-W2.
5. Dossiers Pennylane fermés : procédure non définie.
6. Concurrence : un seul rédacteur à la fois, pas de verrou entre processus.
7. Authentification : connexion provisoire par e-mail en place (lot 12). Reste : Microsoft 365, rattacher les dépôts et approbations de configuration à la personne connectée, mot de passe oublié. Requis par la DSI avant tout usage réel.
8. Hébergement définitif, plateforme Git, dépôt public, accès : décisions DSI. Phase test : GitHub Pages et Supabase (décision 0006).
15. Lot 12 : filtrage du tableau de bord par parc, réalisé au lot 13.
9. Lot 5 limité : pas de PDF/PPTX, une publication par dossier et exercice.
11. Lot 6 : définitions des six KPI à valider par le contrôle de gestion (notamment RevPAC : CA hébergement + services / nuitées clients ; captage PDJ : couverts / nuitées clients). Source réelle des mesures d'exploitation (Mews, saisie) à décider. Groupes de l'onglet Groupes non encore utilisés par la vue groupe. Pas de publication figée des KPI.
12. Calculateur d'ajustements de la page (lot 9) : à remplacer par le backend en production, avec la même structure d'ajustement. Validation à deux personnes des ajustements et droits non définis.
13. Lot 11 : colonnes `tiers`, `lettrage`, `echeance` à confirmer dans l'extraction Pennylane réelle (sans lettrage, créances et dettes sont non calculables).
14. Lot 11 : rattachements PCG provisoires (708, 709, 608, 648, 649) et comptes non classés (643, 644, 646, 681 sans subdivision, 697, 768) à valider par la direction financière ; règlement ANC 2026-03 (titre V du PCG) à analyser ; exercice N-1 à importer pour remplir la colonne N-1.
10. Charte graphique : appliquée au lot 8. Présentation EBITDA à valider par le contrôle de gestion.

## Comment reprendre

```
pip install -r requirements.txt
python -m pytest            # 336 tests (les tests de page demandent Playwright, ceux des lots 12 et 13 sur la base une base PostgreSQL)
                            # sur GitHub : onglet Actions, lancé automatiquement à chaque dépôt
sh demo.sh                  # démonstration complète
python interface/generer_site.py   # régénère index.html (en ligne, sans données)
python interface/generer_site.py demo.html   # démonstration complète à ouvrir en local
```

## Fichiers à ne jamais committer

Données réelles de quelque nature que ce soit. Le dépôt ne contient que des données fictives
(`tests/fixtures/`, `config_modele/`). Les sorties `publications/`, `state.json` et les dossiers
de store sont exclus par `.gitignore`. Le fichier `.env` (secrets) aussi. Aucune clé secrète Supabase ni
mot de passe de base dans le dépôt : seule la clé publique figure dans `app/config.js` (décision 0006).
