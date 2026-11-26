# Lot 24 - Comptabilité du siège et trésorerie prévisionnelle (décision 0018)

Ajoute la section Comptabilité (CA, Paramétrage des FEES, FEES à refacturer) et la page Trésorerie,
Prévisions et virements. La base n'est PAS remise à zéro ; aucune donnée existante n'est touchée.

## 1. GitHub : déposer les fichiers de l'archive
Glisser-déposer le contenu de l'archive dans le dépôt en gardant les dossiers (nouveaux dossiers
`zenitude/comptabilite/` et `tests/lot24/`), puis **Commit changes**. Aucun fichier ne commence par un point :
pas de manipulation particulière.

Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes (la suite reconstruit sa propre
base de test avec la migration 015).

## 2. Supabase : migration 015
**SQL Editor, New query** : coller tout `migrations/015_comptabilite_et_tresorerie_previsionnelle.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». Elle crée les tables du lot, ajoute le plafond des comptes
bancaires et les rubriques et taux de départ. Elle peut être relancée sans effet.
(Ne pas utiliser `installation_supabase.sql`, qui remet tout à zéro.)

## 3. Vérifier
- **Comptabilité, Chiffre d'affaires** : CA par résidence et par mois ; un clic sur un montant montre ses écritures.
- **Paramétrage des FEES** : management fees 8 %, répartition 40 / 20 / 20 / 15 / 5 % (pastille « 100 % »).
  Ajuster le droit de marque (clic sur la case du groupe), et les taux propres des résidences.
- **FEES à refacturer** : choisir le mois, contrôler, **Clôturer**. Export CSV ou Excel.
- **Trésorerie, Comptes bancaires** : renseigner minimum et plafond. **Prévisions et virements** : saisir les flux
  connus (salaires, loyers, emprunts…), lire les virements proposés, **Marquer fait** une fois passés en banque.

## En cas de problème
- « Migration 015 non appliquée » : refaire l'étape 2, puis recharger la page.
- Un taux saisi ne change pas un mois : ce mois est clôturé (rouvrir puis clôturer de nouveau) ou la version
  commence plus tard.
