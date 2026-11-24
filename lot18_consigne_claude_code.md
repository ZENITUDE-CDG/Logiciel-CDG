# Lot 18 - Connecteur Pennylane sur le dossier de test

Consigne à donner à Claude Code, avec le résultat du workflow « Test structure Pennylane »
(noms des champs seulement) collé à la fin.

## Contexte

- Le porteur du projet a créé un jeton Pennylane **en lecture seule** sur un **dossier de test** :
  ce n'est pas une résidence en activité, il ne contient aucune donnée confidentielle.
- Le jeton est dans les secrets GitHub : `PENNYLANE_TOKEN_PILOTE`. Il n'existe nulle part ailleurs.
- Trois workflows manuels existent déjà et fonctionnent : `test-pennylane.yml` (connexion),
  `test-pennylane-balance.yml` (balance d'un mois, sans montant affiché),
  `test-pennylane-structure.yml` (noms des champs).
- Objectif du lot : que les écritures du dossier de test arrivent jusqu'à la page en ligne, par le
  même chemin que les données de démonstration (moteur Python dans GitHub Actions, publication dans
  Supabase, lecture selon le parc), **sans toucher aux huit résidences de démonstration**.

## Préalable : décision 0011

Créer `docs/decisions/0011-connecteur-pennylane-dossier-test.md` (statut : approuvé par le porteur du
projet le 24 novembre 2026 ; aucune autre approbation requise, le dossier de test ne contient aucune donnée
confidentielle). Elle lève, **pour ce seul dossier de test**, la
limite « ne pas configurer de connexion réelle à Pennylane » de CLAUDE.md :
1. Connexion en lecture seule, jeton dans les secrets GitHub uniquement.
2. Un seul dossier autorisé (liste blanche), marqué `fictif = true` dans la base.
3. Aucune valeur comptable dans le dépôt, les journaux GitHub Actions, les artefacts ou un service d'IA
   (invariant 8) : les journaux n'affichent que des nombres de lignes et des contrôles oui / non.
4. Toute résidence réelle reste refusée par la publication (garde-fou existant de `publier_supabase.py`).
5. Le dépôt étant public, le branchement d'une résidence réelle exige une nouvelle décision
   (dépôt privé ou autre hébergement, validé par la DSI).

## Travail demandé

1. **Connecteur** `zenitude/connecteurs/pennylane.py`, séparé du modèle métier (« changer de source ne
   réécrit pas le P&L ») :
   - API v2 (`https://app.pennylane.com/api/external/v2`), en-tête `Authorization: Bearer`, bibliothèque
     standard (`urllib`, comme `publier_supabase.py`) : aucune nouvelle dépendance.
   - Lit les exercices, les journaux et les écritures (lignes) ; pagination par `cursor` / `limit` ;
     respecte la limite de 25 requêtes par 5 secondes ; reprise sur 429.
   - Produit, dans un dossier temporaire du runner, `ecritures.csv` et `exercices.csv` **au format exact
     du jeu de démonstration** (`interface/demo/`) :
     `dossier;exercice;date;journal;piece;compte;libelle;debit;credit;tiers;lettrage;echeance`
     et `dossier;debut;fin;duree_mois`.
   - Correspondance des champs : d'après le résultat de « Test structure Pennylane » joint. Un champ
     absent (tiers, lettrage, échéance) reste vide, jamais inventé (invariant 1).
   - Exercices réels Pennylane : ne jamais supposer janvier-décembre ni douze mois.
   - Refuse tout dossier absent de la liste blanche.
2. **Identifiant du dossier de test** : `PENNY-TEST` (invariant 11). Ajouté à
   `zenitude/config/dossiers_connus_test.txt` et à l'onglet Referentiel de la configuration de
   démonstration.
3. **Classement des comptes** : les comptes de classe 6 et 7 du dossier de test qui ne sont pas classés
   bloqueront le résultat (contrôle P1). Ne pas inventer de classement : produire la liste des comptes
   non classés (numéros seulement) et me la soumettre.
4. **Base Supabase** : résidence `RES-TEST`, libellé « Dossier Pennylane de test », `dossier_pennylane =
   PENNY-TEST`, `fictif = true`, ajoutée à `scripts/donnees_test.sql` puis `installation_supabase.sql`
   régénéré. Visible par les administrateurs uniquement (pas dans le parc de Benjamin).
5. **Workflow** `.github/workflows/synchro-pennylane-test.yml`, lancement manuel :
   connecteur → fichiers temporaires → moteur → publication de `RES-TEST` avec le chemin existant
   (`publier_supabase.py` étendu pour accepter cette seconde source sans modifier la publication des
   huit résidences de démonstration). Aucun artefact, aucun fichier commité, journaux sans montant.
6. **Tests** (sans réseau, sans secret) : faux serveur Pennylane avec des réponses JSON synthétiques
   marquées « fictif » : pagination, correspondance des champs, débit / crédit, champ manquant, dossier
   hors liste blanche refusé, 429. Publication : `RES-TEST` publiée, résidences de démonstration
   inchangées, résidence réelle toujours refusée. Aucun jeton versionné (test existant étendu).
7. **Paramètre « Écritures reprises »** (Import et paramètres, administrateurs) :
   - Deux choix : « Validées seulement » (par défaut) ou « Validées et brouillard ».
   - Enregistré dans la base (nouvelle table de paramètres d'import, règles par ligne et tests de droits dans
     le même commit, comme l'exige le lot 12) ; lu par le workflow de synchronisation au lancement.
   - Le connecteur récupère toujours tous les statuts, puis filtre selon le paramètre avant le moteur
     (les calculs restent dans le moteur Python, jamais dans la page).
   - Statuts observés dans `ledger_entries.status` : les lister dans les journaux avec leur nombre de lignes.
     Un statut inconnu est traité comme non validé et signalé.
   - Changer le paramètre affiche dans la page « à recalculer » jusqu'à la synchronisation suivante ; la page
     indique toujours le mode utilisé pour les chiffres affichés (« Écritures validées seulement » ou
     « y compris brouillard ») et la date de synchronisation. Le mode est conservé avec la publication
     (invariant 5).
   - Le workflow accepte aussi le choix en paramètre de lancement manuel, qui prime sur la base.
8. **Documentation** : section « Lot 18 » de `CLAUDE.md`, `CONTEXTE.md`, `docs/lot18_mise_en_route.md`
   (étapes dans le navigateur, comme les lots précédents).

## Hors périmètre

- Résidences réelles, jeton cabinet (« Firm »), fichier comptable Mews, Zeendoc.
- Module de contrôle et de fiabilisation (lots suivants, document « Module Contrôle & Fiabilisation
  des données »).
- Synchronisation automatique planifiée (après validation de ce lot).

## Critère de fin

- `pytest` au vert sur GitHub.
- « Synchro Pennylane test » au vert ; `RES-TEST` visible en ligne pour un administrateur, avec la
  balance équilibrée et le même nombre de comptes que « Test balance Pennylane » sur la même période.
- Les huit résidences de démonstration sont inchangées.

## Correspondance des champs (relevée le 24 novembre 2026 sur le dossier de test)

Source : workflow « Test structure Pennylane » (noms de champs uniquement, aucune valeur).
Toutes les listes renvoient `items`, `has_more`, `next_cursor` (pagination par curseur).

| Colonne de `ecritures.csv` | Source Pennylane | Remarque |
| --- | --- | --- |
| dossier | constante `PENNY-TEST` | liste blanche |
| exercice | `/fiscal_years` : `start`, `finish` | exercice dont la période contient la date ; format `debut/fin` comme la démonstration |
| date | `/ledger_entry_lines` : `date` | |
| journal | `ledger_entry_lines.journal.id` → `/journals` : `code` | table de correspondance id → code lue une fois |
| piece | `ledger_entry_lines.ledger_entry.id` → `/ledger_entries` : `piece_number` | à défaut `invoice_number`, sinon vide |
| compte | `ledger_entry_lines.ledger_account.number` | |
| libelle | `ledger_entry_lines.label` | à défaut `ledger_entries.label` |
| debit / credit | `ledger_entry_lines.debit`, `credit` | probablement des chaînes : conversion en Decimal, jamais en float |
| tiers | **aucun champ direct** | voir point ouvert 1 |
| lettrage | `ledger_entry_lines.lettered_ledger_entry_lines.url` | lien vers les lignes lettrées ensemble, pas de code de lettre : voir point ouvert 2 |
| echeance | **absente** des écritures | laisser vide ; le moteur applique déjà « échéance inconnue » ou la règle pièce + N jours (lot 11) |

`exercices.csv` : `/fiscal_years` → `debut = start`, `fin = finish`, `duree_mois` calculée sur les dates réelles
(jamais 12 par défaut).

Champs utiles pour les lots suivants (module de contrôle), à conserver dans le connecteur sans les publier :
`ledger_entries.status`, `fiscal_years.status`, `updated_at` des écritures et des lignes (détection des
modifications après clôture, contrôle TR-06), `ledger_accounts.type`.

## Choix retenus (avancer sans attendre de validation)

1. **Tiers** : si les tiers apparaissent comme comptes auxiliaires (`ledger_accounts.type`, comptes 401 / 411
   subdivisés), remplir `tiers` avec le numéro de compte auxiliaire ; sinon laisser vide (créances et dettes non
   calculables, invariant 1). Indiquer dans le compte rendu ce qui a été observé (types et longueurs de numéros,
   jamais les numéros ni les libellés).
2. **Lettrage** : limité aux comptes 40 et 41 ; identifiant de groupe = `L` + plus petit `id` de ligne du groupe
   (invariant 11) ; 25 requêtes par 5 secondes respectées ; durée constatée indiquée dans le compte rendu.
3. **Statut des écritures** : paramètre « Écritures reprises », point 7 ci-dessus, « Validées seulement » par
   défaut.
4. **Comptes non classés** (P1) : pour le dossier de test uniquement, les classer par préfixe du PCG de
   référence (`config_modele/pcg_reference.csv`), marqués « provisoire » ; lister ces comptes (numéros
   seulement) dans le compte rendu.

## Résultat brut de « Test structure Pennylane »

- `/fiscal_years` : created_at, finish, id, start, status, updated_at
- `/journals` : code, id, label, type
- `/ledger_accounts` : country_alpha2, created_at, enabled, id, label, number, type, updated_at, vat_rate
- `/ledger_entries` : created_at, date, id, invoice_number, journal.id, journal.url, journal_id, label,
  piece_number, status, updated_at
- `/ledger_entry_lines` : created_at, credit, date, debit, id, journal.id, journal.url, label,
  ledger_account.id, ledger_account.number, ledger_account.url, ledger_entry.id,
  lettered_ledger_entry_lines.url, updated_at
