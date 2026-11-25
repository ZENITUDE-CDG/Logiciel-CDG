# 0014 - Lot 20 : suivi KPI paramétrable (catalogue, modèles de suivi, modèle Excel)

Date : 25 novembre 2026
Statut : approuvé par le porteur du projet (25 novembre 2026).

## Contexte

Les KPI suivis chaque mois (consolidé KPI, lot 19) étaient codés en dur dans le logiciel. Le porteur du projet
veut un outil modulable : créer, activer, désactiver et organiser les KPI dans la page Paramètres KPI, exporter un
modèle Excel sur la période voulue, le remplir et le redéposer. Les indicateurs suivis diffèrent selon l'activité
(tourisme, seniors, étudiants) : un import sur un groupe doit vérifier que tout ce qu'il contient existe et
correspond au modèle de chaque résidence.

## Décisions

1. **Données et indicateurs sont séparés.** Une donnée est une valeur mensuelle saisie ou importée par résidence,
   sous un code stable (`kpi_catalogue.code`, jamais modifiable, comme le type). Un indicateur est calculé,
   jamais importé : facteur x somme(numérateur) / somme(dénominateur), ou facteur x somme(numérateur) sans
   dénominateur. Changer une formule recalcule tout l'historique depuis les données brutes ; changer la définition
   d'une donnée se fait en créant un nouveau code.
2. **Ratio de sommes (invariant 4).** Sur un groupe ou plusieurs mois, sommes d'abord, rapport ensuite. Résidences
   retenues : celles dont le modèle suit l'indicateur. Couples (résidence, mois) retenus : ceux où toutes les
   données de la formule sont présentes ; une absence n'est jamais un zéro (invariant 1). Une couverture
   incomplète est signalée (astérisque, détail du calcul) ; aucun couple : « non calculable » avec motif.
3. **Modèles de suivi** (`kpi_modeles`) : Tourisme, Seniors, Étudiants au départ, d'autres peuvent être ajoutés.
   Chaque donnée et chaque indicateur liste les modèles qui le suivent ; chaque résidence a un modèle
   (`residence_modele`), proposé d'après son activité (Hôtellerie → Tourisme, Seniors et Mixte → Seniors,
   Étudiants → Étudiants) et modifiable. Un indicateur ne peut être suivi par un modèle que si ce modèle suit
   toutes les données de sa formule (contrôlé par la page).
4. **La base reste seule juge** : formule limitée aux données existantes, modèles existants, donnée utilisée par un
   indicateur actif ni désactivable ni supprimable, donnée ayant des valeurs importées non supprimable (on la
   désactive), code et type figés. Valeur négative importée acceptée seulement pour une donnée « signée »
   (montants, avoirs) : remplace la règle « CA_... » du lot 19, conservée en secours.
5. **Gouvernance** : seuls les administrateurs modifient le catalogue, les modèles et le modèle de chaque
   résidence ; chaque modification s'applique tout de suite, sans seconde validation (même choix que les
   ajustements, décision 0007). La base journalise chaque création, modification et suppression
   (`kpi_journal` : avant, après, auteur, date), sans écriture possible depuis la page.
6. **Modèle Excel** (page Données externes, ou bouton de Paramètres KPI) : sur le périmètre et la période choisis,
   une feuille « Lisez-moi » (format `ZENITUDE-MODELE-KPI v1`, périmètre, période, empreinte du catalogue, feuille
   de chaque modèle, liste des données) et une feuille par modèle de suivi : une ligne par résidence et par mois,
   une colonne par donnée active du modèle (ligne 2 : codes), déjà remplie avec les valeurs importées. Écrit par le
   navigateur (écriture Excel du lot 17), sans bibliothèque.
7. **Redépôt** : reconnu automatiquement (onglet « Lisez-moi »). Refusé en entier si le format est inconnu, si une
   feuille manque, si une colonne est une donnée inconnue, désactivée ou non suivie par le modèle de la feuille, si
   une résidence est inconnue ou suit un autre modèle que celui de sa feuille, si un mois est en double. Une donnée
   ajoutée au modèle depuis l'export est signalée (« réexportez le modèle »), sans bloquer. Valeur illisible ou
   négative sur une donnée positive : écartée et listée (règle du lot 19). Cellule vide : non fournie, ne supprime
   rien. Mêmes aperçu, enregistrement et historique que le consolidé (lot 19).
8. **Export bloqué** tant qu'une résidence du périmètre n'a pas de modèle ou qu'un indicateur actif a une formule
   incohérente (contrôles du catalogue affichés dans Paramètres KPI).
9. Le **consolidé KPI** (lot 19) reste accepté : ses colonnes sont maintenant lues d'après le catalogue (colonne du
   consolidé de chaque donnée active ; ratios contrôlés d'après les indicateurs qui ont une colonne du consolidé).
   Si l'outil KPI change, on ajuste la colonne dans la page, sans développement.
10. Nouveau tableau de bord « Indicateurs suivis » : indicateurs et données du catalogue par rubrique, mois de la
    réglette, période, N-1, évolution, seuil d'alerte (sens : plus haut ou plus bas = mieux), détail au clic.
11. Les indicateurs du moteur (classeur de configuration, lots 1 à 6) restent en place, affichés en bas de
    Paramètres KPI. Leur remplacement par le catalogue est un chantier ultérieur.

## Conséquences

- Migration 012 (sans remise à zéro), amorce du catalogue générée par `interface/catalogue_kpi.py` (un test
  vérifie qu'elle est à jour). Aucun secret, aucune fonction serveur à redéployer.
- Correctif : dans l'aperçu d'un dépôt KPI, chaque bouton garde son propre gestionnaire (le bouton Importer
  plantait quand le bloc des groupes était absent). Test du rechargement automatique du lot 18c rendu effectif.
