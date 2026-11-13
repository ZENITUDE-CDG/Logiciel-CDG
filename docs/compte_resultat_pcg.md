# Compte de résultat PCG (lot 11)

Code : `zenitude/comptes/pcg.py`. Modèle : article 821-2 du règlement ANC 2014-03 modifié par ANC 2022-06,
**système de base**, présentation en liste. Applicable aux exercices ouverts à compter du 1er janvier 2025 :
le système développé n'existe plus, les transferts de charges (791, 796, 797) sont supprimés.

## Règles

1. Un compte de classe 6 ou 7 tombe dans **un seul poste**, celui de son **préfixe le plus long** (invariant 3).
2. Un compte qu'aucun préfixe ne couvre est **non classé** : le compte de résultat est **bloqué** et rien n'est
   affiché (invariant 7), avec la liste des comptes.
3. Produit = crédit - débit ; charge = débit - crédit. Les comptes à solde inverse (7097, 609x, 619, 629, 6989,
   699, variations de stocks) viennent en déduction du poste auquel ils se rattachent.
4. Aucune écriture de classe 6 ou 7 sur l'exercice : « non calculable », pas zéro (invariant 1).
5. Exercice court conservé tel quel, sans annualisation. Exercices décalés jamais additionnés.
6. Exercice N-1 : « n.d. » tant que les écritures de N-1 ne sont pas importées.
7. Rapprochement : le résultat PCG est comparé au résultat de la publication du lot 5. Un écart signale des
   produits hors chiffre d'affaires (74, 75, 76, 77...) que la publication du lot 5 ne reprend pas.
8. Les postes sans montant sont masqués par défaut (le règlement le permet quand ils sont à zéro deux exercices
   de suite ; comme N-1 est inconnu, la page propose « Tous les postes du modèle »).

## Postes et comptes

| Poste | Comptes |
| --- | --- |
| Ventes de marchandises | 707, 7097 |
| Production vendue | 701 à 706, 708, 709, 7091, 7092, 7094 à 7096, 7098 |
| Production stockée / immobilisée | 71 / 72 |
| Subventions | 74 |
| Reprises sur amortissements, dépréciations et provisions | 781 |
| Produits des cessions d'immobilisations incorporelles et corporelles | 757 |
| Autres produits | 75 (hors 755 et 757) |
| Achats de marchandises | 607, 608, 6097 |
| Variation de stocks (marchandises) | 6037 |
| Achats de matières premières et autres approvisionnements | 601, 602, 6091, 6092 |
| Variation de stocks (matières premières) | 6031, 6032 |
| Autres achats et charges externes | 604 à 606, 61, 62, 6094 à 6096, 6098 |
| Impôts, taxes et versements assimilés | 63 |
| Salaires | 641 |
| Cotisations sociales | 645, 647, 648, 649 |
| Dotations aux amortissements (immobilisations) | 6811 |
| Dotations aux dépréciations (immobilisations / actif circulant) | 6816 / 6817 |
| Dotations aux provisions | 6815 |
| Valeurs comptables des immobilisations cédées | 657 |
| Autres charges | 65 (hors 655 et 657) |
| Quote-part sur opérations faites en commun | 755 (III), 655 (IV) |
| Produits financiers | 761, 762, 764, 763, 765, 786, 766, 7671 à 7674 |
| Charges financières | 686, 661, 664, 665, 666, 6671 à 6674 |
| Produits / charges exceptionnels | 77 et 787 / 67 et 687 |
| Participation des salariés | 691 |
| Impôts sur les bénéfices | 695, 696, 6981, 6989, 699 |
| Mémos (compris dans les autres achats et charges externes) | 6122 (crédit-bail mobilier), 6125 (crédit-bail immobilier) |

Totaux : I produits d'exploitation, II charges d'exploitation, résultat d'exploitation, III et IV quote-part,
V produits financiers, VI charges financières, résultat financier, résultat courant avant impôts
(I - II + III - IV + V - VI), VII et VIII exceptionnels, résultat exceptionnel, IX participation, X impôts,
total des produits (I + III + V + VII), total des charges (II + IV + VI + VIII + IX + X), bénéfice ou perte.

## À valider par la direction financière

Le règlement impose de rattacher les subdivisions de 608, 609, 648, 649 et 708 au poste auquel elles se
rapportent, ce que le seul numéro de compte ne permet pas toujours. Choix provisoires : 708 et 709 sans
subdivision en production vendue ; 608 en achats de marchandises ; 648 et 649 en cotisations sociales.
Restent non classés (absents du tableau de passage) : 643, 644, 646, 681 sans subdivision, 697, 768.
Le compte 67 est classé en charges exceptionnelles par numéro de compte ; depuis ANC 2022-06, le résultat
exceptionnel ne retient que les événements majeurs et inhabituels et les écritures d'origine fiscale : la
qualification relève de la comptabilité, pas du logiciel.
Le règlement ANC 2026-03 (Journal officiel), qui réorganise le titre V du PCG, n'a pas été analysé.
