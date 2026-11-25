# Lot 18c - Mise en route (vitesse de la synchronisation, heures de Paris, rechargement automatique)

## 1. GitHub : fichiers du lot
Déposer les fichiers de l'archive (aucun fichier du dossier `.github` cette fois). Vérifier : onglet
**Actions**, « Tests et publication » avec deux coches vertes.

## 2. Supabase : migration 008
**SQL Editor, New query** : coller tout `migrations/008_lettrages_pennylane.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». (Ne pas utiliser `installation_supabase.sql`.)
Sans cette migration, la synchronisation fonctionne mais relit tout le lettrage à chaque fois.

## 3. Essai
Synchroniser le dossier de test deux fois de suite depuis la page Import comptable, puis ouvrir le journal
de chaque exécution (lien « exécution » de l'historique), étape « Lire Pennylane, calculer et publier » :
- « Lecture : pages de 1000 éléments ; filtre de dates appliqué par Pennylane : oui » (si Pennylane refuse,
  le connecteur se replie sur des pages de 100 ou sans filtre : le résultat est identique, seulement plus lent) ;
- « Lettrage : ... reprise(s) de la mémoire, ... demandée(s) à Pennylane » : à la deuxième synchronisation,
  presque tout vient de la mémoire ;
- « Durée de lecture Pennylane : ... s ».
À la fin d'une synchronisation, la page recharge seule les chiffres et revient sur Import comptable. Les
heures affichées sont à l'heure de Paris.
