# Lot 31 - Page Société (décision 0023)

Renomme « Résidence » en « Société » ; création, modification et archivage des sociétés ; noms et codes dans les
autres outils ; classements et groupes modifiables ; exercices N-2 à N+2 ; cinq derniers ajustements. La base n'est
PAS remise à zéro.

## 1. GitHub
Déposer le contenu de l'archive en gardant les dossiers (nouveau : `tests/lot31/`), puis **Commit changes**.
Vérifier les deux coches vertes dans Actions.

## 2. Supabase : migration 020
**SQL Editor** : coller tout `migrations/020_societes.sql`, **Run** (« Success. No rows returned »). Rejouable.
Sans elle, la page Société s'affiche en lecture seule avec un bandeau.

## 3. Essai
1. Choisir le groupe, menu **Société** : liste des sociétés, recherche par nom ou code, archivées sur demande.
2. **+ Nouvelle société** (administrateurs) : code interne proposé, nom obligatoire. Elle reste « En attente de
   données » jusqu'à la publication qui suit le rattachement de son dossier Pennylane.
3. **Groupes et classements** (bas de la liste) : créer un classement (exemple « RM », exclusif), puis **+ Groupe** et
   cocher les sociétés. Modifier, déplacer ou supprimer un groupe ; supprimer un classement garde ses groupes.
4. Ouvrir une société : **Modifier** (un champ vidé reprend la configuration), **Archiver** ; sous l'identité,
   ajouter les noms et codes (« Mews » / « TRT », « Pennylane » / « YTR »…) ; groupes de la société ; exercices
   N-2 à N+2 et **Voir plus** ; cinq derniers ajustements avec date et auteur ; historique de la fiche.
5. Rechercher « TRT » dans le choix des sociétés : la société correspondante sort.

## 4. Limites
- Un groupe attribué dans un parc ne se supprime pas : le retirer d'abord dans Administration.
- Les groupes et la fiche de la configuration publiée (classeur) restent la valeur de départ ; la page les complète.
