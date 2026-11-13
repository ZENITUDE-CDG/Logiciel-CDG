# 0003 - Compte de résultat PCG et trésorerie (lot 11)

Date : 13 novembre 2026

## Contexte

Le tableau « Compte de résultat publié » ne donnait que quatre montants (CA hébergement, CA services, charges,
résultat). Le contrôle de gestion veut un compte de résultat conforme au Plan comptable général, et un onglet
Trésorerie du même type que celui de Waibi (analyse des créances et des dettes), adapté au logiciel.

## Décisions

1. **Référentiel : système de base, règlement ANC 2014-03 modifié par ANC 2022-06.** Ce règlement (homologué le
   26 décembre 2023) s'applique aux exercices ouverts à compter du 1er janvier 2025. Il supprime le « système
   développé » et les transferts de charges (comptes 791, 796, 797). Tous les exercices du jeu de démonstration
   (ouverts en octobre 2025 ou en janvier 2026) relèvent de ce modèle. Le modèle est l'article 821-2 ; le
   classement des comptes suit le tableau de passage indicatif (IR4) du même article.
2. **Le compte de résultat PCG est calculé par le moteur Python et figé dans la publication** (`compte_resultat`
   dans l'instantané, avec rapprochement sur le résultat du lot 5). La page l'affiche ; pour un cumul de
   résidences elle additionne des montants figés poste par poste, uniquement entre résidences de même exercice.
   Aucune formule comptable n'est recopiée dans le navigateur (invariant du CLAUDE.md).
3. **Un compte non classé dans le modèle bloque le compte de résultat PCG** (statut « bloqué », liste des
   comptes), comme P1 pour la publication du lot 5. La publication du lot 5 reste publiée.
4. **Exercice précédent (N-1) affiché « n.d. »**, jamais zéro : les écritures de N-1 ne sont pas importées
   (invariant 1). Le modèle ANC exige la colonne N-1 ; elle se remplira dès que N-1 sera importé.
5. **Trésorerie : agrégats par dossier et par arrêté calculés par le moteur** (`zenitude/comptes/tresorerie.py`),
   fournis à la page, qui les additionne sur le périmètre. Les ratios sont des ratios de sommes (invariant 4).
   Le seul calcul fait dans le navigateur est cette addition ; `tests/test_lot11.py` compare les chiffres
   affichés au moteur sur tout le groupe. Ce choix évite de recopier la logique de lettrage dans la page, ce
   que la décision 0002 a admis uniquement pour les ajustements.
6. **Trois colonnes facultatives dans les écritures : `tiers`, `lettrage`, `echeance`.** Sans aucun lettrage
   dans les écritures d'un dossier, créances et dettes sont « non calculables ». Une échéance absente en mode
   « échéance de la pièce » donne « échéance inconnue », jamais « non échu ». La disponibilité de ces colonnes
   dans l'extraction Pennylane réelle n'est pas vérifiée (point ouvert 13).
7. **Définitions explicites** (voir `docs/tresorerie.md`) plutôt que la reproduction des indicateurs de Waibi,
   dont les règles de calcul ne sont pas documentées. Les chiffres des captures sont cohérents entre eux (le
   taux de 4,92 % est bien 150,88 k€ sur 3,07 M€) ; seuls les pourcentages de -100 % de leur historique mensuel
   n'ont pas d'explication visible. Les définitions retenues ici sont vérifiables ligne à ligne.
8. **La trésorerie n'est pas concernée par les ajustements** (comptes simulés, provisions) : ils portent sur
   les comptes de classes 6 et 7. La bascule Réel / Ajusté est masquée sur ces pages.
9. **Jeu de démonstration étendu** : tiers, lettrage, échéances, règlements bancaires fictifs jusqu'au
   31 octobre 2026, à-nouveaux, un acompte non affecté et un dossier sans échéance exportée. Un générateur
   aléatoire distinct est utilisé : les écritures de classes 6 et 7, les mesures et la configuration sont
   identiques à celles du lot 10.

## À faire valider

| Sujet | Qui |
| --- | --- |
| Rattachements : 708 et 709 sans subdivision (production vendue), 608 (achats de marchandises), 648 et 649 (cotisations sociales), 6094 à 6098 (autres achats et charges externes) | Direction financière |
| Comptes laissés non classés : 643, 644, 646, 681 sans subdivision, 697, 768 (absents du tableau de passage) | Direction financière |
| Règlement ANC 2026-03 (Journal officiel), qui réorganise le titre V du PCG : il n'a pas été analysé, à confirmer qu'il ne change ni le modèle ni le classement | Direction financière |
| Colonnes tiers, lettrage, échéance dans l'extraction Pennylane | DSI et contrôle de gestion |

## Approbations

| Instance | Statut |
| --- | --- |
| Porteur du projet | Demande du 13 novembre 2026 |
| Contrôle de gestion | À tracer |
| DAF | À tracer |
| DSI | À tracer |
