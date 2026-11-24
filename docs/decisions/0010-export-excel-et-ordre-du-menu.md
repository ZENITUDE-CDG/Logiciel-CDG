# 0010 - Lot 17 : ordre du menu latéral et export Excel des pages

Date : 24 novembre 2026
Statut : demandé par le porteur du projet (24 novembre 2026) ; à faire approuver comme les décisions 0004 à 0009

## Contexte
Demandes du porteur du projet : améliorer la mise en page du ruban de gauche (Résidence en haut, puis Import et
paramètres, Tableaux de bord, Ajustements, Trésorerie, Budgets, Rapports) et pouvoir exporter en Excel tous les
tableaux et graphiques avec leurs données et les écritures des montants calculés.

## Décisions
1. **Menu latéral** : ordre ci-dessus. Aucune autre rubrique ni page n'est modifiée. La page ouverte à la
   connexion reste le choix de la résidence, puis les tableaux de bord.
2. **Export Excel** : un bouton dans l'en-tête de chaque page de données (Tableaux de bord, Trésorerie, Écarts
   Réel → Ajusté). Le classeur reprend la période, le périmètre et la vue (ajustée ou réelle) de la page.
   Contenu : Résumé, Indicateurs, un onglet par tableau, Graphiques (données), Ajustements actifs, Détail des
   calculs, Composition, Écritures.
3. **Écritures** : pour chaque montant cliquable, les écritures comptables qui le composent (les mêmes que le
   panneau de détail du lot 14). Un montant composé (résultat, sous-total) est suivi jusqu'aux écritures de ses
   comptes, sans doublon. Pour un ratio (KPI), les écritures sont celles de ses numérateurs et dénominateurs.
4. **Liens** : chaque montant d'un tableau renvoie à sa ligne de « Détail des calculs » (référence C001...), et
   chaque ligne de détail à ses écritures. La feuille Écritures se filtre par référence.
5. **Technique** : le fichier .xlsx est écrit par le navigateur (zip et XML), sans bibliothèque externe et sans
   connexion. Aucune formule Excel n'est écrite (invariant 6) : les montants sont des valeurs, les formules sont
   en texte dans le détail. Les chiffres sont ceux de la page ; rien d'officiel n'est recalculé (décisions 0002
   et 0008).
6. **Droits** : l'export ne contient que ce que la page affiche à la personne connectée ; il n'ouvre aucune donnée
   supplémentaire. Les pages réservées aux administrateurs le restent.

## Limites connues
- Les graphiques sont exportés sous forme de données (période et séries), pas comme graphiques Excel natifs.
- Montants des tableaux arrondis comme à l'écran ; les écritures sont au centime.
- Détail limité à 1 000 000 d'écritures et 5 000 sous-calculs par export (avertissement dans le Résumé).
- Pages Import et paramètres, Résidence, Budgets, Rapports : pas d'export (données de paramétrage ou à venir).
