"""Lot 18 (décision 0011) : jeu de données = démonstration + dossier Pennylane de test.

Le moteur lit un dossier de fichiers (configuration.xlsx, ecritures.csv, exercices.csv, mesures.csv).
Ce module en fabrique une copie TEMPORAIRE (jamais dans le dépôt) : les fichiers de démonstration
inchangés, plus les lignes du dossier de test lues par le connecteur, plus, dans la copie de la
configuration, la fiche de la résidence de test (onglet Referentiel) et le classement provisoire de ses
comptes non classés (onglet Rubriques).

Garde-fous :
- les huit résidences de démonstration gardent leurs écritures et leur classement : une rubrique
  provisoire ne couvre qu'un préfixe qu'aucune rubrique existante ne couvre déjà pour ces comptes, donc
  aucun compte de démonstration ne change de rubrique (règle du préfixe le plus long) ;
- les écritures du dossier de test antérieures au premier mois de la démonstration ne sont pas reprises
  (la frise du site, la trésorerie et les dates d'effet des rubriques commencent là) ; elles sont comptées
  dans le rapport ;
- rien n'est écrit hors du dossier temporaire.
"""
import csv
import os
import shutil
from datetime import date, datetime

import openpyxl

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCG_REFERENCE = os.path.join(RACINE, "config_modele", "pcg_reference.csv")

DOSSIER_TEST = "PENNY-TEST"
FICHE_TEST = {
    "Identifiant interne": "RES-TEST",
    "Nom de la résidence": "Dossier Pennylane de test",
    "Dossier Pennylane (identifiant)": DOSSIER_TEST,
    "Société": "Dossier de test Pennylane (sans donnée confidentielle)",
    "Activité": "Hôtellerie",
    "Région": "Test",
    "Marque": "Test",
    "Date d'ouverture": datetime(2025, 1, 1),
    "Date d'effet": datetime(2025, 1, 1),
    "Date de fin d'effet": None,
    "Statut": "actif",
    "Dossier à créer (oui / non)": "oui",
}
DATE_EFFET_PROVISOIRE = datetime(2025, 1, 1)


def _lire_csv(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _ecrire_csv(chemin, colonnes, lignes):
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def debut_frise(demo):
    """Premier jour du premier mois des écritures de démonstration."""
    premiere = min(e["date"] for e in _lire_csv(os.path.join(demo, "ecritures.csv")))
    return date(int(premiere[:4]), int(premiere[5:7]), 1)


def _pcg():
    out = {}
    with open(PCG_REFERENCE, encoding="utf-8") as f:
        lignes = [l for l in f if not l.startswith("#")]
    for r in csv.DictReader(lignes, delimiter=";"):
        out[r["compte"].strip()] = r["libelle"].strip()
    return out


def _entetes(ws):
    """Ligne d'en-têtes (celle qui contient « Code rubrique » ou « Identifiant interne ») et colonnes."""
    for row in ws.iter_rows(min_row=1, max_row=10):
        valeurs = [str(c.value).strip() if c.value is not None else "" for c in row]
        if "Code rubrique" in valeurs or "Identifiant interne" in valeurs:
            return row[0].row, {v: i + 1 for i, v in enumerate(valeurs) if v}
    raise ValueError(f"en-têtes introuvables dans l'onglet {ws.title}")


def _premiere_ligne_libre(ws, ligne_entete):
    r = ligne_entete + 1
    while ws.cell(row=r, column=1).value not in (None, ""):
        r += 1
    return r


def _prefixes_existants(ws, ligne_entete, col):
    out = []
    for r in range(ligne_entete + 1, ws.max_row + 1):
        if ws.cell(row=r, column=1).value in (None, ""):
            continue
        p = str(ws.cell(row=r, column=col["Préfixe ou plage de comptes"]).value or "").strip()
        statut = str(ws.cell(row=r, column=col["Statut"]).value or "").strip()
        dossier = str(ws.cell(row=r, column=col["Dossier Pennylane (ou * pour tous)"]).value or "").strip()
        if p and statut == "actif" and dossier in ("*", DOSSIER_TEST):
            out.append(p)
    return out


def classement_provisoire(comptes, prefixes_existants):
    """Rubriques provisoires pour les comptes de classe 6 ou 7 qu'aucun préfixe existant ne couvre.

    Préfixe retenu : le plus long compte du PCG de référence qui commence le numéro (au moins 3 chiffres),
    sinon les 3 premiers chiffres. Agrégat : classe 6 -> PL_CHARGES ; 706 -> CA_HEBERGEMENT ; autre classe 7
    -> CA_SERVICES (provisoire, à valider par le contrôle de gestion).
    """
    pcg = _pcg()
    nouvelles = {}
    for compte in sorted(comptes):
        if compte[:1] not in ("6", "7"):
            continue
        if any(compte.startswith(p) for p in prefixes_existants + list(nouvelles)):
            continue
        candidats = [k for k in pcg if len(k) >= 3 and k.isdigit() and compte.startswith(k)]
        prefixe = max(candidats, key=len) if candidats else compte[:3]
        if not prefixe.isdigit():
            prefixe = "".join(ch for ch in compte if ch.isdigit())[:3]
        if not prefixe or prefixe in nouvelles:
            continue
        if compte[:1] == "6":
            agregat = "PL_CHARGES"
        elif prefixe.startswith("706"):
            agregat = "CA_HEBERGEMENT"
        else:
            agregat = "CA_SERVICES"
        nouvelles[prefixe] = {"Code rubrique": f"PROV-{prefixe}",
                              "Libellé": f"Provisoire lot 18 : {pcg.get(prefixe, 'compte ' + prefixe)}",
                              "Type": "charge" if compte[:1] == "6" else "produit",
                              "Dossier Pennylane (ou * pour tous)": "*",
                              "Préfixe ou plage de comptes": prefixe,
                              "Exceptions (comptes exclus, séparés par ;)": None,
                              "Agrégat de base": agregat, "Priorité": 1,
                              "Date d'effet": DATE_EFFET_PROVISOIRE, "Date de fin": None, "Statut": "actif",
                              "Justification": "Classement provisoire du dossier de test (lot 18), à valider"}
    return list(nouvelles.values())


def _ecrire_ligne(ws, ligne, col, valeurs):
    for nom, v in valeurs.items():
        if nom in col:
            ws.cell(row=ligne, column=col[nom], value=v)


def assembler(demo, dest, lignes_test, exercice_test):
    """Écrit dans dest la démonstration + le dossier de test. Renvoie la liste des préfixes provisoires."""
    os.makedirs(dest, exist_ok=True)
    for nom in ("mesures.csv",):
        shutil.copyfile(os.path.join(demo, nom), os.path.join(dest, nom))

    ecritures = _lire_csv(os.path.join(demo, "ecritures.csv"))
    colonnes = list(ecritures[0].keys()) if ecritures else []
    _ecrire_csv(os.path.join(dest, "ecritures.csv"), colonnes, ecritures + list(lignes_test))
    exercices = _lire_csv(os.path.join(demo, "exercices.csv"))
    _ecrire_csv(os.path.join(dest, "exercices.csv"), ["dossier", "debut", "fin", "duree_mois"],
                exercices + [exercice_test])

    wb = openpyxl.load_workbook(os.path.join(demo, "configuration.xlsx"))
    ws = wb["Referentiel"]
    l0, col = _entetes(ws)
    _ecrire_ligne(ws, _premiere_ligne_libre(ws, l0), col, FICHE_TEST)

    ws = wb["Rubriques"]
    l0, col = _entetes(ws)
    comptes = {x["compte"] for x in lignes_test}
    nouvelles = classement_provisoire(comptes, _prefixes_existants(ws, l0, col))
    for rub in nouvelles:
        _ecrire_ligne(ws, _premiere_ligne_libre(ws, l0), col, rub)
    wb.save(os.path.join(dest, "configuration.xlsx"))
    return [r["Préfixe ou plage de comptes"] for r in nouvelles]
