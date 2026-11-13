#!/bin/sh
# Démonstration du lot 1 à 5 sur données fictives. Aucun accès réseau ni Pennylane.
set -e
STORE=$(mktemp -d)/store
echo "1. Validation du classeur modèle (incomplet)"
python3 -m zenitude.config check config_modele/Zenitude_Configuration_modele.xlsx --md > /dev/null && echo "   valide" || true
echo "2. Tentative de dépôt d'un classeur refusé (rubrique en conflit)"
python3 -m zenitude.config versions "$STORE" deposer tests/fixtures/T-B13-a.xlsx alice || true
echo "3. Dépôt, approbation et application de la configuration complète"
python3 -m zenitude.config versions "$STORE" deposer tests/fixtures/config_complete_v1.xlsx alice
python3 -m zenitude.config versions "$STORE" approuver v1 bob
python3 -m zenitude.config versions "$STORE" appliquer v1 bob
echo "4. Publication du compte de résultat PENNY-1001"
python3 -m zenitude.config versions "$STORE" publier PENNY-1001 tests/fixtures/ecritures_synthetiques.csv tests/fixtures/exercices.csv carol
echo "5. Instantané publié"
cat "$STORE/publications/p1.json"
echo
echo "6. État du dépôt"
python3 -m zenitude.config versions "$STORE" statut | python3 -c "import json,sys; d=json.load(sys.stdin); print('courante:', d['courante']); [print(' -', j['action'], j['auteur'], j['detail']) for j in d['journal']]"
