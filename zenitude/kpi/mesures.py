"""Mesures sources du moteur de KPI (lot 6).

Deux familles de mesures, toujours par dossier et par mois (« AAAA-MM ») :

- mesures comptables : agrégats de base de l'onglet Rubriques (CA_HEBERGEMENT, CA_SERVICES,
  PL_CHARGES...), calculées à partir des écritures avec la version de configuration appliquée ;
- mesures d'exploitation : LN_VENDUES, LN_DISPONIBLES, NB_SEJOURS, NUITEES_CLIENTS, COUVERTS_PDJ...
  lues dans un fichier CSV (phase test : données fictives ; plus tard : Mews ou saisie).

Règles (CLAUDE.md, invariants 1 et 2) :
- une absence de donnée n'est jamais zéro : elle produit « non calculable » avec un motif ;
- un mois sans aucune écriture pour un dossier est un mois sans donnée comptable ;
- un compte de classe 6 ou 7 mouvementé et non classé (P1) rend toutes les mesures comptables
  du dossier non calculables sur la période : on ne sait pas dans quelle mesure il tomberait.
"""
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from zenitude.config import publication

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"]


@dataclass(frozen=True)
class NonCalculable:
    """Valeur absente : jamais remplacée par zéro."""
    motif: str

    def __str__(self):
        return f"non calculable : {self.motif}"


def libelle_mois(mois):
    annee, m = mois.split("-")
    return f"{MOIS_FR[int(m) - 1]} {annee}"


def liste_mois(debut, fin):
    """Mois « AAAA-MM » de debut à fin inclus (dates ou chaînes AAAA-MM)."""
    if isinstance(debut, str):
        debut = date(int(debut[:4]), int(debut[5:7]), 1)
    if isinstance(fin, str):
        fin = date(int(fin[:4]), int(fin[5:7]), 1)
    d = date(debut.year, debut.month, 1)
    out = []
    while d <= fin:
        out.append(f"{d.year:04d}-{d.month:02d}")
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def bornes(mois):
    """Premier et dernier jour couverts par une liste de mois."""
    a, m = int(mois[0][:4]), int(mois[0][5:7])
    debut = date(a, m, 1)
    a, m = int(mois[-1][:4]), int(mois[-1][5:7])
    fin = date(a + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return debut, fin


def charger_exploitation(chemin_csv):
    """CSV « dossier;mois;mesure;valeur;source ». Retourne {(dossier, mois, mesure): Decimal}.

    Une valeur vide est une absence (la ligne est ignorée), jamais un zéro.
    Une valeur non numérique ou un doublon bloque le chargement.
    """
    donnees = {}
    with open(chemin_csv, encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f, delimiter=";"), start=2):
            brut = (r.get("valeur") or "").strip()
            if brut == "":
                continue
            try:
                v = Decimal(brut.replace(",", "."))
            except InvalidOperation:
                raise ValueError(f"{chemin_csv}, ligne {i} : valeur non numérique « {brut} »")
            cle = (r["dossier"].strip(), r["mois"].strip(), r["mesure"].strip().upper())
            if cle in donnees:
                raise ValueError(f"{chemin_csv}, ligne {i} : doublon {cle}")
            donnees[cle] = v
    return donnees


class Source:
    """Fournit la somme d'une mesure sur un périmètre (dossiers × mois)."""

    def __init__(self, rubriques, ecritures, exploitation):
        self.rubriques = rubriques
        self.ecritures = ecritures
        self.exploitation = exploitation
        self.comptables = {str(r.get("Agrégat de base") or "").strip() for r in rubriques
                           if str(r.get("Agrégat de base") or "").strip()}
        self._cache = {}

    # --- comptabilité -----------------------------------------------------------
    def _comptable(self, dossier, mois):
        """{mois: {agrégat: Decimal}}, mois couverts, comptes non classés — pour un dossier."""
        cle = (dossier, tuple(mois))
        if cle in self._cache:
            return self._cache[cle]
        debut, fin = bornes(mois)
        par_mois, couverts, non_classes, classes = {}, set(), set(), {}
        for e in self.ecritures:
            if e["dossier"] != dossier:
                continue
            m = e["date"][:7]
            if m not in mois:
                continue
            couverts.add(m)
            compte = e["compte"]
            if compte[:1] not in ("6", "7"):
                continue
            if compte not in classes:
                classes[compte] = publication._classer(compte, self.rubriques, dossier, debut, fin)
            r = classes[compte]
            if r is None:
                non_classes.add(compte)
                continue
            d = Decimal(e["debit"] or "0")
            k = Decimal(e["credit"] or "0")
            agr = str(r["Agrégat de base"]).strip()
            montant = (d - k) if compte[:1] == "6" else (k - d)
            par_mois.setdefault(m, {})
            par_mois[m][agr] = par_mois[m].get(agr, Decimal("0")) + montant
        res = (par_mois, couverts, sorted(non_classes))
        self._cache[cle] = res
        return res

    # --- interface ----------------------------------------------------------------
    def somme(self, mesure, dossiers, mois):
        """Somme de la mesure sur les dossiers et les mois, ou NonCalculable avec motif."""
        total = Decimal("0")
        manques = []
        for dossier in dossiers:
            if mesure in self.comptables:
                par_mois, couverts, non_classes = self._comptable(dossier, mois)
                if non_classes:
                    return NonCalculable(
                        f"comptes non classés (P1) : {', '.join(non_classes)}, dossier {dossier}")
                absents = [m for m in mois if m not in couverts]
                if absents:
                    manques.append((dossier, absents))
                    continue
                for m in mois:
                    # Mois couvert par des écritures mais sans mouvement sur cet agrégat :
                    # le compte n'a pas bougé, c'est un vrai zéro comptable.
                    total += par_mois.get(m, {}).get(mesure, Decimal("0"))
            else:
                absents = [m for m in mois if (dossier, m, mesure) not in self.exploitation]
                if absents:
                    manques.append((dossier, absents))
                    continue
                for m in mois:
                    total += self.exploitation[(dossier, m, mesure)]
        if manques:
            details = "; ".join(f"dossier {d}, {', '.join(libelle_mois(m) for m in ms)}"
                                for d, ms in manques)
            return NonCalculable(f"donnée manquante : {mesure}, {details}")
        return total
