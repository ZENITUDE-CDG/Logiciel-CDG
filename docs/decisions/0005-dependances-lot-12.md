# 0005 - Dépendances du lot 12

Date : 23 novembre 2026
Statut : à tracer avec la décision 0004 (mêmes instances)

Dépendances ajoutées à `requirements.txt` :
- `psycopg[binary]>=3.1` : connexion à PostgreSQL (base de test Supabase, puis tout autre PostgreSQL).
- `python-dotenv>=1.0` : lecture du fichier `.env` local (jamais versionné).

Aucune autre dépendance. Sans ces paquets ou sans base de test, les tests du lot 12 sont ignorés
et le reste de la suite (238 tests) n'est pas affecté.
