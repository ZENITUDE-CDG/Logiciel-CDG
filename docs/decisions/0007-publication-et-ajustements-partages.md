# 0007 - Lot 13 : chiffres publiés par GitHub Actions, ajustements partagés, lissage

Date : 23 novembre 2026
Statut : approuvé par le porteur du projet (23 novembre 2026) ; à faire approuver comme les décisions 0004 et 0006

## Contexte
Jusqu'au lot 12, le tableau de bord (`index.html`) contenait les chiffres des huit résidences de
démonstration : toute personne qui ouvrait la page les voyait, quel que soit son parc. Les ajustements
(lot 9) étaient enregistrés dans le navigateur de chacun. Le porteur du projet demande, pour la phase
test : le compte de résultat et les ajustements (provisions, lissage) depuis la base, selon le parc,
sans rien installer sur un poste.

## Décisions
1. **Publication par GitHub Actions.** Modifie le point 7 de la décision 0006. Après les tests, sur la
   branche main uniquement, GitHub Actions lance `interface/publier_supabase.py` : le moteur Python
   calcule les chiffres (comme pour le site) et les écrit dans la base de test Supabase
   (`donnees_communes`, `donnees_residences`, migration 004). La clé secrète Supabase est gardée dans les
   secrets GitHub (`SUPABASE_SECRET_KEY`), jamais dans le dépôt, les journaux ou la page. Les tests, eux,
   n'utilisent toujours aucun secret et ne touchent jamais Supabase.
2. **La page en ligne ne contient plus aucune donnée.** Après la connexion, elle lit les données communes
   (paramètres, sans aucune donnée de résidence) et celles des seules résidences du parc ; la base filtre
   (règles par ligne). La démonstration complète reste disponible en local pour les tests
   (`python interface/generer_site.py demo.html`).
3. **Les calculs restent dans le moteur Python.** La base stocke des résultats. La page recompose les
   données du site à partir des morceaux publiés ; un test vérifie qu'elle obtient exactement les mêmes
   données que le générateur (`tests/test_lot13_page.py`).
4. **Ajustements partagés, actifs dès leur création.** Ajustements et comptes simulés sont enregistrés
   dans la base (`ajustements`, `comptes_simules`). Pas de validation par une seconde personne. La base
   trace l'auteur et le dernier modificateur.
5. **Droits des ajustements** (vérifiés dans la base) : lecture si toutes les résidences concernées sont
   dans le parc, ou si l'ajustement porte sur toutes les résidences ; un collaborateur crée, modifie et
   supprime les ajustements de ses résidences ; seul l'administrateur gère un ajustement « toutes les
   résidences » (il s'applique aussi aux résidences ajoutées plus tard) ; la lecture seule ne modifie rien.
   Pour un collaborateur, « toutes les résidences » enregistre la liste des résidences de son parc.
6. **Lissage** (nouveau type d'ajustement) : le montant réel des comptes qui commencent par un numéro donné,
   sur des mois d'origine, est retiré de ces mois et réparti à parts égales (au centime, le reste sur les
   premiers mois) sur des mois de répartition. Calculé sur la comptabilité réelle. Le total de chaque compte
   sur l'ensemble des mois concernés ne change pas. Un mois de répartition sans écriture rend le lissage non
   calculable pour la résidence (invariant 1), jamais zéro. Calcul dans la page, comme les autres
   ajustements (décision 0002), sans formule saisie (invariant 6).
7. **Nettoyage des résidences de test.** La base de test contient les huit résidences de démonstration
   (RES-001 à RES-008, dossiers DEMO-2001 à DEMO-2008). RES-901, RES-902 et le groupe pilote sont supprimés.
   Démonstration : Raphael administrateur (tout), Benjamin collaborateur avec le groupe GRP-SENIORS
   (RES-003, RES-004, RES-005).
8. **Garde-fous de la publication** : seules les résidences déjà créées dans la base reçoivent des données ;
   la publication s'arrête si l'une d'elles est marquée réelle ; les tables de données refusent toute ligne
   marquée réelle (`CHECK (fictif)`) pendant la phase test (invariant 8).

## Dépendances
- `psycopg[binary]` ajouté à `requirements.txt` (déjà prévu par la décision 0005, pour les tests de droits).
- GitHub Actions installe en plus Playwright et Chromium pour les tests de page (outil de test seulement).
- La publication n'utilise que la bibliothèque standard de Python.

## Limites
- Les publications figées ne tiennent pas compte des ajustements (inchangé, invariant 5).
- Le calculateur d'ajustements reste dans la page (décision 0002) ; à remplacer par le backend en production.
- La publication écrase les chiffres de démonstration à chaque dépôt sur main ; pas d'historique des
  publications dans la base (les publications du moteur restent figées et vérifiables par leur empreinte).
- Dépôt public : décision DSI toujours attendue.

## Approbations
| Instance | Statut |
| --- | --- |
| Porteur du projet | Approuvé le 23/11/2026 (envoi par GitHub Actions, ajustements actifs dès leur création) |
| Benjamin Gagneur | À tracer |
| Contrôle de gestion | À tracer |
| DAF | À tracer |
| DSI | À tracer (clé secrète dans les secrets GitHub, écriture automatique dans la base de test) |
