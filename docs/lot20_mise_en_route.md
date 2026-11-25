# Lot 20 - Mise en route (sans rien installer)

Suivi KPI paramétrable (décision 0014). Deux étapes seulement : pas de secret ni de fonction serveur à changer.
La base n'est PAS remise à zéro. Le lot 19 doit être en place (migration 011 appliquée).

## 1. GitHub : fichiers du lot
Déposer les fichiers de l'archive (glisser-déposer, en respectant les dossiers). Vérifier : onglet **Actions**,
« Tests et publication » avec deux coches vertes, puis « pages build and deployment » terminé.

## 2. Supabase : migration 012
**SQL Editor, New query** : coller tout `migrations/012_suivi_kpi_parametrable.sql`, **Run**.
Résultat attendu : « Success. No rows returned ». Le catalogue de départ (21 données, 9 indicateurs, 3 modèles)
est créé une seule fois ; relancer la migration ne l'écrase jamais.

## 3. Premiers réglages (dans le logiciel, en administrateur)
1. Recharger le site sans le cache (Ctrl+F5).
2. **Import et paramètres**, **Paramètres KPI**, choisir « Groupe Zenitude » dans le ruban.
3. Bloc « Modèles de suivi » : **Attribuer le modèle proposé…** (d'après l'activité), puis corriger à la main les
   résidences qui doivent suivre un autre modèle.
4. Bloc « Contrôles du catalogue » : il doit disparaître (sinon, corriger ce qu'il indique).
5. Ajuster le catalogue si besoin : **Modifier** (libellé, rubrique, modèles, seuil…), **Nouvel indicateur**,
   **Nouvelle donnée**, flèches ↑ ↓ pour l'ordre. Le journal en bas de page garde chaque modification.

## 4. Utilisation mensuelle
- **Données externes**, bloc « Modèle Excel du catalogue » : choisir la période, **Exporter le modèle**. Remplir
  (une feuille par modèle), puis **Choisir le fichier…** pour le redéposer. Ne pas modifier les deux premières
  lignes des feuilles ni l'onglet « Lisez-moi ».
- Le consolidé KPI se dépose toujours directement, comme au lot 19.
- **Tableaux de bord**, **Indicateurs suivis** : les indicateurs du catalogue sur la période de la réglette.

## En cas de problème
- « Migration 012 non appliquée » : étape 2.
- « Export bloqué » : une résidence du périmètre n'a pas de modèle, ou une formule est incohérente (Paramètres KPI).
- Dépôt refusé « donnée … inconnue / désactivée / non suivie » ou « suit le modèle … » : le catalogue ou les
  modèles ont changé depuis l'export ; réexporter le modèle, y recopier les valeurs, redéposer.
