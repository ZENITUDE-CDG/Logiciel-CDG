"""Chargement et contrôles du classeur de configuration (docs/configuration.md).

Chaque contrôle renvoie un Constat : code, niveau, onglet, ligne, message.
Une configuration avec au moins une erreur n'est jamais appliquée.
"""
import csv
import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl import load_workbook

from . import formules

HERE = os.path.dirname(__file__)
DATE_REFERENCE_DEFAUT = date(2026, 11, 13)
FREQ_PERIODE = {"quotidienne": 1, "hebdomadaire": 7, "mensuelle": 31}
SECTIONS_CONNUES = {"Page de garde", "Synthèse", "KPI", "Écarts budget", "P&L",
                    "Comparatif scénarios", "Commentaires", "Tableaux de détail"}
ATTRIBUTS_RESIDENCE = {"Activité": "Activité", "Région": "Région", "Marque": "Marque", "Société": "Société"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

ONGLETS_REQUIS = ["Mode_emploi", "Listes", "Referentiel", "Rubriques", "KPI",
                  "Groupes", "Scenarios", "Seuils", "Rapports"]
ONGLET_OPTIONNEL = "Notes"

SCHEMA = {
    "Referentiel": dict(
        entetes=["Identifiant interne", "Nom de la résidence", "Dossier Pennylane (identifiant)", "Société",
                 "Activité", "Région", "Marque", "Date d'ouverture", "Date d'effet", "Date de fin d'effet",
                 "Statut", "Dossier à créer (oui / non)"],
        requis=["Identifiant interne", "Nom de la résidence", "Dossier Pennylane (identifiant)",
                "Activité", "Date d'effet", "Statut", "Dossier à créer (oui / non)"],
        dates=["Date d'ouverture", "Date d'effet", "Date de fin d'effet"],
        eff="Date d'effet", fin="Date de fin d'effet"),
    "Rubriques": dict(
        entetes=["Code rubrique", "Libellé", "Type", "Dossier Pennylane (ou * pour tous)",
                 "Préfixe ou plage de comptes", "Exceptions (comptes exclus, séparés par ;)",
                 "Agrégat de base", "Priorité", "Date d'effet", "Date de fin", "Statut", "Justification"],
        requis=["Code rubrique", "Libellé", "Type", "Dossier Pennylane (ou * pour tous)",
                "Préfixe ou plage de comptes", "Agrégat de base", "Priorité", "Date d'effet", "Statut"],
        dates=["Date d'effet", "Date de fin"], eff="Date d'effet", fin="Date de fin"),
    "KPI": dict(
        entetes=["Code KPI", "Nom", "Définition", "Formule", "Unité", "Agrégation",
                 "Traitement de l'absence de donnée", "Grain", "Temps de référence", "Responsable",
                 "Statut", "Version", "Date d'effet", "Date de fin", "Approbateur"],
        requis=["Code KPI", "Nom", "Formule", "Unité", "Agrégation", "Statut"],
        dates=["Date d'effet", "Date de fin"], eff="Date d'effet", fin="Date de fin"),
    "Groupes": dict(
        entetes=["Code groupe", "Nom", "Type", "Objet regroupé", "Critère 1 (attribut = valeur)",
                 "Critère 2", "Opérateur (ET / OU)", "Inclusions manuelles (codes RES, séparés par ;)",
                 "Exclusions (codes RES, séparés par ;)", "Responsable", "Visibilité",
                 "Date d'effet", "Date de fin", "Statut"],
        requis=["Code groupe", "Nom", "Type", "Statut"],
        dates=["Date d'effet", "Date de fin"], eff="Date d'effet", fin="Date de fin"),
    "Scenarios": dict(
        entetes=["Scénario", "Résidence ou groupe", "Poste (rubrique)", "Période début", "Période fin",
                 "Valeur", "Unité", "Mode (remplacement / variation %)", "Justification", "Auteur",
                 "Date d'effet", "Version de référence"],
        requis=["Scénario", "Résidence ou groupe", "Poste (rubrique)", "Date d'effet"],
        dates=["Période début", "Période fin", "Date d'effet"], eff="Date d'effet", fin=None),
    "Seuils": dict(
        entetes=["Code seuil", "KPI ou rubrique surveillé", "Périmètre (groupe ou résidence)", "Sens",
                 "Seuil (montant ou %)", "Unité", "Seuil d'ancienneté des données (jours)",
                 "Fréquence de la source", "Destinataires internes", "Statut", "Justification"],
        requis=["Code seuil", "Sens", "Statut"],
        dates=[], eff=None, fin=None),
    "Rapports": dict(
        entetes=["Code rapport", "Titre", "Format", "Sections (dans l'ordre, séparées par ;)",
                 "KPI inclus (codes, séparés par ;)", "Périmètre (groupe ou résidence)",
                 "Scénarios comparés (séparés par ;)", "Fréquence d'envoi",
                 "Destinataires (adresses internes ou externes vérifiées)",
                 "Envoi automatique (oui / non)", "Blocage si période non validée (oui / non)", "Statut"],
        requis=["Code rapport", "Titre", "Format", "Sections (dans l'ordre, séparées par ;)",
                "Destinataires (adresses internes ou externes vérifiées)", "Statut"],
        dates=[], eff=None, fin=None),
}

LISTES_COLONNES = ["Activité", "Statut", "Type de groupe", "Agrégation", "Unité", "Scénario",
                   "Fréquence", "Format rapport", "Sens seuil", "Région"]
AGREGATS_BASE = {"CA_HEBERGEMENT", "CA_SERVICES", "PL_CHARGES", "PL_PRODUITS", "EBITDA_AJUSTE", "TRESORERIE"}


@dataclass
class Constat:
    code: str
    niveau: str            # "erreur" | "avertissement"
    onglet: str
    ligne: int | None
    message: str

    def __str__(self):
        lieu = f"{self.onglet}" + (f" ligne {self.ligne}" if self.ligne else "")
        return f"[{self.code}] {lieu} : {self.message}"


@dataclass
class Rapport:
    chemin: str
    empreinte: str = ""
    lignes_lues: dict = field(default_factory=dict)
    constats: list = field(default_factory=list)

    @property
    def erreurs(self):
        return [c for c in self.constats if c.niveau == "erreur"]

    @property
    def avertissements(self):
        return [c for c in self.constats if c.niveau == "avertissement"]

    def codes_erreurs(self):
        return {c.code for c in self.erreurs}

    def codes_avertissements(self):
        return {c.code for c in self.avertissements}

    def resume(self):
        return "\n".join(str(c) for c in self.constats) or "aucun constat"


class _Ctx:
    def __init__(self, rapport, dossiers_connus, date_ref):
        self.r = rapport
        self.dossiers_connus = dossiers_connus
        self.date_ref = date_ref
        self.feuilles = {}     # nom -> liste de dict (ligne, valeurs)
        self.listes = {}       # nom de colonne Listes -> liste de valeurs
        self.invalides = set() # onglets absents ou avec en-tête manquant : contrôles dépendants ignorés

    def err(self, code, onglet, ligne, msg):
        self.r.constats.append(Constat(code, "erreur", onglet, ligne, msg))

    def warn(self, code, onglet, ligne, msg):
        self.r.constats.append(Constat(code, "avertissement", onglet, ligne, msg))

    def liste(self, nom):
        return self.listes.get(nom, [])


def _date(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(v.strip(), fmt).date()
            except ValueError:
                pass
    raise ValueError(v)


def _nombre(v):
    if isinstance(v, bool):
        raise ValueError(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(v.strip().replace(",", "."))
    raise ValueError(v)


def _vide(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def _lire(ctx, chemin):
    wb = load_workbook(chemin)
    noms = set(wb.sheetnames)
    for n in sorted(noms - set(ONGLETS_REQUIS) - {ONGLET_OPTIONNEL}):
        ctx.err("B1", n, None, "onglet non reconnu")
    for n in ONGLETS_REQUIS:
        if n not in noms:
            ctx.err("B1", n, None, "onglet attendu absent ou renommé")
    # Listes
    if "Listes" in noms:
        ws = wb["Listes"]
        entetes = {str(ws.cell(4, c).value).strip(): c for c in range(1, ws.max_column + 1) if ws.cell(4, c).value}
        for nom in LISTES_COLONNES:
            if nom not in entetes:
                ctx.err("B2", "Listes", 4, f"en-tête attendu absent : {nom}")
                continue
            vals, r = [], 5
            while not _vide(ws.cell(r, entetes[nom]).value):
                vals.append(str(ws.cell(r, entetes[nom]).value).strip())
                r += 1
            ctx.listes[nom] = vals
    # Feuilles métier
    for nom, sch in SCHEMA.items():
        if nom not in noms:
            ctx.invalides.add(nom)
            continue
        ws = wb[nom]
        entetes = {}
        for c in range(1, ws.max_column + 1):
            v = ws.cell(4, c).value
            if v is not None:
                entetes[str(v).strip()] = c
        manquants = [h for h in sch["entetes"] if h not in entetes]
        for h in manquants:
            ctx.err("B2", nom, 4, f"en-tête attendu absent ou renommé : « {h} »")
        if manquants:
            ctx.invalides.add(nom)
            ctx.feuilles[nom] = []
            continue
        lignes = []
        for r in range(5, ws.max_row + 1):
            valeurs = {h: ws.cell(r, c).value for h, c in entetes.items() if h in sch["entetes"]}
            if all(_vide(v) for v in valeurs.values()):
                continue
            valeurs["_ligne"] = r
            lignes.append(valeurs)
        ctx.feuilles[nom] = lignes
        ctx.r.lignes_lues[nom] = len(lignes)


def _controles_structure_valeurs(ctx):
    for nom, sch in SCHEMA.items():
        for row in ctx.feuilles.get(nom, []):
            r = row["_ligne"]
            for h in sch["requis"]:
                if _vide(row.get(h)):
                    ctx.err("B4", nom, r, f"valeur obligatoire vide : « {h} »")
            for h in sch["dates"]:
                try:
                    _date(row.get(h))
                except ValueError:
                    ctx.err("B3", nom, r, f"date non reconnue dans « {h} » : {row.get(h)!r}")
            if nom == "Rubriques" and not _vide(row.get("Priorité")):
                try:
                    _nombre(row.get("Priorité"))
                except ValueError:
                    ctx.err("B3", nom, r, "priorité non numérique")
            if nom == "Scenarios" and not _vide(row.get("Valeur")):
                try:
                    _nombre(row.get("Valeur"))
                except ValueError:
                    ctx.err("B26", nom, r, f"valeur non numérique : {row.get('Valeur')!r}")
            if nom == "Seuils" and not _vide(row.get("Seuil (montant ou %)")):
                try:
                    _nombre(row.get("Seuil (montant ou %)"))
                except ValueError:
                    ctx.err("B27", nom, r, "seuil non numérique")


def _dates_periode(row, sch):
    """Période de validité ; une date illisible est traitée comme absente (signalée par B3 ailleurs)."""
    def lire(champ):
        if not champ:
            return None
        try:
            return _date(row.get(champ))
        except ValueError:
            return None
    eff = lire(sch.get("eff"))
    fin = lire(sch.get("fin"))
    return eff or date.min, fin or date.max


def _chevauche(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def _rng(p):
    if "-" in p:
        lo, hi = p.split("-", 1)
    else:
        lo = hi = p
    return lo.strip(), hi.strip()


def _prefixes_se_chevauchent(p1, p2):
    a, b = _rng(p1), _rng(p2)
    L = max(len(x) for x in a + b)
    alo, ahi = a[0].ljust(L, "0"), a[1].ljust(L, "9")
    blo, bhi = b[0].ljust(L, "0"), b[1].ljust(L, "9")
    return not (ahi < blo or bhi < alo)


def _compte_dans(exc, p):
    lo, hi = _rng(p)
    L = max(len(exc), len(lo), len(hi))
    return lo.ljust(L, "0") <= exc.ljust(L, "0") <= hi.ljust(L, "9")


def _periode_valide(p):
    return re.fullmatch(r"\d+", p) is not None or re.fullmatch(r"\d+-\d+", p) is not None


def _doublons_codes(ctx, nom, champ_code, code_erreur):
    vus = {}
    for row in ctx.feuilles.get(nom, []):
        code = row.get(champ_code)
        if _vide(code):
            continue
        code = str(code).strip().upper()
        eff = _dates_periode(row, SCHEMA[nom])[0]
        cle = (code, eff)
        if cle in vus:
            ctx.err(code_erreur, nom, row["_ligne"], f"code « {code} » en double (ligne {vus[cle]})")
        else:
            vus[cle] = row["_ligne"]


def _controles_references(ctx):
    rub = ctx.feuilles.get("Rubriques", [])
    res = ctx.feuilles.get("Referentiel", [])
    kpis = ctx.feuilles.get("KPI", [])
    grp = ctx.feuilles.get("Groupes", [])
    scn = ctx.feuilles.get("Scenarios", [])
    seu = ctx.feuilles.get("Seuils", [])
    rap = ctx.feuilles.get("Rapports", [])

    codes_rub = {str(r["Code rubrique"]).strip().upper() for r in rub if not _vide(r.get("Code rubrique"))}
    if "Rubriques" in ctx.invalides:
        codes_rub = None  # inconnu : ne pas signaler de références en cascade
    codes_kpi = {str(k["Code KPI"]).strip().upper() for k in kpis if not _vide(k.get("Code KPI"))}
    codes_res = {str(r["Identifiant interne"]).strip().upper() for r in res if not _vide(r.get("Identifiant interne"))}
    if "Referentiel" in ctx.invalides:
        codes_res = None
    codes_grp = {str(g["Code groupe"]).strip().upper() for g in grp if not _vide(g.get("Code groupe"))}
    dossiers_ref = {str(r["Dossier Pennylane (identifiant)"]).strip() for r in res
                    if not _vide(r.get("Dossier Pennylane (identifiant)"))}

    # B5 : résidences en double à même date
    _doublons_codes(ctx, "Referentiel", "Identifiant interne", "B5")
    # B8 : codes en double à même date d'effet
    _doublons_codes(ctx, "Rubriques", "Code rubrique", "B8")
    _doublons_codes(ctx, "KPI", "Code KPI", "B8")
    _doublons_codes(ctx, "Groupes", "Code groupe", "B8")

    # B6 : dossiers Pennylane
    for r in res:
        d = str(r.get("Dossier Pennylane (identifiant)") or "").strip()
        if _vide(d):
            continue
        flag = str(r.get("Dossier à créer (oui / non)") or "non").strip().lower()
        if flag not in ("oui", "non"):
            ctx.err("B7", "Referentiel", r["_ligne"], "« Dossier à créer » doit valoir oui ou non")
            continue
        if flag == "oui":
            ctx.warn("W6", "Referentiel", r["_ligne"], f"dossier {d} déclaré à créer dans Pennylane")
        elif d not in ctx.dossiers_connus:
            ctx.err("B6", "Referentiel", r["_ligne"], f"dossier Pennylane inconnu : {d}")
    for r in rub:
        d = str(r.get("Dossier Pennylane (ou * pour tous)") or "").strip()
        if d and d != "*" and d not in ctx.dossiers_connus and d not in dossiers_ref:
            ctx.err("B6", "Rubriques", r["_ligne"], f"dossier Pennylane inconnu : {d}")

    # B7 : valeurs de listes
    for r in res:
        for h, liste in (("Activité", "Activité"), ("Statut", "Statut")):
            v = r.get(h)
            if not _vide(v) and str(v).strip() not in ctx.liste(liste):
                ctx.err("B7", "Referentiel", r["_ligne"], f"« {v} » absent de la liste {liste}")
    for r in rub:
        v = r.get("Statut")
        if not _vide(v) and str(v).strip() not in ctx.liste("Statut"):
            ctx.err("B7", "Rubriques", r["_ligne"], f"statut « {v} » inconnu")
        agr = r.get("Agrégat de base")
        if not _vide(agr) and str(agr).strip() not in AGREGATS_BASE:
            ctx.err("B7", "Rubriques", r["_ligne"], f"agrégat de base inconnu : {agr}")
    for k in kpis:
        for h, liste in (("Unité", "Unité"), ("Agrégation", "Agrégation"), ("Statut", "Statut")):
            v = k.get(h)
            if not _vide(v) and str(v).strip() not in ctx.liste(liste):
                ctx.err("B7", "KPI", k["_ligne"], f"« {v} » absent de la liste {liste}")
    for g in grp:
        for h, liste in (("Type", "Type de groupe"), ("Statut", "Statut")):
            v = g.get(h)
            if not _vide(v) and str(v).strip() not in ctx.liste(liste):
                ctx.err("B7", "Groupes", g["_ligne"], f"« {v} » absent de la liste {liste}")
    for s in seu:
        for h, liste in (("Sens", "Sens seuil"), ("Unité", "Unité"), ("Fréquence de la source", "Fréquence"),
                         ("Statut", "Statut")):
            v = s.get(h)
            if not _vide(v) and str(v).strip() not in ctx.liste(liste):
                ctx.err("B7", "Seuils", s["_ligne"], f"« {v} » absent de la liste {liste}")

    # B9 / B24 / B28 / B29 / B30 : références, scénarios, rapports
    for s in scn:
        poste = str(s.get("Poste (rubrique)") or "").strip().upper()
        if poste and codes_rub is not None and poste not in codes_rub:
            ctx.err("B9", "Scenarios", s["_ligne"], f"rubrique inconnue : {poste}")
        cible = str(s.get("Résidence ou groupe") or "").strip().upper()
        if cible and codes_res is not None and cible not in codes_res and cible not in codes_grp:
            ctx.err("B9", "Scenarios", s["_ligne"], f"résidence ou groupe inconnu : {cible}")
        sc = s.get("Scénario")
        if not _vide(sc) and str(sc).strip() not in ctx.liste("Scénario"):
            ctx.err("B24", "Scenarios", s["_ligne"], f"scénario non listé : {sc}")
    for s in seu:
        cible = str(s.get("KPI ou rubrique surveillé") or "").strip().upper()
        if cible and codes_rub is not None and cible not in codes_kpi and cible not in codes_rub:
            ctx.err("B9", "Seuils", s["_ligne"], f"KPI ou rubrique inconnu : {cible}")
    for rp in rap:
        r = rp["_ligne"]
        for k in _liste_codes(rp.get("KPI inclus (codes, séparés par ;)")):
            if k not in codes_kpi:
                ctx.err("B9", "Rapports", r, f"KPI inconnu : {k}")
        for sct in _liste_codes(rp.get("Sections (dans l'ordre, séparées par ;)"), casse=False):
            if sct not in SECTIONS_CONNUES:
                ctx.err("B28", "Rapports", r, f"section non disponible dans les gabarits : {sct}")
        fmt = rp.get("Format")
        if not _vide(fmt) and str(fmt).strip() not in ctx.liste("Format rapport"):
            ctx.err("B29", "Rapports", r, f"format non pris en charge : {fmt}")
        for sc in _liste_codes(rp.get("Scénarios comparés (séparés par ;)"), casse=False):
            if sc not in ctx.liste("Scénario"):
                ctx.err("B24", "Rapports", r, f"scénario non listé : {sc}")
        for adr in _liste_codes(rp.get("Destinataires (adresses internes ou externes vérifiées)"), casse=False):
            if not EMAIL.match(adr):
                ctx.err("B30", "Rapports", r, f"adresse mal formée : {adr}")


def _liste_codes(v, casse=True):
    if _vide(v):
        return []
    morceaux = [m.strip() for m in str(v).split(";") if m.strip()]
    return [m.upper() for m in morceaux] if casse else morceaux


def _controles_rubriques(ctx):
    rub = ctx.feuilles.get("Rubriques", [])
    for r in rub:
        ln = r["_ligne"]
        pref = str(r.get("Préfixe ou plage de comptes") or "").strip()
        if pref and not _periode_valide(pref):
            ctx.err("B14", "Rubriques", ln, f"préfixe ou plage mal formé : « {pref} »")
        elif pref and "-" in pref:
            lo, hi = _rng(pref)
            if lo > hi:
                ctx.err("B14", "Rubriques", ln, f"plage inversée : {pref}")
        exc = _liste_codes(r.get("Exceptions (comptes exclus, séparés par ;)"), casse=False)
        for e in exc:
            if pref and _periode_valide(pref) and not _compte_dans(e, pref):
                ctx.err("B15", "Rubriques", ln, f"exception « {e} » hors du préfixe « {pref} »")

    # B10 / B11 / B13 : chevauchements et conflits
    for i, a in enumerate(rub):
        pa = str(a.get("Préfixe ou plage de comptes") or "").strip()
        if not pa or not _periode_valide(pa):
            continue
        per_a = _dates_periode(a, SCHEMA["Rubriques"])
        if a.get("Date de fin") and _date(a["Date de fin"]) < per_a[0]:
            ctx.err("B10", "Rubriques", a["_ligne"], "date de fin antérieure à la date d'effet")
        for b in rub[i + 1:]:
            pb = str(b.get("Préfixe ou plage de comptes") or "").strip()
            if not pb or not _periode_valide(pb):
                continue
            per_b = _dates_periode(b, SCHEMA["Rubriques"])
            if not _chevauche(per_a, per_b):
                continue
            if not _prefixes_se_chevauchent(pa, pb):
                continue
            da = str(a.get("Dossier Pennylane (ou * pour tous)") or "").strip()
            db = str(b.get("Dossier Pennylane (ou * pour tous)") or "").strip()
            ca = str(a.get("Code rubrique") or "").strip().upper()
            cb = str(b.get("Code rubrique") or "").strip().upper()
            # B11 : même règle (même code) qui se chevauche dans le temps, même dossier
            if ca == cb and (da == db or "*" in (da, db)):
                ctx.err("B11", "Rubriques", b["_ligne"], f"règle « {ca} » active en même temps que la ligne {a['_ligne']}")
            # B13 : même agrégat, même dossier exact, même priorité, comptes qui se recouvrent
            if (str(a.get("Agrégat de base")) == str(b.get("Agrégat de base"))
                    and da == db
                    and str(a.get("Priorité")) == str(b.get("Priorité"))):
                ctx.err("B13", "Rubriques", b["_ligne"],
                        f"compte classé dans deux rubriques ({ca} et {cb}) pour le même agrégat, "
                        f"même dossier et même priorité")


def _controles_kpi(ctx):
    kpis = ctx.feuilles.get("KPI", [])
    res_ref = {}
    for k in kpis:
        ln = k["_ligne"]
        code = str(k.get("Code KPI") or "").strip().upper()
        statut = str(k.get("Statut") or "").strip()
        if statut == "actif" and _vide(k.get("Date d'effet")):
            ctx.err("B12", "KPI", ln, "KPI actif sans date d'effet")
        if statut == "brouillon" and _vide(k.get("Date d'effet")):
            ctx.warn("W7", "KPI", ln, "KPI brouillon sans date d'effet")
        if statut == "actif" and _vide(k.get("Approbateur")):
            ctx.err("B19", "KPI", ln, "KPI actif sans approbateur")
        if not _vide(k.get("Date de fin")) and not _vide(k.get("Date d'effet")):
            if _date(k["Date de fin"]) < _date(k["Date d'effet"]):
                ctx.err("B10", "KPI", ln, "date de fin antérieure à la date d'effet")
        res_ref[code] = k

    # Unités déclarées des KPI
    unites = {c: str(k.get("Unité") or "").strip() for c, k in res_ref.items()}
    refs_par_kpi = {}
    for k in kpis:
        code = str(k.get("Code KPI") or "").strip().upper()
        formule = k.get("Formule")
        if _vide(formule):
            continue
        try:
            a = formules.analyser(str(formule), formules.MESURES, unites)
        except formules.FormuleError as e:
            ctx.err("B16", "KPI", k["_ligne"], f"formule invalide : {e}")
            continue
        for code_err, msg in a.erreurs:
            ctx.err(code_err, "KPI", k["_ligne"], msg)
        refs_par_kpi[code] = a.refs_kpi
    _cycles(ctx, refs_par_kpi, "B17", "KPI", "référence circulaire entre KPI")

    # W1 : KPI jamais utilisé
    utilises = set()
    for rp in ctx.feuilles.get("Rapports", []):
        utilises.update(_liste_codes(rp.get("KPI inclus (codes, séparés par ;)")))
    for s in ctx.feuilles.get("Seuils", []):
        utilises.add(str(s.get("KPI ou rubrique surveillé") or "").strip().upper())
    for refs in refs_par_kpi.values():
        utilises.update(refs)
    for k in kpis:
        code = str(k.get("Code KPI") or "").strip().upper()
        if code and code not in utilises:
            ctx.warn("W1", "KPI", k["_ligne"], f"KPI « {code} » jamais utilisé")


def _cycles(ctx, graphe, code, onglet, msg):
    etat = {}
    signale = set()

    def visite(n, pile):
        etat[n] = 1
        for v in graphe.get(n, []):
            if v not in graphe:
                continue
            if etat.get(v) == 1:
                if n not in signale:
                    signale.add(n)
                    ctx.err(code, onglet, None, f"{msg} : {' → '.join(pile + [v])}")
            elif v not in etat:
                visite(v, pile + [v])
        etat[n] = 2

    for n in graphe:
        if n not in etat:
            visite(n, [n])


def _controles_groupes(ctx):
    if "Referentiel" in ctx.invalides:
        return
    grp = ctx.feuilles.get("Groupes", [])
    res = ctx.feuilles.get("Referentiel", [])
    codes_res = {str(r["Identifiant interne"]).strip().upper() for r in res if not _vide(r.get("Identifiant interne"))}
    attributs = {}
    for a, col in ATTRIBUTS_RESIDENCE.items():
        attributs[a] = {str(r.get(col)).strip() for r in res if not _vide(r.get(col))}
    graphe = {}
    for g in grp:
        ln = g["_ligne"]
        code = str(g.get("Code groupe") or "").strip().upper()
        typ = str(g.get("Type") or "").strip()
        c1 = str(g.get("Critère 1 (attribut = valeur)") or "").strip()
        c2 = str(g.get("Critère 2") or "").strip()
        membres = _liste_codes(g.get("Inclusions manuelles (codes RES, séparés par ;)"))
        if typ in ("dynamique", "avec exceptions") and _vide(c1):
            ctx.err("B20", "Groupes", ln, "groupe dynamique sans critère")
        if typ == "manuel" and not membres:
            ctx.err("B23", "Groupes", ln, "groupe manuel sans membre")
        for m in membres:
            if m not in codes_res:
                ctx.err("B9", "Groupes", ln, f"résidence inconnue : {m}")
        for crit in (c1, c2):
            if not crit or typ == "composé":
                continue
            if "=" not in crit:
                ctx.err("B21", "Groupes", ln, f"critère mal formé : « {crit} »")
                continue
            attr, val = [x.strip() for x in crit.split("=", 1)]
            if attr not in attributs:
                ctx.err("B21", "Groupes", ln, f"attribut inconnu : {attr}")
            elif val not in attributs[attr]:
                ctx.err("B21", "Groupes", ln, f"aucune résidence avec {attr} = {val}")
        if typ == "composé":
            refs = [x.upper() for x in (c1, c2) if x]
            for r in refs:
                if r not in {str(g2.get("Code groupe") or "").strip().upper() for g2 in grp}:
                    ctx.err("B9", "Groupes", ln, f"groupe inconnu dans la composition : {r}")
            graphe[code] = refs
    _cycles(ctx, graphe, "B22", "Groupes", "cycle entre groupes composés")


def _controles_scenarios(ctx):
    scn = ctx.feuilles.get("Scenarios", [])
    for s in scn:
        ln = s["_ligne"]
        if _vide(s.get("Justification")) or _vide(s.get("Auteur")):
            ctx.err("B25", "Scenarios", ln, "hypothèse sans justification ou sans auteur")
        if not _vide(s.get("Période début")) and not _vide(s.get("Période fin")):
            if _date(s["Période fin"]) < _date(s["Période début"]):
                ctx.err("B10", "Scenarios", ln, "période de fin antérieure au début")
    # B11 : même scénario, même poste, même résidence, périodes qui se chevauchent
    for i, a in enumerate(scn):
        for b in scn[i + 1:]:
            if (str(a.get("Scénario")) == str(b.get("Scénario"))
                    and str(a.get("Poste (rubrique)")) == str(b.get("Poste (rubrique)"))
                    and str(a.get("Résidence ou groupe")) == str(b.get("Résidence ou groupe"))):
                pa = (_date(a.get("Période début")) or date.min, _date(a.get("Période fin")) or date.max)
                pb = (_date(b.get("Période début")) or date.min, _date(b.get("Période fin")) or date.max)
                if _chevauche(pa, pb):
                    ctx.err("B11", "Scenarios", b["_ligne"], "hypothèse en double sur une période qui se chevauche")
    # W5 : Optimiste identique à Référence
    ref = {(str(s.get("Poste (rubrique)")), str(s.get("Résidence ou groupe"))): s
           for s in scn if str(s.get("Scénario")).strip() == "Référence"}
    for s in scn:
        if str(s.get("Scénario")).strip() != "Optimiste":
            continue
        r = ref.get((str(s.get("Poste (rubrique)")), str(s.get("Résidence ou groupe"))))
        if r is not None and _nombre_ou_none(s.get("Valeur")) == _nombre_ou_none(r.get("Valeur")):
            ctx.warn("W5", "Scenarios", s["_ligne"], "Optimiste identique à la Référence")


def _nombre_ou_none(v):
    try:
        return _nombre(v)
    except (ValueError, TypeError):
        return None


def _controles_seuils(ctx):
    for s in ctx.feuilles.get("Seuils", []):
        ln = s["_ligne"]
        if _vide(s.get("Seuil (montant ou %)")):
            ctx.err("B27", "Seuils", ln, "seuil absent")
        if _vide(s.get("KPI ou rubrique surveillé")):
            ctx.err("B27", "Seuils", ln, "indicateur absent")
        if _vide(s.get("Seuil d'ancienneté des données (jours)")) or _vide(s.get("Fréquence de la source")):
            ctx.err("B27", "Seuils", ln, "seuil de fraîcheur sans ancienneté ou sans fréquence de source")
            continue
        freq = str(s["Fréquence de la source"]).strip()
        if freq in FREQ_PERIODE:
            anc = _nombre_ou_none(s["Seuil d'ancienneté des données (jours)"])
            if anc is not None and anc > 3 * FREQ_PERIODE[freq]:
                ctx.warn("W3", "Seuils", ln,
                         f"seuil de {anc:g} jours trop large pour une source {freq} "
                         f"(plus de 3 fois {FREQ_PERIODE[freq]} jour(s))")


def _controles_fin_proche(ctx):
    for r in ctx.feuilles.get("Rubriques", []):
        fin = _date(r.get("Date de fin")) if not _vide(r.get("Date de fin")) else None
        if fin and ctx.date_ref <= fin <= date.fromordinal(ctx.date_ref.toordinal() + 30):
            ctx.warn("W4", "Rubriques", r["_ligne"], f"règle qui prend fin le {fin.isoformat()}")


def _hash(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def _charger_dossiers(chemin):
    out = set()
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#"):
                out.add(ligne)
    return out


def verifier(chemin, dossiers_connus=None, date_reference=DATE_REFERENCE_DEFAUT):
    """Valide un classeur de configuration. Ne modifie jamais le fichier."""
    rapport = Rapport(chemin=str(chemin), empreinte=_hash(chemin))
    if dossiers_connus is None:
        dossiers_connus = _charger_dossiers(os.path.join(HERE, "dossiers_connus_test.txt"))
    ctx = _Ctx(rapport, dossiers_connus, date_reference)
    _lire(ctx, chemin)
    _controles_structure_valeurs(ctx)
    _controles_references(ctx)
    _controles_rubriques(ctx)
    _controles_kpi(ctx)
    _controles_groupes(ctx)
    _controles_scenarios(ctx)
    _controles_seuils(ctx)
    _controles_fin_proche(ctx)
    return rapport
