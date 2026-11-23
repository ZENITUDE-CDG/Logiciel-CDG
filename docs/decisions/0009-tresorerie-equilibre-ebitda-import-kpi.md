# 0009 - Lot 15 : comptes bancaires, équilibre financier, EBITDA du groupe, import des KPI

Date : 23 novembre 2026
Statut : approuvé par le porteur du projet (23 novembre 2026) ; à faire approuver comme les décisions 0004 à 0008

## Contexte
Demandes du porteur du projet : une vue des soldes bancaires de chaque résidence pour le trésorier (ajuster les
comptes principaux et secondaires), une analyse des soldes comparés à N-1 ; FRNG, BFR et TN dans les tableaux de
bord ; des graphiques qui suivent la réglette ; le tableau EBITDA du modèle de gestion du groupe (fichier « CR Senior
Bailly-Romainvilliers ») ; l'import des KPI mensuels de toutes les résidences en une fois.

## Décisions
1. **Comptes bancaires** (Trésorerie, réservé aux administrateurs en ligne) : solde comptable de chaque compte 51 et 53
   par résidence à l'arrêté, variation du mois, virements internes, solde N-1, minimum et besoin d'alimentation ;
   totaux par résidence, par groupe et pour le périmètre ; virement conseillé = le plus petit entre le besoin des
   comptes sous leur minimum (0 € sans minimum : un découvert est à combler) et l'excédent du compte principal.
   Libellé, rôle (principal, secondaire, autre) et minimum paramétrés par un administrateur (table
   `comptes_bancaires`, migration 006). Sans paramétrage, le compte le plus mouvementé est proposé comme principal.
2. **Virements internes** : une pièce équilibrée, hors à-nouveaux, sur au moins deux comptes, toute en 51, 53 ou 58
   n'est ni un encaissement ni un décaissement (position de trésorerie et comptes bancaires).
3. **Analyse du solde** : soldes de fin de mois, encaissements, décaissements et flux nets de la période comparés au
   même mois de l'année précédente, par compte ou tous comptes. N-1 non importé = « non disponible », jamais zéro.
4. **FRNG, BFR, TN** (moteur, `tresorerie.bilan`) : soldes cumulés jusqu'à l'arrêté ; ressources stables = classe 1 +
   résultat non affecté (classes 6 et 7) ; emplois stables = classe 2 nette ; BFR = classes 3 et 4 ; TN = classe 5.
   Contrôle FRNG = BFR + TN. Lecture simplifiée de la balance, à valider par le contrôle de gestion.
5. **Graphiques de la synthèse** : mois de la période choisie avec la réglette.
6. **Tableau EBITDA** : structure et règles d'affectation du modèle de gestion du groupe (onglets CR et Mapping du
   fichier fourni ; aucun montant repris, le fichier contient des données réelles). Règles : compte exact, puis
   mot-clé du libellé du compte (appliqué quand l'export fournit le libellé), puis préfixe le plus long. KPI
   (données commerciales) en tête du tableau, ratios en % du CA, éléments hors CR et résultat net pour le bouclage.
   Remplace la présentation provisoire du lot 8.
7. **Import des KPI** (Données externes) : modèle Excel (`modeles/Zenitude_Import_KPI_modele.xlsx`, une ligne par
   résidence et par mois, une colonne par KPI) ou CSV pré-rempli ; contrôle complet avant enregistrement, tout ou
   rien (invariant 7) ; import par un administrateur seulement ; une valeur importée remplace la valeur publiée pour
   le même mois et le même KPI (table `mesures_importees`, migration 006). Les KPI de la page les utilisent aussitôt.
8. **Démonstration** : un compte bancaire secondaire (5122) par résidence, alimenté par des virements internes.

## Limites et points ouverts
- Les KPI calculés par le moteur Python (publication) n'utilisent pas encore les valeurs importées : seule la page les
  utilise. À brancher côté serveur avec la base définitive.
- Colonnes du dossier KPI non reprises (CA SAP, TO seniors, lots, CA restauration seniors) : à ajouter quand le
  contrôle de gestion aura validé les KPI qui les utilisent. Ratios par chambre vendue du modèle CR non repris.
- Mots-clés d'affectation inactifs tant que l'export ne fournit pas le libellé du compte (colonne `libelle_compte`).
- N-1 : non disponible tant que l'exercice précédent n'est pas importé.
- Soldes bancaires = soldes comptables, pas les soldes en banque.

## Approbations
| Instance | Statut |
| --- | --- |
| Porteur du projet | Approuvé le 23/11/2026 |
| Contrôle de gestion | À tracer (affectations EBITDA, définitions FRNG / BFR / TN, KPI importés) |
| Trésorier | À tracer (vue des comptes bancaires, règle du virement conseillé) |
| DAF | À tracer |
| DSI | À tracer |
