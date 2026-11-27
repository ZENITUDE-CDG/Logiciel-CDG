# Écrire une mission Claude (lot 25, décision 0019)

Une mission décrit un document standard. Elle ne contient **aucun chiffre réel** : ils viennent du paquet. Elle
sert telle quelle pour une résidence ou pour tout un groupe.

## Ce que le logiciel ajoute tout seul
En tête de chaque mission copiée ou jointe (MISSION.md), le logiciel écrit le titre, le code, la version, la
référence du paquet, l'empreinte des données, puis les **règles communes** (`ENTETE_MISSION` dans
`zenitude/socle/paquet.py`) :
- le paquet est la seule source des chiffres réels, pas d'accès à Pennylane ;
- hypothèses uniquement celles de la mission (sinon hypothèse prudente, écrite et signalée) ;
- cartouche en tête de chaque document (référence, empreinte, mission et version, périmètre, période, date) ;
- chaque chiffre sourcé (fichier et ligne, hypothèse ou formule), constaté / estimé / à confirmer ;
- section finale « Sources et hypothèses » ;
- incohérences signalées, jamais corrigées en silence ;
- pour un groupe, même méthode par résidence puis consolidation à partir des fichiers `groupe_*`.
Inutile de les répéter dans les consignes.

## Plan conseillé des consignes
1. **Objectif** : le document à produire et pour qui (une ligne).
2. **Hypothèses** : taux, indexations, scénarios, règles de retraitement, valeurs par défaut. Ce sont elles qui
   changent d'une mission à l'autre.
3. **Méthode** : étapes, en citant les fichiers du paquet à utiliser (voir LISEZ-MOI.md : `cr_gestion_periode.csv`,
   `balance_mensuelle.csv`, `tiers_soldes.csv`, `fournisseurs_mensuel.csv`, `banque_mensuel.csv`,
   `kpi_mensuel.csv`, `controles.csv`, `ecritures.csv`…) et le traitement attendu de chaque contrôle C01 à C10.
4. **Pièces complémentaires** : ce que l'utilisateur joindra en plus du paquet (budget de CA, baux, fichier de suivi
   des loyers…), avec la règle si elles manquent.
5. **Contrôles avant livraison** : totaux à retrouver, cohérences à vérifier.

Les **livrables** (champ séparé) donnent les noms de fichiers et le plan type de chaque document.

## Transformer un prompt existant
1. Supprimer tout ce qui concerne l'accès à Pennylane, les autorisations et la vitesse des appels.
2. Remplacer chaque lecture de Pennylane par le fichier du paquet correspondant :

| Le prompt demandait | Fichier du paquet |
| --- | --- |
| balance des comptes 6 et 7, mois par mois | `balance_mensuelle.csv`, `cr_gestion_mensuel.csv` |
| compte de résultat et comparatif N-1 | `cr_gestion_periode.csv` (et `groupe_cr_gestion.csv`) |
| factures récurrentes par fournisseur et par mois | `fournisseurs_mensuel.csv`, contrôles C04 et C05 |
| comptes fournisseurs débiteurs, clients créditeurs | `tiers_soldes.csv`, contrôles C06 et C07 |
| journal de banque, paiements, virements | `banque_mouvements.csv`, `banque_mensuel.csv` |
| comptes 471, 580, transit | `balance_fin.csv`, contrôles C08 et C09 |
| paies (OD salaires) | `balance_mensuelle.csv` (641, 645), contrôle C03 |
| taxe de séjour | contrôle C10, `ecritures.csv` |
| KPI (TO, prix moyen, RevPAR) | `kpi_mensuel.csv` |
| société, exercice, activité | `residences.csv` |
3. Garder la méthode, les hypothèses et les livrables. Retirer la boucle « résidence par résidence » : un paquet
   de groupe suffit.
4. Préciser les pièces que le paquet ne contient pas (baux, budget de CA, factures en pièce jointe) : elles sont
   jointes à la conversation.
5. Enregistrer la mission dans le logiciel (jamais dans le dépôt, qui est public).
