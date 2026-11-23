# Zenitude – Pilotage (phase test)

Logiciel de contrôle de gestion des résidences Zenitude. **Données entièrement fictives.**

- Site : `connexion.html` (entrée), `espace.html` (mon parc), `administration.html`, `index.html` (tableau de bord).
- Base de test : Supabase, créée par `scripts/installation_supabase.sql` (voir `docs/lot13_mise_en_route.md` et `docs/lot14_mise_en_route.md`).
- Tout montant est cliquable : formule, éléments du calcul et écritures d'origine.
- Import des KPI mensuels : modèle `modeles/Zenitude_Import_KPI_modele.xlsx` (page Données externes).
- Chiffres : calculés par le moteur Python (dossier `zenitude/`) dans GitHub Actions et publiés dans la base
  (`interface/publier_supabase.py`). La page en ligne ne contient aucune donnée : chacun ne voit que son parc.
- Règles de travail et invariants : `CLAUDE.md`. État du projet : `CONTEXTE.md`. Décisions : `docs/decisions/`.

## Tests et publication

Lancés automatiquement par GitHub à chaque dépôt (onglet **Actions**, « Tests et publication ») :
la suite de tests, puis, sur main, la publication des chiffres dans la base de test
(secret GitHub `SUPABASE_SECRET_KEY`). En local :

```
pip install -r requirements.txt
python -m pytest
```

## Régénérer le tableau de bord

```
python interface/generer_site.py            # index.html en ligne (sans données)
python interface/generer_site.py demo.html  # démonstration complète à ouvrir en local
```
