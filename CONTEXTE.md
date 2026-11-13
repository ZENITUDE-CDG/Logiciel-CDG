# Contexte pour reprise du projet

Ce fichier résume l'état du projet pour une nouvelle conversation ou un nouveau contributeur.
À lire avant CLAUDE.md.

## Où en est-on (13 novembre 2026)

- Phase : **test uniquement**. Données fictives. Pas de Pennylane, pas d'hébergement, pas d'envoi de mail.
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

Site (`index.html`, lot 7) : application de pilotage affichée par GitHub Pages, sur huit résidences fictives (`interface/demo/`). Charte graphique Zenitude appliquée (lot 8). L'ancienne maquette (`maquette/`) est remplacée.

## Décisions prises

- Pas de studio sans code : la configuration métier est un classeur Excel.
- Dossier Pennylane inconnu : refusé, sauf déclaré « à créer » (accepté avec avertissement W6).
- Seuils de fraîcheur : 45 jours (comptabilité), 2 jours (exploitation). Fréquence de la source obligatoire.
- Comptes : Plan comptable général officiel (libellés à vérifier contre l'extrait Pennylane).
- Une seule approbation distincte du déposant suffit pour appliquer une version (règle à confirmer).
- Une règle datée est une version : changer une date d'effet crée un retrait et un ajout.
- Phase test : le calcul des ajustements se fait dans la page (`docs/decisions/0002-calcul-ajustements-navigateur.md`), le moteur Python reste la référence et un test compare les deux.

## Points ouverts

1. Libellés PCG et sous-comptes réels : à remplacer par l'extrait Pennylane anonymisé.
2. Catalogue des mesures KPI (`LN_VENDUES`, `CA_HEBERGEMENT`, etc.) : à valider par le contrôle de gestion.
3. Colonnes différées : destinataire externe, périmètre de diffusion, approbation des envois (B30 partie externe, B31).
4. Cas non tranchés (`A_DEFINIR` dans `tests/attendus.csv`) : T-B30-b, T-B31-a, T-B31-b, T-W2.
5. Dossiers Pennylane fermés : procédure non définie.
6. Concurrence : un seul rédacteur à la fois, pas de verrou entre processus.
7. Authentification : rien n'identifie aujourd'hui les personnes qui déposent ou approuvent. Requis par la DSI avant tout usage réel.
8. Hébergement, plateforme Git, accès : décisions DSI.
9. Lot 5 limité : pas de PDF/PPTX, une publication par dossier et exercice.
11. Lot 6 : définitions des six KPI à valider par le contrôle de gestion (notamment RevPAC : CA hébergement + services / nuitées clients ; captage PDJ : couverts / nuitées clients). Source réelle des mesures d'exploitation (Mews, saisie) à décider. Groupes de l'onglet Groupes non encore utilisés par la vue groupe. Pas de publication figée des KPI.
12. Calculateur d'ajustements de la page (lot 9) : à remplacer par le backend en production, avec la même structure d'ajustement. Validation à deux personnes des ajustements et droits non définis.
10. Charte graphique : appliquée au lot 8. Présentation EBITDA à valider par le contrôle de gestion.

## Comment reprendre

```
pip install -r requirements.txt
python -m pytest            # 128 tests attendus (2 demandent Playwright)
sh demo.sh                  # démonstration complète
python interface/generer_site.py   # régénère index.html
```

## Fichiers à ne jamais committer

Données réelles de quelque nature que ce soit. Le dépôt ne contient que des données fictives
(`tests/fixtures/`, `config_modele/`). Les sorties `publications/`, `state.json` et les dossiers
de store sont exclus par `.gitignore`.
