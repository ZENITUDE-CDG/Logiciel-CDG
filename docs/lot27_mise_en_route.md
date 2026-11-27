# Lot 27 - Détail des salaires et indicateurs de pilotage (décision 0021)

Ajoute dans Social : **Rémunérations**, **Productivité**, **Contrôles de paie**, **Base budget**, et dans Import et
paramètres : **Référentiel des postes**. Réservé aux administrateurs. La base n'est PAS remise à zéro.

## 1. GitHub
Déposer le contenu de l'archive en gardant les dossiers (nouveau dossier `tests/lot27/`), puis **Commit changes**.
Vérifier les deux coches vertes dans Actions.

## 2. Supabase : migration 018
Si la migration 017 (lot 26) n'est pas encore passée, la coller d'abord. Puis **SQL Editor** : coller tout
`migrations/018_dsn_detail_salaries.sql`, **Run** (« Success. No rows returned »). Rejouable.

## 3. Réimporter les DSN
Les DSN importées avant ce lot n'ont pas le détail par salarié (message en haut des pages) : les redéposer dans
**Import DSN** (statut « Remplace l'import précédent »). Les nouvelles DSN fictives de `interface/demo/dsn/` ont des
postes, niveaux et salaires réalistes, et des anomalies volontaires :
- Le Clos Fleuri : un salarié payé sous le SMIC tous les mois ;
- Les Terrasses du Port : un salaire de base en baisse de 35 % en juillet 2026 puis rétabli en août ;
- des CDD de plus de 18 mois.

## 4. Référentiel des postes
**Import et paramètres, Référentiel des postes** : vérifier que chaque libellé de la paie est rattaché au bon poste
et à la bonne famille (les variantes « Réceptionniste H/F », accents… sont regroupées automatiquement), corriger
au besoin et **Enregistrer**.

## 5. Avant un fichier réel
Validation DSI, DAF et référent RGPD (données pseudonymisées de salariés). Vérifier sur un premier fichier Silae
la rubrique du niveau (S21.G00.40.041) et les libellés d'emploi.
