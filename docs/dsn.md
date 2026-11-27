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
