# Zenitude - Pilotage (phase test)

Lot 1 : chargement et validation du classeur de configuration.

## Installation

    pip install -r requirements.txt

## Vérifier un classeur

    python -m zenitude.config check config_modele/Zenitude_Configuration_modele.xlsx

Le code de sortie est 0 si le classeur est valide, 1 s'il est refusé.

## Rapport de chargement exportable

    python -m zenitude.config check <fichier.xlsx> --md
    python -m zenitude.config check <fichier.xlsx> --json

## Aperçu des impacts entre deux versions

    python -m zenitude.config impact <ancienne.xlsx> <nouvelle.xlsx>
    python -m zenitude.config impact <ancienne.xlsx> <nouvelle.xlsx> --json

Code de sortie 1 si la nouvelle version est refusée.

## Données synthétiques (lot 3)

    python tests/generer_ecritures.py tests/fixtures

Écritures fictives sur le plan comptable général (`config_modele/pcg_reference.csv`), trois dossiers
dont un exercice décalé et un exercice de neuf mois. Les montants sont fictifs.

## Versions : dépôt, approbation, application, retour arrière

    python -m zenitude.config versions <dossier_store> deposer <classeur.xlsx> <auteur>
    python -m zenitude.config versions <dossier_store> approuver <vid> <approbateur>
    python -m zenitude.config versions <dossier_store> appliquer <vid> <auteur>
    python -m zenitude.config versions <dossier_store> revenir <vid> <auteur>
    python -m zenitude.config versions <dossier_store> publier <dossier> <ecritures.csv> <exercices.csv> <auteur>
    python -m zenitude.config versions <dossier_store> statut

Code de sortie 1 en cas de refus, avec le motif sur la sortie d'erreur.

## Publication du compte de résultat (lot 5)

Calcule le CA hébergement, le CA services, les charges et le résultat d'un dossier et de son exercice,
avec la version courante. Refusée si un compte de classe 6 ou 7 n'est pas classé (P1).
L'instantané est figé dans `publications/<id>.json`, avec son empreinte.

Configuration de test complète (comptes PCG des écritures synthétiques) :

    python tests/generer_config_complete.py config_modele/Zenitude_Configuration_modele.xlsx tests/fixtures tests/fixtures/ecritures_synthetiques.csv

## Démonstration

    sh demo.sh

Déroule le dépôt, l'approbation, l'application, la publication et l'historique sur les données fictives.

## Maquette du site (à ouvrir dans un navigateur)

    python maquette/generer_maquette.py maquette/index.html

Page HTML autonome, données fictives issues du moteur réel. Aucune fonction réelle hors calculs et contrôles.

## Tests

    python -m pytest

Les 70 fichiers de test sont dans `tests/fixtures/`. Ils se régénèrent à partir du modèle :

    python tests/generer_fixtures.py config_modele/Zenitude_Configuration_modele.xlsx tests_out

## Documents

- `docs/configuration.md` : format du classeur, grammaire des formules, contrôles.
- `docs/tests_configuration.md` : cas de test.
- `docs/decisions/` : décisions tracées.
- `CLAUDE.md` : règles de travail et invariants.
