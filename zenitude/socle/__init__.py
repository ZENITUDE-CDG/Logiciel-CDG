"""Socle de données pour Claude (lot 25, décision 0019).

Le logiciel fournit les chiffres réels, complets et standardisés, d'une résidence ou d'un groupe ; Claude
reçoit ce paquet et ne va plus chercher les données dans Pennylane. Les hypothèses, scénarios et
retraitements restent dans les missions (prompts), jamais dans le paquet.

Référence Python du paquet construit par la page (interface/gabarit.html, fonction socleConstruire) :
tests/test_lot25_page.py vérifie que les deux produisent exactement les mêmes fichiers.
"""
from .paquet import CONTROLES, FICHIERS, ENTETE_MISSION, LISEZ_MOI, construire, definition, empreinte, texte_mission  # noqa: F401
