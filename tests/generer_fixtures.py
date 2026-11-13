"""Génère les fixtures de test du chargeur de configuration à partir du classeur modèle.

Usage : python generer_fixtures.py <modele.xlsx> <dossier_sortie>
Produit un fichier par cas, et tests/attendus.csv. Les cas marqués A_DEFINIR
dépendent d'une règle non encore modélisée dans le classeur ; ils ne produisent
pas de fichier et doivent être tranchés avant développement.
"""
import csv
import datetime as dt
import os
import sys
from openpyxl import load_workbook

MODELE, SORTIE = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(SORTIE, "tests"), exist_ok=True)
os.makedirs(os.path.join(SORTIE, "tests", "fixtures"), exist_ok=True)


def col_of(ws, header):
    for c in range(1, ws.max_column + 1):
        if ws.cell(4, c).value == header:
            return c
    raise KeyError(f"{ws.title}: en-tête absent : {header}")


def setv(wb, sheet, row, header, value):
    ws = wb[sheet]
    ws.cell(row, col_of(ws, header)).value = value


def next_row(ws):
    r = 5
    while ws.cell(r, 1).value not in (None, ""):
        r += 1
    return r


def append_copy(wb, sheet, src_row, **changes):
    """Ajoute une copie de la ligne src_row (hors colonne Contrôle) avec modifications."""
    ws = wb[sheet]
    new = next_row(ws)
    ctrl = ws.max_column
    for c in range(1, ctrl):
        ws.cell(new, c).value = ws.cell(src_row, c).value
    for header, value in changes.items():
        ws.cell(new, col_of(ws, header)).value = value
    return new


def add_list_value(wb, liste, value):
    ws = wb["Listes"]
    c = col_of(ws, liste)
    r = 5
    while ws.cell(r, c).value not in (None, ""):
        r += 1
    ws.cell(r, c).value = value


D_RUB = "Dossier Pennylane (ou * pour tous)"
PREF = "Préfixe ou plage de comptes"
EXC = "Exceptions (comptes exclus, séparés par ;)"
AGR = "Agrégat de base"
PRIO = "Priorité"
EFF = "Date d'effet"
FIN = "Date de fin"
STAT = "Statut"
CODE_RUB = "Code rubrique"
LIB = "Libellé"
FORM = "Formule"
DATE_EFF_REF = "Date d'effet"

# Chaque cas : (attendu, description, fonction de modification ou None)
# attendu : REFUS:<code> | ACCEPTE | ACCEPTE:<avertissement> | A_DEFINIR:<raison>
CAS = {}


def cas(identifiant, attendu, description, fn=None):
    CAS[identifiant] = (attendu, description, fn)


# 1. Structure
cas("T-B1-a", "REFUS:B1", "Onglet Rubriques renommé", lambda wb: setattr(wb["Rubriques"], "title", "Rubrique"))
cas("T-B1-b", "ACCEPTE", "Onglet Notes ajouté", lambda wb: wb.create_sheet("Notes"))


def b2a(wb):
    setv(wb, "Referentiel", 4, "Date d'effet", "Date effet")


cas("T-B2-a", "REFUS:B2", "En-tête renommé", b2a)


def b2b(wb):
    ws = wb["Rubriques"]
    # Permute les colonnes A et B (en-têtes et valeurs)
    for r in range(4, 9):
        a, b = ws.cell(r, 1).value, ws.cell(r, 2).value
        ws.cell(r, 1).value, ws.cell(r, 2).value = b, a


cas("T-B2-b", "ACCEPTE", "Colonnes permutées, lecture par en-tête", b2b)
cas("T-B3-a", "REFUS:B3", "Texte dans une date", lambda wb: setv(wb, "Referentiel", 5, "Date d'effet", "2026-01"))
cas("T-B3-b", "ACCEPTE", "Date au format texte jj/mm/aaaa reconnu",
    lambda wb: setv(wb, "Referentiel", 5, "Date d'effet", "13/11/2026"))


def b4a(wb):
    ws = wb["Rubriques"]
    ws.cell(9, 1).value = "TEST"
    ws.cell(9, col_of(ws, PREF)).value = "603"


cas("T-B4-a", "REFUS:B4", "Code sans libellé", b4a)


def b4b(wb):
    ws = wb["Rubriques"]
    for c in range(1, 13):
        ws.cell(10, c).value = ws.cell(5, c).value
    ws.cell(10, col_of(ws, CODE_RUB)).value = "AUTRE"
    ws.cell(10, col_of(ws, LIB)).value = "Autres charges (exemple)"
    ws.cell(10, col_of(ws, PREF)).value = "603"
    ws.cell(10, col_of(ws, AGR)).value = "PL_CHARGES"
    ws.cell(10, col_of(ws, PRIO)).value = 3
    ws.cell(10, col_of(ws, EXC)).value = None
    ws.cell(10, col_of(ws, EFF)).value = dt.date(2026, 1, 1)
    ws.cell(10, col_of(ws, FIN)).value = None


cas("T-B4-b", "ACCEPTE", "Ligne vide au milieu des données", b4b)

# 2. Référentiels
cas("T-B5-a", "REFUS:B5", "Doublon de résidence à même date d'effet",
    lambda wb: append_copy(wb, "Referentiel", 5))
cas("T-B5-b", "ACCEPTE", "Même résidence, date d'effet différente",
    lambda wb: append_copy(wb, "Referentiel", 5, **{DATE_EFF_REF: dt.date(2026, 6, 1)}))
cas("T-B6-a", "REFUS:B6", "Dossier Pennylane inconnu, non déclaré à créer",
    lambda wb: setv(wb, "Referentiel", 5, "Dossier Pennylane (identifiant)", "PENNY-9999"))
def b6b(wb):
    setv(wb, "Referentiel", 5, "Dossier Pennylane (identifiant)", "PENNY-1004")
    setv(wb, "Referentiel", 5, "Dossier à créer (oui / non)", "oui")


cas("T-B6-b", "ACCEPTE:W6", "Dossier déclaré à créer, avertissement W6", b6b)
cas("T-B7-a", "REFUS:B7", "Activité absente de Listes",
    lambda wb: setv(wb, "Referentiel", 5, "Activité", "Résidence service"))


def b7b(wb):
    add_list_value(wb, "Activité", "Résidence service")
    setv(wb, "Referentiel", 5, "Activité", "Résidence service")


cas("T-B7-b", "ACCEPTE", "Activité ajoutée à Listes puis utilisée", b7b)


def b8a(wb):
    append_copy(wb, "Rubriques", 5)


cas("T-B8-a", "REFUS:B8", "Rubrique en double à même date", b8a)
cas("T-B8-b", "ACCEPTE", "Rubrique en double à date différente",
    lambda wb: (setv(wb, "Rubriques", 5, FIN, dt.date(2026, 5, 31)),
                append_copy(wb, "Rubriques", 5, **{EFF: dt.date(2026, 6, 1), FIN: None})))


def b9a(wb):
    append_copy(wb, "Scenarios", 5, **{"Poste (rubrique)": "CA-INCONNU", "Période début": dt.date(2026, 1, 1),
                                        "Période fin": dt.date(2026, 12, 31)})


cas("T-B9-a", "REFUS:B9", "Hypothèse sur une rubrique inconnue", b9a)
cas("T-B9-b", "ACCEPTE", "Seuil sur un KPI existant",
    lambda wb: setv(wb, "Seuils", 5, "KPI ou rubrique surveillé", "OCC-HOT"))

# 3. Dates
cas("T-B10-a", "REFUS:B10", "Fin antérieure à l'effet",
    lambda wb: setv(wb, "Rubriques", 8, FIN, dt.date(2025, 12, 31)))
cas("T-B10-b", "ACCEPTE", "Fin égale à l'effet",
    lambda wb: setv(wb, "Rubriques", 8, FIN, dt.date(2026, 1, 1)))


def b11_base(wb):
    setv(wb, "Rubriques", 7, D_RUB, "PENNY-1001")
    setv(wb, "Rubriques", 7, FIN, dt.date(2026, 12, 31))


def b11a(wb):
    b11_base(wb)
    append_copy(wb, "Rubriques", 7, **{EFF: dt.date(2026, 6, 1), FIN: None})


def b11b(wb):
    b11_base(wb)
    setv(wb, "Rubriques", 7, FIN, dt.date(2026, 5, 31))
    append_copy(wb, "Rubriques", 7, **{EFF: dt.date(2026, 6, 1), FIN: None})


cas("T-B11-a", "REFUS:B11", "Deux règles actives qui se chevauchent", b11a)
cas("T-B11-b", "ACCEPTE", "Deux règles successives sans chevauchement", b11b)


def b12a(wb):
    setv(wb, "KPI", 5, "Date d'effet", None)


def b12b(wb):
    setv(wb, "KPI", 6, "Date d'effet", None)


cas("T-B12-a", "REFUS:B12", "KPI actif sans date d'effet", b12a)
cas("T-B12-b", "ACCEPTE:W7", "KPI brouillon sans date d'effet, avertissement W7", b12b)

# 4. Rubriques
cas_b13_base = dict(**{CODE_RUB: "AUTRE-616", LIB: "Autre assurance (exemple)", PREF: "6161", D_RUB: "*",
                       AGR: "PL_CHARGES", PRIO: 1, EFF: dt.date(2026, 1, 1)})
cas("T-B13-a", "REFUS:B13", "Compte dans deux rubriques, même agrégat et priorité",
    lambda wb: append_copy(wb, "Rubriques", 5, **{CODE_RUB: "AUTRE-616", PREF: "6161", PRIO: 1}))
cas("T-B13-b", "ACCEPTE", "Même cas, priorités distinctes",
    lambda wb: append_copy(wb, "Rubriques", 5, **{CODE_RUB: "AUTRE-616", PREF: "6161", PRIO: 2}))
cas("T-B13-c", "ACCEPTE", "Même cas, agrégats différents",
    lambda wb: append_copy(wb, "Rubriques", 5, **{CODE_RUB: "AUTRE-616", PREF: "6161", AGR: "EBITDA_AJUSTE"}))
cas("T-B14-a", "REFUS:B14", "Préfixe avec astérisque", lambda wb: setv(wb, "Rubriques", 5, PREF, "616*"))
cas("T-B14-b", "ACCEPTE", "Plage 616-618", lambda wb: setv(wb, "Rubriques", 5, PREF, "616-618"))
cas("T-B15-a", "REFUS:B15", "Exception hors du préfixe", lambda wb: setv(wb, "Rubriques", 5, EXC, "7063"))
cas("T-B15-b", "ACCEPTE", "Exception incluse dans le préfixe", None)

# 5. KPI
cas("T-B16-a", "REFUS:B16", "Parenthèse manquante",
    lambda wb: setv(wb, "KPI", 5, FORM, "RATIO([LN_VENDUES];[LN_DISPONIBLES]"))
cas("T-B16-b", "ACCEPTE", "Formule valide", None)
cas("T-B16-c", "REFUS:B16", "Fonction non autorisée",
    lambda wb: setv(wb, "KPI", 5, FORM, "MOYENNE([A])"))
cas("T-B16-d", "REFUS:B16", "Caractère interdit dans une mesure",
    lambda wb: setv(wb, "KPI", 6, FORM, "[P&L_CHARGES]"))


def b17a(wb):
    setv(wb, "KPI", 5, "Code KPI", "KPI-A")
    setv(wb, "KPI", 5, FORM, "{KPI-B}+1")
    setv(wb, "KPI", 6, "Code KPI", "KPI-B")
    setv(wb, "KPI", 6, FORM, "{KPI-A}*2")


cas("T-B17-a", "REFUS:B17", "Référence circulaire", b17a)
cas("T-B17-b", "ACCEPTE", "Dépendance sans retour",
    lambda wb: append_copy(wb, "KPI", 6, **{"Code KPI": "KPI-A", FORM: "{OCC-HOT}+1", "Statut": "brouillon",
                                            "Approbateur": None, "Unité": "%"}))


def b18a(wb):
    setv(wb, "KPI", 6, FORM, "SOMME([CA_HEBERGEMENT])+{OCC-HOT}")


def b18b(wb):
    setv(wb, "KPI", 5, FORM, "RATIO([CA_HEBERGEMENT];[LN_VENDUES])")
    setv(wb, "KPI", 5, "Unité", "€")


cas("T-B18-a", "REFUS:B18", "Addition € et %", b18a)
cas("T-B18-b", "ACCEPTE", "Ratio avec unité déclarée", b18b)
cas("T-B19-a", "REFUS:B19", "KPI actif sans approbateur",
    lambda wb: setv(wb, "KPI", 5, "Approbateur", None))
cas("T-B19-b", "ACCEPTE", "KPI brouillon sans approbateur", None)

# 6. Groupes
cas("T-B20-a", "REFUS:B20", "Groupe dynamique sans critère",
    lambda wb: (setv(wb, "Groupes", 5, "Critère 1 (attribut = valeur)", None),
                setv(wb, "Groupes", 5, "Critère 2", None)))
cas("T-B20-b", "ACCEPTE", "Groupe dynamique avec critère", None)
cas("T-B21-a", "REFUS:B21", "Attribut inconnu",
    lambda wb: setv(wb, "Groupes", 5, "Critère 1 (attribut = valeur)", "Marque = Marque Z"))
cas("T-B21-b", "ACCEPTE", "Attribut existant",
    lambda wb: setv(wb, "Groupes", 5, "Critère 1 (attribut = valeur)", "Marque = Marque B"))


def b22a(wb):
    setv(wb, "Groupes", 5, "Code groupe", "GRP-A")
    setv(wb, "Groupes", 5, "Type", "composé")
    setv(wb, "Groupes", 5, "Critère 1 (attribut = valeur)", "GRP-B")
    setv(wb, "Groupes", 5, "Critère 2", None)
    setv(wb, "Groupes", 6, "Code groupe", "GRP-B")
    setv(wb, "Groupes", 6, "Type", "composé")
    setv(wb, "Groupes", 6, "Critère 1 (attribut = valeur)", "GRP-A")
    setv(wb, "Groupes", 6, "Critère 2", None)


def b22b(wb):
    setv(wb, "Groupes", 5, "Code groupe", "GRP-A")
    setv(wb, "Groupes", 5, "Type", "composé")
    setv(wb, "Groupes", 5, "Critère 1 (attribut = valeur)", "GRP-B")
    setv(wb, "Groupes", 5, "Critère 2", None)
    setv(wb, "Groupes", 6, "Code groupe", "GRP-B")


cas("T-B22-a", "REFUS:B22", "Cycle entre groupes composés", b22a)
cas("T-B22-b", "ACCEPTE", "Composition sans cycle", b22b)
cas("T-B23-a", "REFUS:B23", "Groupe manuel sans membre",
    lambda wb: setv(wb, "Groupes", 6, "Inclusions manuelles (codes RES, séparés par ;)", None))
cas("T-B23-b", "ACCEPTE", "Groupe manuel avec membres", None)

# 7. Scénarios et seuils
cas("T-B24-a", "REFUS:B24", "Scénario non listé", lambda wb: setv(wb, "Scenarios", 5, "Scénario", "Pessimiste"))


def b24b(wb):
    add_list_value(wb, "Scénario", "Pessimiste")
    setv(wb, "Scenarios", 5, "Scénario", "Pessimiste")


cas("T-B24-b", "ACCEPTE", "Scénario ajouté à Listes", b24b)
cas("T-B25-a", "REFUS:B25", "Hypothèse sans justification",
    lambda wb: setv(wb, "Scenarios", 5, "Justification", None))
cas("T-B25-b", "ACCEPTE", "Hypothèse justifiée", None)
cas("T-B26-a", "REFUS:B26", "Valeur textuelle", lambda wb: setv(wb, "Scenarios", 5, "Valeur", "dix"))
cas("T-B26-b", "ACCEPTE", "Valeur négative", lambda wb: setv(wb, "Scenarios", 5, "Valeur", -0.05))
cas("T-B27-a", "REFUS:B27", "Seuil sans indicateur",
    lambda wb: setv(wb, "Seuils", 5, "KPI ou rubrique surveillé", None))
cas("T-B27-b", "ACCEPTE", "Seuil avec indicateur", None)

# 8. Rapports
cas("T-B28-a", "REFUS:B28", "Section inconnue",
    lambda wb: setv(wb, "Rapports", 5, "Sections (dans l'ordre, séparées par ;)", "Prévisions détaillées"))
cas("T-B28-b", "ACCEPTE", "Sections du modèle", None)
cas("T-B29-a", "REFUS:B29", "Format non pris en charge", lambda wb: setv(wb, "Rapports", 5, "Format", "Word"))
cas("T-B29-b", "ACCEPTE", "Format PDF", None)
cas("T-B30-a", "REFUS:B30", "Adresse mal formée",
    lambda wb: setv(wb, "Rapports", 5, "Destinataires (adresses internes ou externes vérifiées)", "direction@@exemple"))
cas("T-B30-b", "A_DEFINIR:colonne « externe » et périmètre de diffusion absents du classeur v0.1", "Destinataire externe")
cas("T-B30-c", "ACCEPTE", "Adresse valide", None)
cas("T-B31-a", "A_DEFINIR:approbation des envois absente du classeur v0.1", "Envoi auto sans approbation")
cas("T-B31-b", "A_DEFINIR:approbation des envois absente du classeur v0.1", "Envoi auto approuvé")

# 9. Avertissements
cas("T-W1", "ACCEPTE:W1", "KPI non utilisé",
    lambda wb: append_copy(wb, "KPI", 6, **{"Code KPI": "KPI-ORPHELIN", "Approbateur": "Contrôle de gestion"}))


def w4(wb):
    setv(wb, "Rubriques", 5, FIN, dt.date(2026, 12, 3))


cas("T-W4", "ACCEPTE:W4", "Fin de règle dans moins de 30 jours", w4)


def w5(wb):
    append_copy(wb, "Scenarios", 5, **{"Scénario": "Référence", "Valeur": 0.03, "Justification": "Référence (exemple)"})


cas("T-W5", "ACCEPTE:W5", "Optimiste identique à la Référence", w5)
cas("T-W6", "ACCEPTE:W6", "Dossier à créer déclaré (cas T-B6-b, avertissement W6)", b6b)
cas("T-W2", "A_DEFINIR:dépend des données de test, non du classeur", "Membre sans donnée")
def w3a(wb):
    setv(wb, "Seuils", 5, "Seuil d'ancienneté des données (jours)", 90)
    setv(wb, "Seuils", 5, "Fréquence de la source", "hebdomadaire")


def w3b(wb):
    setv(wb, "Seuils", 5, "Seuil d'ancienneté des données (jours)", 14)
    setv(wb, "Seuils", 5, "Fréquence de la source", "hebdomadaire")


cas("T-W3", "ACCEPTE:W3", "Seuil de 90 jours sur une donnée hebdomadaire (plus de 3 fois la période)", w3a)
cas("T-W3-b", "ACCEPTE", "Seuil de 14 jours sur une donnée hebdomadaire", w3b)
cas("T-B27-c", "REFUS:B27", "Seuil de fraîcheur sans fréquence de source",
    lambda wb: setv(wb, "Seuils", 5, "Fréquence de la source", None))

# 10. Publication et versions : hors chargement
HORS = {
    "T-P1-a": "Publication : données comptables requises", "T-P1-b": "Publication : données comptables requises",
    "T-P2-a": "Publication : données requises", "T-P3-a": "Publication : données requises",
    "T-P4-a": "Publication : données requises", "T-P5-a": "Publication : données requises",
    "T-V-1": "Versions : test d'exécution, pas de fixture", "T-V-2": "Versions : test d'exécution",
    "T-V-3": "Versions : test d'exécution", "T-V-4": "Versions : test d'exécution",
}

# Génération
base_path = MODELE
rows = []
for ident, (attendu, desc, fn) in CAS.items():
    if attendu.startswith("A_DEFINIR"):
        rows.append([ident, attendu, desc, ""])
        continue
    wb = load_workbook(base_path)
    if fn:
        fn(wb)
    fichier = f"fixtures/{ident}.xlsx"
    wb.save(os.path.join(SORTIE, "tests", fichier))
    rows.append([ident, attendu, desc, fichier])
for ident, desc in HORS.items():
    rows.append([ident, "HORS_CHARGEMENT", desc, ""])

with open(os.path.join(SORTIE, "tests", "attendus.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["identifiant", "attendu", "description", "fichier"])
    w.writerows(rows)

ok = sum(1 for r in rows if r[3])
print(f"{len(rows)} cas listés, {ok} fichiers générés, "
      f"{sum(1 for r in rows if r[1].startswith('A_DEFINIR'))} à définir, "
      f"{sum(1 for r in rows if r[1]=='HORS_CHARGEMENT')} hors chargement")
