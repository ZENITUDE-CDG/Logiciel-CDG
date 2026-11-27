# DSN : règles de lecture et indicateurs (lot 26)

Référence : `zenitude/social/dsn.py` (la page applique exactement les mêmes règles). Décision 0020.
Les codes ci-dessous suivent la norme NEODeS ; **à confirmer sur le premier fichier exporté de Silae**.

## Fichier
- Une ligne = `RUBRIQUE,'valeur'`. Encodage UTF-8 ou ISO-8859-1. Un envoi peut contenir plusieurs déclarations
  (une par bloc S20.G00.05).
- Déclaration lue : nature 01 (mensuelle), types 01, 02 (néant), 03 et 05 (annule et remplace), non fractionnée.
- SIRET = SIREN (S21.G00.06.001) + NIC (S21.G00.11.001). Mois = S20.G00.05.005.
- Le total S90 (nombre de rubriques et de déclarations) est vérifié : un écart donne un avertissement.

## Salariés et contrats
- Contrat (S21.G00.40) : début .001, statut catégoriel .003 (01, 02 = cadre), nature .007, dispositif .008,
  quotité de référence .012, quotité du contrat .013. Fin de contrat (S21.G00.62) : date .001, motif .002.
- Exclus de l'effectif : convention de stage (nature 29, comptée à part) et mandataire social (80).
- Catégorie : alternance si dispositif 61, 64 ou 65 ; CDI si nature 01 ou 07 ; CDD si 02, 08, 09 ou 10 ; sinon autre.
- **Effectif fin de mois** : salariés ayant au moins un contrat en cours le dernier jour du mois (fin absente ou
  postérieure ou égale). Un salarié compte une fois, dans la catégorie de son contrat en cours le plus ancien.
- **ETP** : par salarié présent, somme des quotité ÷ quotité de référence de ses contrats en cours, arrondie au
  millième, plafonnée à 1. Une quotité absente rend l'ETP du mois non calculable (alerte).
- **Entrées** : contrat commencé dans le mois, sans autre contrat plus ancien du même salarié dans la DSN.
- **Sorties** : salarié sans contrat en cours en fin de mois dont un contrat s'est terminé dans le mois. Motifs :
  059 démission ; 043 rupture conventionnelle ; 011 à 026 licenciement ; 031, 032 fin de CDD ou de mission ;
  034, 035 fin de période d'essai ; 038, 039 retraite ; autres codes : autre.
- Âge et ancienneté au dernier jour du mois (ancienneté depuis le plus ancien contrat déclaré).

## Rémunérations
- Brut : S21.G00.51.013 pour le type 001 (rémunération brute non plafonnée).
- Heures rémunérées : S21.G00.51.012 pour le type 002. Heures supplémentaires : types 017 et 018 (heures et montant).
- Net versé : S21.G00.50.004. Prélèvement à la source : S21.G00.50.009. Primes : S21.G00.52.002.
- Versements aux organismes : S21.G00.20.005 (informatif).

## Arrêts de travail (S21.G00.60)
- Motif .001 : 01 maladie ; 04, 05, 06 accident de trajet, maladie professionnelle, accident du travail ; 02, 03
  maternité, paternité ; autres codes : autre. Dernier jour travaillé .002, fin prévisionnelle .003, reprise .010.
- L'arrêt commence le lendemain du dernier jour travaillé. Ses déclarations successives sont reliées par une clé
  anonyme (SIRET, dernier jour travaillé, motif, date de naissance et sexe, passés dans SHA-256 puis tronqués).
- Fin : veille de la reprise si elle est connue, sinon fin prévisionnelle, sinon fin du dernier mois importé.
- Taux d'absentéisme = jours calendaires d'arrêt ÷ (effectif fin de mois × jours du mois).

## Croisements
- Rapprochement : brut DSN ↔ débit − crédit des comptes 641 (règle `DSN_REGLE_BRUT`). Écart toléré : 1 % ou 1 €.
- Charges de personnel : comptes 64 (règle `DSN_REGLE_CHARGES`). Charges / CA, coût mensuel par ETP, charges par
  nuitée vendue (LN_VENDUES).
- Turnover = ((entrées + sorties) ÷ 2) ÷ effectif moyen de la période.

## Détail par salarié (lot 27, décision 0021)
- Une ligne par individu ayant un contrat hors stage et mandat : `id` (SHA-256 de « SAL|SIREN|N:NIR », à défaut
  « M:matricule », tronqué à 12 caractères), `emploi` (S21.G00.40.006, espaces réduits, majuscules), `pcs` (.004),
  `statut` (.002), `niveau` (.041), `idcc` (.017), `cadre` (.003 = 01 ou 02), `contrat`, `sexe`, `age`, `anc_mois`
  (depuis le plus ancien contrat déclaré), `present`, `complet` (contrat en cours du premier au dernier jour),
  `entree`, `sortie` (motif), `etp_milli`, `brut`, `heures`, `hs_heures`, `hs_montant`, `primes`, `net`.
- Contrat de référence : contrat en cours le plus ancien ; à défaut, le dernier terminé ; à défaut, le plus ancien.
- Arrêts : la clé de l'arrêt porte en plus l'identifiant du salarié (`sal`).

## Indicateurs du lot 27
- Salaire brut temps plein d'un groupe = Σ brut ÷ Σ ETP (salariés présents tout le mois, ETP connu, brut > 0).
  Part fixe = brut − heures supplémentaires − primes. Taux horaire = (brut − heures sup.) ÷ heures rémunérées.
  Minimum, médiane, maximum : sur les salaires moyens individuels de la période.
- Coût employeur = brut × (1 + comptes 645 et 647 ÷ comptes 641) de la résidence et du mois.
- Productivité (par résidence et total) : CA, EBITDA, valeur ajoutée et comptes 64 par ETP (annualisés × 12),
  charges de personnel / CA et / VA, nuitées par ETP, heures payées par nuitée, CA par heure payée.
- Contrôles de paie : taux horaire hors heures sup. et primes sous le SMIC du mois (alternants exclus, tolérance
  0,5 %) ; variation du salaire de base temps plein de plus de 25 % d'un mois sur l'autre ; plus de 20 h
  supplémentaires ; CDD depuis 18 mois ou plus ; quotité sous 24 h par semaine ; contrat en cours sans brut ni net ;
  arrêt de plus de 90 jours en cours.
- Base budget : par résidence et par poste, effectif et ETP fin de période, base mensuelle par ETP, variables
  mensuels par ETP, taux de charges réel, coût mensuel et annuel chargé.
