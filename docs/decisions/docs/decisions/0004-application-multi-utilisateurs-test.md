# 0004 - Application multi-utilisateurs en phase de test (lot 12)

Date : 23 novembre 2026
Statut : proposé, en attente d'approbation

## Contexte
La décision 0001 exclut l'hébergement et la sécurité d'accès. Le lot 12 introduit une base
de données multi-utilisateurs et une connexion. Il faut donc une décision spécifique.

## Décisions
1. Base de test : projet Supabase (PostgreSQL hébergé par un tiers). Données entièrement
   fictives, marquées « fictif ». Aucune donnée réelle (invariant 8).
2. Migration : scripts SQL standard versionnés dans `migrations/`. Pas de fonction propre à
   Supabase, hormis la connexion et les règles d'accès par ligne. Migration possible vers un
   autre PostgreSQL.
3. Écart à CLAUDE.md : l'architecture Django / React n'est pas retenue pour cette phase.
   Les droits sont vérifiés par des règles d'accès par ligne dans PostgreSQL (rôles
   administrateur, collaborateur, lecture seule ; parc par utilisateur). Le contrôle se fait
   donc dans la base et non plus dans un serveur applicatif. L'invariant 9 devra être réexaminé
   avant toute mise en production.
4. Les calculs restent dans le moteur Python. Aucun calcul comptable dans la base.
5. Connexion provisoire par e-mail, inscriptions désactivées, limitée à :
   raphael.bracq@zenitude-groupe.com et benjamin.gagneur@zenitude-groupe.com.
   Le passage à Microsoft 365 ne changera que le mode de connexion.
6. Parcs : un utilisateur voit les résidences et groupes qui lui sont attribués. Une résidence
   ajoutée plus tard à un groupe lui est visible automatiquement. Les administrateurs voient tout.
7. Exécution : moteur Python et interface sur poste de travail ; base de test Supabase.
   Aucun hébergement Zenitude.

## Hors périmètre
Pennylane, EBITDA, budgets, import des KPI, provisions, hébergement définitif, Microsoft 365,
mise en production.

## Conditions
- Aucune clé ni fichier `.env` dans le dépôt (`.gitignore` en place).
- Si un `.env` a déjà été versionné, les clés Supabase sont régénérées.
- Le dépôt est public : décision DSI à prendre (point ouvert).

## Approbations
| Instance | Statut |
| --- | --- |
| Porteur du projet | Demande du 23 novembre 2026 |
| Stack Supabase | À confirmer par écrit par Benjamin Gagneur |
| Contrôle de gestion | À tracer |
| DAF | À tracer |
| DSI | À tracer (hébergement tiers et écart à CLAUDE.md : requis avant tout accès réel) |
