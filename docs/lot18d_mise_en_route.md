# Lot 18d - Mise en route (lecture par modifications)

## 1. GitHub : fichiers du lot
Déposer les fichiers de l'archive (aucun fichier du dossier `.github`). Vérifier : onglet **Actions**,
« Tests et publication » avec deux coches vertes. Ce dépôt relance une publication automatique : elle fait
la première lecture complète et conserve les écritures (si la migration 009 est déjà appliquée).

## 2. Supabase : migration 009
**SQL Editor, New query** : coller tout `migrations/009_ecritures_pennylane.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». (Ne pas utiliser `installation_supabase.sql`.)

## 3. Essai : deux synchronisations de suite depuis la page
Journal de chaque exécution (lien « exécution »), étape « Lire Pennylane, calculer et publier » :
- 1re : « Lecture : complète » ; « Écritures conservées pour la prochaine synchronisation ».
- 2e : « Écritures conservées relues dans la base : ... ligne(s) » ; « Lecture : par modifications depuis ... :
  X ligne(s) modifiée(s) ou ajoutée(s), Y supprimée(s) » ; « Contrôle de la balance Pennylane : identique » ;
  « Durée de lecture Pennylane : ... s ».

## Quand la lecture reste complète (normal, le motif est écrit dans le journal)
- première synchronisation, ou migration 009 absente ;
- dernière relecture complète il y a plus de 7 jours (relecture de sécurité hebdomadaire) ;
- période demandée plus large que celle déjà lue (par exemple, début avancé) ;
- journal des modifications de Pennylane indisponible ;
- balance de Pennylane différente de celle des écritures conservées : la relecture complète corrige
  automatiquement.
Si « Contrôle de la balance » indique « différente » à chaque synchronisation, envoyer le journal : la
comparaison avec la balance de Pennylane est à ajuster (par exemple écritures en brouillard exclues de sa
balance).
