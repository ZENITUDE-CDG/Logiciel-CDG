# Lot 18b - Mise en route (sans rien installer)

Synchronisation lancée depuis la page Import comptable (décision 0012). Tout se fait dans le navigateur,
dans cet ordre. La base n'est PAS remise à zéro.

## 1. GitHub : fichiers du lot
Déposer les fichiers de l'archive. Les fichiers dont le nom commence par un point ne passent pas par le
glisser-déposer : les ouvrir dans GitHub (crayon, Edit), remplacer tout le contenu par celui de l'archive,
**Commit changes** :
- `.github/workflows/synchro-pennylane-test.yml`
- `.github/workflows/tests-et-publication.yml`

Vérifier : onglet **Actions**, « Tests et publication » avec deux coches vertes.

## 2. Supabase : migration 007
**SQL Editor, New query** : coller tout `migrations/007_synchronisation_pennylane.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». (Ne pas utiliser `installation_supabase.sql`.)

## 3. GitHub : jeton pour lancer la synchronisation
1. Photo de profil GitHub, **Settings**, **Developer settings**, **Personal access tokens**,
   **Fine-grained tokens**, **Generate new token**.
2. Nom : `Zenitude - lancer synchro`. Expiration : 90 jours (à noter dans l'agenda).
3. **Resource owner** : l'organisation ZENITUDE-CDG. **Repository access** : *Only select repositories*,
   `Logiciel-CDG`.
4. **Permissions**, *Repository permissions* : **Actions : Read and write**. Rien d'autre.
5. **Generate token**, copier le jeton (il ne s'affiche qu'une fois). Ne le coller nulle part ailleurs qu'à
   l'étape 4. Si l'organisation exige une validation des jetons, un propriétaire de l'organisation doit
   l'approuver.

## 4. Supabase : la fonction serveur
1. **Edge Functions**, **Secrets** (ou *Manage secrets*) : ajouter
   - `GITHUB_JETON_SYNCHRO` : le jeton de l'étape 3 ;
   - `CLE_SECRETE_SUPABASE` : la clé secrète du projet (Project Settings, API Keys, *secret*, sb_secret_...),
     la même que le secret GitHub `SUPABASE_SECRET_KEY`.
2. **Edge Functions**, **Deploy a new function**, **Via Editor**. Nom : `lancer-synchro` (exactement).
   Remplacer le code proposé par tout le contenu de `supabase/functions/lancer-synchro/index.ts`.
   **Deploy function**.
3. Dans les réglages de la fonction (*Details* ou *Settings*) : **désactiver « Verify JWT with legacy secret »**
   (la fonction vérifie elle-même la session), puis enregistrer.

## 5. Essai
1. Ouvrir le site, se connecter en administrateur, choisir « Dossier Pennylane de test »,
   **Import et paramètres**, **Import comptable**.
2. Choisir la période, laisser « Masquer les écritures en brouillard » activé, cliquer **Synchroniser**,
   confirmer.
3. Message « Synchronisation n° ... lancée ». L'historique passe de « demandée » à « en cours » puis
   « terminée » (quelques minutes ; mise à jour automatique). Cliquer **Recharger les chiffres**.
4. Refaire l'essai en désactivant le masquage : le compte de résultat doit rejoindre celui de Pennylane.
5. Choisir « Groupe Zenitude » : le bouton devient « Synchroniser les 9 résidences » ; le dossier de test est
   synchronisé, les huit résidences de démonstration sont signalées « non connectée ».

## En cas de problème (message affiché sous le titre de la page)
- « fonction non configurée (secrets manquants) » : étape 4.1.
- « session invalide ou expirée » : se déconnecter, se reconnecter.
- « jeton GitHub refusé » : jeton expiré, mal copié ou sans le droit Actions (étape 3), ou non approuvé par
  l'organisation.
- « workflow ou dépôt introuvable » : nom du dépôt différent ; ajouter le secret `GITHUB_DEPOT`
  (organisation/dépôt).
- Message d'erreur générique sans détail, ou erreur CORS dans la console : réglage JWT de l'étape 4.3, ou
  adresse du site différente de https://zenitude-cdg.github.io (ajouter le secret `ORIGINES_AUTORISEES`).
- Demande en « échec » : le lien « exécution » de l'historique ouvre le journal GitHub (sans montant).
