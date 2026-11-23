# Zenitude – Pilotage (phase test)

Logiciel de contrôle de gestion des résidences Zenitude. **Données entièrement fictives.**

- Site : `connexion.html` (entrée), `espace.html` (mon parc), `administration.html`, `index.html` (tableau de bord).
- Base de test : Supabase, créée par `scripts/installation_supabase.sql` (voir `docs/lot12_mise_en_route.md`).
- Moteur de calcul Python : dossier `zenitude/` (lots 1 à 11).
- Règles de travail et invariants : `CLAUDE.md`. État du projet : `CONTEXTE.md`. Décisions : `docs/decisions/`.

## Tests

Lancés automatiquement par GitHub à chaque dépôt (onglet **Actions**). En local :

```
pip install -r requirements.txt
python -m pytest
```

## Régénérer le tableau de bord

```
python interface/generer_demo.py
python interface/generer_site.py
```
