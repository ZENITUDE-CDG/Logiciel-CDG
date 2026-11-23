# Lot 14 - Mise en route (sans rien installer)

## Si le lot 13 n'est pas encore installé
Suivre `docs/lot13_mise_en_route.md` avec les fichiers de ce lot : `scripts/installation_supabase.sql`
contient déjà la migration 005 (lissages).

## Si le lot 13 est déjà installé
1. Supabase, **SQL Editor** : coller `migrations/005_lissages.sql`, **Run**. Rien n'est effacé.
   (Ou relancer tout `scripts/installation_supabase.sql` : remise à zéro complète, ajustements compris.)
2. GitHub : déposer les fichiers du lot (glisser-déposer). Le dépôt sur main relance les tests puis la
   publication : elle ajoute le détail des écritures dans la base.

## Vérifier
- Onglet Actions : « Tests et publication » avec deux coches vertes.
- Site : cliquer sur un montant (tableau, carte, point d'un graphique, barre) ouvre le détail à droite ;
  « › » descend dans le calcul, « ← » remonte, Échap ferme.
- Ajustements, **Lissage de postes** : choisir une résidence, ouvrir « Écritures » sur un compte, activer
  « Lissée » sur une écriture, choisir les mois, Valider.
- En bas à gauche, l'adresse e-mail ouvre Mon compte ; sur Mon compte, le logo ramène au choix des résidences.
