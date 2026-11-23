# 0005 - Dépendances du lot 12

Date : 23 novembre 2026
Statut : approuvé par le porteur du projet (23 novembre 2026) ; à tracer avec la décision 0006

Dépendances ajoutées (CLAUDE.md : « Ne pas installer de dépendance non listée sans l'indiquer ») :

| Dépendance | Où | Rôle |
| --- | --- | --- |
| `psycopg[binary]==3.2.3` | Tests GitHub Actions uniquement (installé par `.github/workflows/tests.yml`) | Connexion des tests à PostgreSQL |
| `@supabase/supabase-js@2.45.4` | Pages `connexion.html`, `espace.html`, `administration.html` (chargé depuis cdn.jsdelivr.net) | Connexion du site à la base de test |
| Image `postgres:16` | Tests GitHub Actions | Base temporaire, jetée après les tests |
| `actions/checkout@v4`, `actions/setup-python@v5` | Tests GitHub Actions | Récupération du dépôt et de Python |
| Police Montserrat (Google Fonts) | Pages du lot 12 | Charte Zenitude ; police de secours Arial |

`requirements.txt` n'est pas modifié : le moteur Python n'utilise aucune de ces dépendances.
Versions figées : une mise à jour se fait par une nouvelle décision.
