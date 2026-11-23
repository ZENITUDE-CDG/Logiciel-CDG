# 0008 - Lot 14 : détail des calculs, lissage de postes, compte et logo

Date : 23 novembre 2026
Statut : approuvé par le porteur du projet (23 novembre 2026) ; à faire approuver comme les décisions 0004 à 0007

## Contexte
Le porteur du projet demande, en priorité : ouvrir son compte en cliquant sur son adresse en bas à gauche ;
pouvoir cliquer sur tout montant (tableau ou graphique) pour voir la formule et les opérations (écritures
comptables, KPI) ; revenir au choix des résidences par le logo depuis toute page. Il demande aussi le lissage de
postes sur le modèle de Waibi (écriture par écriture, répartition possible sur l'exercice suivant), ce qui
suppose le détail des écritures.

## Décisions
1. **Détail des écritures publié.** Le moteur publie, pour chaque résidence, ses écritures (identifiant stable :
   pièce + rang de la ligne, date, journal, pièce, compte, libellé, montant, tiers, lettrage, échéance), dans la
   partie de la résidence (`donnees_residences`), donc lisibles selon le parc. Jamais dans la partie commune.
2. **Détail des calculs.** Un clic sur un montant ouvre un panneau : valeur, formule, éléments du calcul
   (cliquables jusqu'aux comptes), écritures d'origine (export CSV), ajustements et lissages en vue Ajusté.
   Le panneau utilise les mêmes fonctions que l'écran ; pour les montants calculés par le moteur (compte de
   résultat publié, trésorerie, créances et dettes), il refait la somme des écritures et affiche le
   rapprochement avec le moteur. Un test vérifie, sur toutes les pages, que la valeur du détail est celle
   affichée et que tous les rapprochements sont exacts.
3. **Lissage de postes (remplace le lissage par compte du lot 13).** Une écriture lissée sort de son mois ; son
   montant est réparti à parts égales (au centime, reste sur les premiers mois) sur la période choisie, qui peut
   aller jusqu'à la fin de l'exercice suivant, **comme Waibi**, y compris sur des mois sans écriture. Le total est
   conservé. La frise des mois va désormais jusqu'à la fin de l'année suivante. Lissages actifs dès leur
   création, appliqués en vue Ajusté. Table `lissages` (migration 005) : mêmes droits que les ajustements (lecture
   selon le parc ; collaborateur sur ses résidences ; lecture seule : rien). Une écriture modifiée ou supprimée à
   une publication suivante rend son lissage « non appliqué » et signalé, jamais deviné.
4. **Compte** : clic sur le nom et l'adresse en bas à gauche du menu (et en haut de l'écran de choix) ; le bouton
   flottant « Mon espace » est supprimé ; la page s'appelle « Mon compte ».
5. **Logo** : sur le tableau de bord, il ouvre le choix des résidences (inchangé) ; sur Mon compte et
   Administration, il renvoie au tableau de bord sur le choix des résidences (`index.html#choix`).

## Limites
- Les montants affichés comme des nombres de lignes (contrôle des données, imports) ne sont pas détaillés.
- Le lissage d'une écriture d'un exercice n'est éditable que depuis cet exercice (choix de l'exercice en haut
  de la page) ; son effet apparaît partout.
- Calcul des lissages dans la page (décision 0002), à reprendre par le backend en production.

## Approbations
| Instance | Statut |
| --- | --- |
| Porteur du projet | Approuvé le 23/11/2026 (lissage comme Waibi, répartition possible sur l'exercice suivant) |
| Benjamin Gagneur | À tracer |
| Contrôle de gestion | À tracer (définition du lissage) |
| DAF | À tracer |
| DSI | À tracer (détail des écritures dans la base de test) |
