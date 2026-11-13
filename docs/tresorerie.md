# Trésorerie : définitions (lot 11)

Code : `zenitude/comptes/tresorerie.py`. Page : section « Trésorerie » (position, créances, dettes).

## Données d'entrée

Écritures (`ecritures.csv`) avec trois colonnes facultatives :

| Colonne | Contenu |
| --- | --- |
| `tiers` | compte auxiliaire (client ou fournisseur) |
| `lettrage` | code de lettrage ; vide = non lettré |
| `echeance` | échéance de la pièce, `AAAA-MM-JJ` ; vide = non exportée |

Sans aucun lettrage dans les écritures d'un dossier, les créances et dettes de ce dossier sont **non
calculables**. La position de trésorerie ne dépend pas de ces colonnes.

## Arrêté et période

La réglette de période fixe la période. L'**arrêté** est le dernier jour du dernier mois de la période,
plafonné au dernier mois importé. Les flux (facturé, encaissé, encaissements, décaissements) portent sur la
période ; les stocks (ouvert, échu, non échu, solde de trésorerie) portent sur toutes les pièces jusqu'à
l'arrêté.

## Position de trésorerie

- Solde = débit moins crédit des comptes **51 et 53** jusqu'à l'arrêté (banques, caisse, nets des concours
  bancaires courants 519). Placements (50) exclus.
- Encaissements et décaissements = débits et crédits de ces comptes, hors journal d'à-nouveaux (AN).
- Créances et dettes ouvertes : voir ci-dessous.

## Créances et dettes

| | Créances clients | Dettes fournisseurs |
| --- | --- | --- |
| Comptes | 411, 413, 416, 418 | 401, 403 |
| Pièce | ligne au débit | ligne au crédit |
| Règlement | ligne au crédit, même tiers, même lettrage | ligne au débit, même tiers, même lettrage |

- **Pièce soldée à l'arrêté** : son groupe de lettrage (tiers + code) est équilibré et son dernier mouvement est
  daté au plus de l'arrêté. Sinon elle est **ouverte** pour son montant total (un lettrage partiel laisse la
  pièce ouverte).
- **Facturé** = pièces de la période, hors à-nouveaux. **Encaissé / réglé** = celles soldées à l'arrêté.
  **Taux de recouvrement / d'apurement** = somme des soldées sur somme des facturées (ratio de sommes ; non
  calculable si rien n'est facturé).
- **Ouvert** = toutes les pièces non soldées datées jusqu'à l'arrêté, y compris avant la période et les
  à-nouveaux (suivis à part : « dont à-nouveaux », datés de l'ouverture de l'exercice).
- **Échéance** au choix : date de la pièce + 30, 45 ou 60 jours, ou échéance de la pièce. En mode « pièce »,
  une pièce sans échéance est classée « échéance inconnue », jamais « non échu ».
- **Échu** si l'échéance est antérieure à l'arrêté. Retards : 1 à 30 jours, 31 à 60, 61 à 90, plus de 90.
- **Lignes de sens inverse non lettrées** (avoirs, acomptes, règlements à affecter) : montrées à part, non
  déduites de l'ouvert.

## Limites connues

- Lettrage partiel : les règlements partiels ne sont pas déduits (approche prudente).
- La date de règlement est celle du dernier mouvement du groupe de lettrage (pas de date de lettrage).
- Pas de prévision : un échéancier d'encaissements et de décaissements attendus relèverait du module Budgets.
- Les autres dettes (sociales, fiscales, emprunts) et les créances hors clients ne sont pas analysées.
- Données de démonstration fictives : les règlements, les impayés et les à-nouveaux sont générés.
