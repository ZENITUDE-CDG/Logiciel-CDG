# 0015 - Lot 21 : allègement des pages d'import, modèle Mixte

Date : 25 novembre 2026
Statut : approuvé par le porteur du projet (25 novembre 2026).

## Décisions

1. **Page d'arrivée** : après la connexion et le choix d'un groupe ou d'une résidence, on arrive toujours sur
   Import et paramètres, Import comptable (le retour après une synchronisation, lot 18c, est conservé).
2. **Historiques** (synchronisations, dépôts KPI, journal du catalogue) : les 5 dernières lignes, puis « Voir plus »
   pour tout afficher (et « Réduire »). Journal du catalogue lu jusqu'à 1 000 lignes.
3. **Données externes** : un seul chemin, le modèle Excel du catalogue (exporter, remplir, redéposer). Retirés :
   le modèle de saisie du lot 15 (Excel et CSV, `interface/generer_modele_import.py`,
   `modeles/Zenitude_Import_KPI_modele.xlsx`), le dépôt direct du consolidé KPI du lot 19 (rattachement par code
   Mews, groupes du fichier, statuts des mois), la grille « Mesures d'exploitation disponibles ». Un autre fichier
   déposé est refusé avec un message clair. Les tables du lot 19 (`kpi_mois`, `residences.code_mews`) restent en
   base, sans usage, et pourront être supprimées plus tard.
4. **Paramètres KPI** : nouveau modèle de suivi « Mixte (plusieurs activités) » (migration 013), ajouté à toutes
   les données et à tous les indicateurs suivis par Tourisme, Seniors ou Étudiants ; activité « Mixte » → modèle
   Mixte. L'ancienne configuration du moteur (classeur, « v1 ») n'est plus affichée ; la colonne du consolidé est
   masquée. Le classeur de configuration reste utilisé par le moteur (Synthèse, Indicateurs hôteliers, compte de
   résultat) tant que le catalogue ne le remplace pas.
