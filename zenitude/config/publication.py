"""Publication du compte de résultat d'une résidence (lot 5).

Calcul à partir des écritures, de la version de configuration applicable et du contrôle P1.
Refus si un compte de classe 6 ou 7 mouvementé n'est pas classé.
Chaque publication est figée dans un instantané JSON, jamais réécrit.

Conventions :
- charges = débit - crédit sur les comptes de classe 6 ;
- produits = crédit - débit sur les comptes de classe 7 ;
- résultat = CA hébergement + CA services - charges ;
- montants en Decimal, arrondis au centime à la fin uniquement ;
- aucune annualisation : un exercice court reste sur sa durée réelle.

Lot 11 : l'instantané contient aussi le compte de résultat du PCG (système de base, règlement ANC
2022-06, voir zenitude/comptes/pcg.py) et son rapprochement avec le résultat ci-dessus. Un compte non
classé dans ce modèle ne bloque pas la publication du lot 5 : il rend le compte de résultat PCG « bloqué »,
avec la liste des comptes.
"""
import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from . import controles as c
from . import couverture
from ..comptes import pcg


class PublicationBloquee(Exception):
    def __init__(self, non_classes):
        self.non_classes = non_classes
        super().__init__("comptes non classés : " + ", ".join(non_classes))


def _classer(compte, rubriques, dossier, debut, fin):
    """Rubrique active la plus précise pour ce compte, ou None."""
    candidats = []
    for r in rubriques:
        if not couverture._rubrique_couvre_dossier(r, dossier):
            continue
        if not couverture._rubrique_active(r, debut, fin):
            continue
        pref = str(r.get("Préfixe ou plage de comptes") or "").strip()
        if not pref or not c._periode_valide(pref) or not c._compte_dans(compte, pref):
            continue
        exc = c._liste_codes(r.get("Exceptions (comptes exclus, séparés par ;)"), casse=False)
        if any(compte.startswith(e) for e in exc):
            continue
        candidats.append((len(pref), r))
    if not candidats:
        return None
    candidats.sort(key=lambda x: -x[0])
    return candidats[0][1]


def calculer(ecritures, rubriques, dossier, debut, fin):
    """Retourne (montants par agrégat, lignes utilisées). Lève PublicationBloquee si P1 échoue."""
    non_classes = set()
    montants = {"CA_HEBERGEMENT": Decimal("0"), "CA_SERVICES": Decimal("0"), "PL_CHARGES": Decimal("0")}
    utilisees = {}
    for e in ecritures:
        if e["dossier"] != dossier:
            continue
        if e.get("date") and not (debut <= date.fromisoformat(e["date"]) <= fin):
            continue  # écriture hors de l'exercice publié
        compte = e["compte"]
        if compte[:1] not in ("6", "7"):
            continue
        d = Decimal(e["debit"] or "0")
        k = Decimal(e["credit"] or "0")
        if compte[:1] == "6":
            r = _classer(compte, rubriques, dossier, debut, fin)
            if r is None:
                non_classes.add(compte)
                continue
            agr = str(r["Agrégat de base"]).strip()
            montants[agr] = montants.get(agr, Decimal("0")) + (d - k)
        else:
            r = _classer(compte, rubriques, dossier, debut, fin)
            if r is None:
                non_classes.add(compte)
                continue
            agr = str(r["Agrégat de base"]).strip()
            montants[agr] = montants.get(agr, Decimal("0")) + (k - d)
        utilisees[str(r["Code rubrique"]).strip()] = agr
    if non_classes:
        raise PublicationBloquee(sorted(non_classes))
    return montants, utilisees


def _arrondi(v):
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resultat(montants):
    ca = montants["CA_HEBERGEMENT"] + montants["CA_SERVICES"]
    charges = montants["PL_CHARGES"]
    return {
        "CA_HEBERGEMENT": str(_arrondi(montants["CA_HEBERGEMENT"])),
        "CA_SERVICES": str(_arrondi(montants["CA_SERVICES"])),
        "PL_CHARGES": str(_arrondi(charges)),
        "RESULTAT": str(_arrondi(ca - charges)),
    }


def publier(depot, ecritures_csv, exercices_csv, dossier, auteur):
    """Calcule et fige la publication du dossier sur l'exercice, avec la version courante."""
    from .versions import RefusAction
    etat = depot._lire()
    if not etat["courante"]:
        raise RefusAction("aucune version appliquée : publication impossible")
    version = next(v for v in etat["versions"] if v["id"] == etat["courante"])
    classeur = os.path.join(depot.fichiers, version["empreinte"] + ".xlsx")
    rubriques = couverture.charger_rubriques(classeur)
    exercices = couverture.charger_exercices(exercices_csv)
    if dossier not in exercices:
        raise RefusAction(f"exercice inconnu pour {dossier}")
    debut, fin = exercices[dossier]
    ecritures = couverture.charger_ecritures(ecritures_csv)
    try:
        montants, utilisees = calculer(ecritures, rubriques, dossier, debut, fin)
    except PublicationBloquee as e:
        depot._journal_refus(etat, "publication refusée", auteur, dossier, e.non_classes)
        depot._ecrire(etat)
        raise
    lignes = [e for e in ecritures if e["dossier"] == dossier and e["compte"][:1] in ("6", "7")
              and (not e.get("date") or debut <= date.fromisoformat(e["date"]) <= fin)]
    cr = pcg.calculer(ecritures, [dossier], debut, fin)
    if cr["statut"] == "calculé":
        ecart = Decimal(cr["lignes"]["RESULTAT"]) - Decimal(resultat(montants)["RESULTAT"])
        cr["rapprochement"] = {"resultat_publie": resultat(montants)["RESULTAT"],
                               "resultat_pcg": cr["lignes"]["RESULTAT"], "ecart": str(_arrondi(ecart))}
    instantane = {
        "dossier": dossier,
        "exercice": {"debut": debut.isoformat(), "fin": fin.isoformat(),
                     "duree_mois": (fin.year - debut.year) * 12 + fin.month - debut.month + 1},
        "version_config": etat["courante"],
        "empreinte_config": version["empreinte"],
        "rubriques_utilisees": utilisees,
        "resultat": resultat(montants),
        "compte_resultat": cr,
        "empreinte_donnees": hashlib.sha256(
            json.dumps(lignes, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "date": datetime.now().replace(microsecond=0).isoformat(),
        "auteur": auteur,
    }
    pid = f"p{len(etat['publications']) + 1}"
    chemin = os.path.join(depot.dossier, "publications")
    os.makedirs(chemin, exist_ok=True)
    fichier = os.path.join(chemin, pid + ".json")
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(instantane, f, ensure_ascii=False, indent=2, sort_keys=True)
    empreinte = hashlib.sha256(open(fichier, "rb").read()).hexdigest()
    etat["publications"].append({"id": pid, "nom": dossier, "version_config": etat["courante"],
                                 "date": instantane["date"], "auteur": auteur,
                                 "fichier": os.path.basename(fichier), "empreinte": empreinte})
    depot._journal(etat, "publication", auteur, pid)
    depot._ecrire(etat)
    return pid, instantane


def verifier_instantane(depot, pid):
    etat = depot._lire()
    pub = next(p for p in etat["publications"] if p["id"] == pid)
    fichier = os.path.join(depot.dossier, "publications", pub["fichier"])
    return hashlib.sha256(open(fichier, "rb").read()).hexdigest() == pub["empreinte"]
