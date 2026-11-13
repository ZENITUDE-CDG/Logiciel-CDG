# 0001 - Approbation du cadrage pour la phase de test

Date : 13 novembre 2026

## Décision

Le cadrage ZENITUDE v0.8 et le lot 1 (chargeur et validateur du classeur de configuration) sont approuvés pour la **phase de test uniquement**.

## Périmètre autorisé

- Données entièrement fictives (dossiers `PENNY-100x`, résidences `RES-00x`). Aucune donnée réelle.
- Exécution sur poste de travail, base locale ou aucune base. Aucun hébergement.
- Aucune connexion à Pennylane, Mews ou un autre système.
- Aucun envoi de rapport par mail.
- Coût nul.

## Hors périmètre de cette décision

- Mise en production, hébergement, sécurité d'accès applicatif.
- Connecteur Pennylane et tout import de données réelles.
- Envois programmés et colonnes différées (destinataire externe, approbation des envois).
- Passage en production de la configuration.

## Approbations

| Instance | Statut |
| --- | --- |
| Porteur du projet | Approuvé pour la phase de test (13 novembre 2026) |
| Contrôle de gestion | À tracer |
| DAF | À tracer |
| DSI | À tracer (requis avant tout accès réel) |

## Conditions

1. Toute donnée réelle est exclue du dépôt, des fixtures, des logs et des sorties de test.
2. Le code respecte les invariants de `CLAUDE.md`.
3. Toute décision de périmètre nouvelle fait l'objet d'un fichier dans ce dossier.
