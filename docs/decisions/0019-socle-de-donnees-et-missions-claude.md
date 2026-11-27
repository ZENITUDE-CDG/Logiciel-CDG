# 0019 - Socle de données pour Claude et missions

Date : 27 novembre 2026
Statut : décidé par le porteur du projet (27 novembre 2026), phase test, données fictives.

## Contexte

Les analyses récurrentes (situation et EBITDA normatif, budget, effort de loyer, négociation…) sont aujourd'hui
confiées à Claude par des prompts de type cahier des charges qui lui demandent d'aller chercher les données dans
Pennylane, résidence par résidence. C'est lent (des dizaines d'appels par résidence), non reproductible (deux
exécutions peuvent lire des données différentes), sans historique commun, et impossible à mener sur une centaine
de résidences sans répéter cent fois la même opération. Les hypothèses (taux Choice, fees, indexations, scénarios)
changent d'une analyse à l'autre : les figer dans le logiciel demanderait un paramétrage par scénario.

## Décision

1. **Partage des rôles.** Le logiciel fournit le tronc commun : les chiffres réels, complets et standardisés.
   Claude fait l'analyse. Les hypothèses, scénarios, retraitements et livrables sont écrits dans des **missions**,
   jamais dans le logiciel ni dans le paquet.
2. **Paquet pour Claude** (Rapports, « Paquet pour Claude ») : pour le périmètre du ruban (une résidence ou un
   groupe entier) et la période de la réglette, un .zip de fichiers CSV standard (une ligne par résidence et par
   mois, toutes les résidences dans les mêmes fichiers), un LISEZ-MOI.md (règles pour Claude, conventions,
   dictionnaire des fichiers), MISSION.md si une mission est jointe et un classeur synthese.xlsx pour lecture.
   Deux niveaux : complet (grand livre et mouvements bancaires compris) ou synthèse (par défaut au-delà de
   10 résidences).
3. **Chiffres réels uniquement** : écritures publiées depuis Pennylane et données d'exploitation importées. Aucun
   ajustement, lissage, provision ni hypothèse. Une donnée absente est une case vide, jamais zéro.
4. **Contrôles automatiques** C01 à C10 (mois sans données, sans CA, sans paie, fournisseur récurrent sans facture,
   doublon possible, fournisseur débiteur, client créditeur, comptes 47 et 58 non soldés, taxe de séjour en CA) :
   ce sont des constats, pas des corrections. La mission dit comment les traiter.
5. **Traçabilité.** Chaque paquet reçoit une référence (PQ-000001) inscrite au journal partagé avant le
   téléchargement, et une empreinte SHA-256 des fichiers de données. Les deux figurent dans LISEZ-MOI.md et
   MISSION.md ; les règles communes des missions imposent de les citer en tête de chaque document produit, de
   sourcer chaque chiffre (fichier et ligne) et de finir par « Sources et hypothèses ». Le document produit (lien
   ou nom) se note ensuite sur la ligne du journal : on retrouve qui a produit quoi, avec quelles données et quelle
   version de mission. En ligne, un paquet qui n'a pas pu être inscrit n'est pas téléchargé.
6. **Missions** (Rapports, « Missions Claude ») : nombre illimité, code stable, catégorie, consignes, livrables.
   Chaque modification du contenu crée une nouvelle version (les anciennes restent lisibles et copiables). Lecture
   par tous ; création, modification et archivage par les administrateurs. Les textes des missions sont dans la
   base, jamais dans le dépôt (public).
7. **Calcul** : référence Python `zenitude/socle/paquet.py` ; la page construit le même paquet (fonction
   `socleConstruire`) à partir des seules données que la personne a le droit de voir. Un test vérifie que les
   fichiers sont identiques à l'octet près. Rien du paquet n'est stocké dans la base.

## Conséquences

- Un prompt existant devient une mission : on retire tout ce qui concerne l'accès à Pennylane et la collecte, on
  garde la méthode, les hypothèses et les livrables, et on remplace les lectures par les fichiers du paquet.
- Un seul paquet et un seul échange suffisent pour tout un groupe.
- Les données réelles ne vont à Claude que si la DSI et la DAF l'approuvent (invariant 8 : en phase test, seules
  des données fictives existent dans le logiciel). Le partage est volontaire : la personne télécharge le paquet et
  le joint elle-même ; le logiciel n'appelle aucun service d'IA (invariant 10).
- Les factures fournisseurs non reprises dans les écritures (pièces jointes Pennylane), les baux, les contrats et
  les budgets de CA ne sont pas dans le paquet : la mission les fournit en pièces jointes si besoin.
