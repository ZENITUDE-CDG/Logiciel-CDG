# Analyse des écarts : règles (lots 28 à 30)

Référence : `zenitude/analyse/ecarts.py` ; page : `anCalculer` dans `interface/gabarit.html` ; décision 0022.

## Principes

- Montants en centimes, sens naturel (produits et charges positifs, comme le tableau EBITDA).
- Postes = lignes du tableau EBITDA du modèle de gestion du groupe (`LIGNES_EBITDA`).
- Référence : `n1` (mêmes mois un an plus tôt), `prec` (mois qui précèdent, en même nombre), `moy12` (12 mois avant
  la période × nombre de mois ÷ 12, arrondi par ligne de base avant les totaux).
- Résidence retenue : comptabilité couvrant tous les mois de la période et de la référence. Sinon : « hors des
  écarts » (motif période ou référence). Les blocs anomalies (A1 à A7) et fournisseurs F4, F5 regardent chaque
  résidence, même hors des écarts.
- Effet sur l'EBITDA : produit = écart ; charge = − écart. Priorité = effet en valeur absolue décroissante.
- Seuils (Seuils et références) : `pct`, `montant` (centimes), `sigma`, `ecriture`, `coherence`, `rapprochement`,
  `etalement`, `historique`.

## Écarts repérés

| Code | Écart | Règle |
| --- | --- | --- |
| N1 | Poste en écart | Ligne de base du tableau EBITDA : écart ≥ montant ET (référence nulle OU écart ≥ pct). Effet activité (charges variables, sous « Total charges variables ») = référence × (nuitées vendues période ÷ nuitées référence − 1). |
| V1 | CA hébergement : volume et prix | Écart du CA hébergement au-delà des seuils. Effet volume = (N période − N référence) × CA réf ÷ N réf ; effet prix = écart − volume ; volume = capacité ((K pér − K réf) × TO réf × prix réf) + occupation. Annexes et restauration : effet volume (nuitées) et effet panier. |
| F1 | Nouveau fournisseur | Tiers (ligne 40 de la pièce) sans pièce dans la référence, charges (lignes 6) ≥ montant. |
| F2 | Fournisseur disparu | Tiers sans pièce sur la période, référence ≥ montant. |
| F3 | Fournisseur en forte variation | Écart ≥ montant et ≥ pct. |
| F4 | Facture en double possible | Règle du contrôle C05 : deux pièces différentes, même tiers, même montant (ligne 40 au crédit), 5 jours d'écart au plus, la seconde dans la période. Sans seuil de montant. |
| F5 | Fournisseur récurrent sans facture | Règle du contrôle C04 sur les mois couverts de la période (3 au moins) ; montant habituel (médiane) ≥ montant ÷ 10. |
| A1 | Poste hors de sa tendance | Mois de la période contre les 12 mois précédents couverts (au moins `historique`) : |valeur − moyenne| ≥ montant ET > sigma × écart-type (population). |
| A2 | Écriture inhabituelle | Écriture 6 ou 7 de la période, |montant| ≥ montant et > `ecriture` × médiane des |montants| du compte sur les 12 mois précédents (3 écritures au moins). |
| A3 | Compte nouveau | Compte 6 ou 7 mouvementé sur la période, aucune écriture sur les 12 mois précédents (au moins `historique` couverts), total ≥ montant. |
| A4 | Charge à étaler | Écriture au débit d'un compte 616, 635, 614, 6156 ou 6281 ≥ montant et ≥ `etalement` du total du compte sur les 12 mois finissant à son mois. Effet = − (montant − montant ÷ 12). |
| A5 | Mois sans comptabilité | Mois de la période non couvert. |
| A6 | Mois sans chiffre d'affaires | Règle C02. |
| A7 | Mois sans paie | Règle C03 (641 présent sur la période ou les 12 mois précédents). |
| K1 | Ratio compta / activité | Ratios du tableau ci-dessous : |ratio pér ÷ ratio réf − 1| ≥ `coherence` ET |effet| ≥ montant ; effet = (ratio pér − ratio réf) × base de la période (signe : charge −, produit +). |
| R1 | CA comptable / CA Mews | Par mois : |compta − Mews| ≥ montant ÷ 10 ET > `rapprochement` × Mews. CA total / CA_MEWS_TOTAL ; CA restauration / CA_MEWS_RESTO + CA_MEWS_PDJ. |
| B1 | Poste au-dessus des comparables | Base « % du CA », ligne de base : ratio > médiane × (1 + pct) des résidences de même activité (3 au moins, sinon tout le périmètre), potentiel = (ratio − médiane) × CA ≥ montant. |
| S1 | Brut DSN / 641 | Par mois : |brut − 641| ≥ montant ÷ 10 ET > `rapprochement` × 641. Page seulement. |
| S2 | Masse salariale : effectif et coût moyen | Charges 64 sur les mois où ETP et charges existent : écart ramené à la durée de la période ; effet effectif = (ETP moyen pér − réf) × coût mensuel par ETP réf × mois ; effet coût = écart − effet effectif. Page seulement. |
| S3 | Intérim sans hausse des arrêts | Intérim (MEN_INT, INT_HB, REST_INT) en hausse ≥ montant et ≥ pct, absentéisme en hausse de moins d'un point. Page seulement. |
| S4 | Coût horaire | Charges 64 ÷ heures rémunérées : variation ≥ `coherence` et effet ≥ montant. Page seulement. |

## Ratios compta / activité (K1)

| Code | Ratio | Numérateur | Base |
| --- | --- | --- | --- |
| K_PRIX | Prix moyen comptable par nuitée | CA_HEB | LN_VENDUES |
| K_COMM | Commissions / CA hébergement | COMM | CA_HEB |
| K_MEN | Ménage par nuitée | MEN | LN_VENDUES |
| K_BLANCH | Blanchissage par nuitée | BLANCH | LN_VENDUES |
| K_ACCUEIL | Produits d'accueil par client | PROD_ACC | NUITEES_CLIENTS |
| K_PDJ | Achats restauration par petit-déjeuner | ACH_REST | COUVERTS_PDJ |
| K_FOOD | Coût matière / CA restauration | ACH_REST | CA_REST |
| K_ENERGIE | Énergie par logement-nuit disponible | ENERGIE | LN_DISPONIBLES |
| K_PERS | Frais de personnel / CA | PERS_HB + MEN + CF_REST | CA |

## Comparaison des résidences

Bases : % du CA, par nuitée vendue, par logement-nuit disponible. Lignes : descendants de « Total charges variables »,
« Total charges fixes », « Frais de siège » et « Loyers propriétaires ». Comparables : même activité (3 au moins),
sinon tout le périmètre. Rang 1 = coût le plus bas. Potentiel = (ratio − médiane) × base, si au-dessus.
