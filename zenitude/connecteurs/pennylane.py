"""Connecteur Pennylane, lecture seule (lot 18, décision 0011).

Lit, par l'API Pennylane v2, les exercices, les journaux, les comptes, les écritures et leurs lignes d'UN
dossier autorisé (liste blanche), et produit les lignes de `ecritures.csv` et `exercices.csv` au format
exact du jeu de démonstration (interface/demo). Le connecteur est séparé du modèle métier : il ne calcule
rien, il traduit (« changer de source ne réécrit pas le P&L »).

Règles :
- jeton lu par l'appelant (secret GitHub), jamais écrit ni affiché ;
- aucune valeur comptable dans les journaux : le rapport ne contient que des nombres de lignes, des
  statuts et des contrôles oui / non (invariant 8) ;
- un champ absent reste vide, jamais inventé (invariant 1) ; seule exception technique : une écriture
  sans numéro de pièce reçoit l'identifiant `PL<id de l'écriture>`, pour garder ses lignes ensemble ;
- exercices réels Pennylane : jamais janvier-décembre ni douze mois supposés ;
- au plus 25 requêtes par 5 secondes ; reprise sur 429.

Correspondance des champs (relevée sur le dossier de test, workflow « Test structure Pennylane ») :
  date      ledger_entry_lines.date
  journal   ledger_entry_lines.journal.id -> journals.code
  piece     ledger_entry_lines.ledger_entry.id -> ledger_entries.piece_number (à défaut invoice_number)
  compte    ledger_entry_lines.ledger_account.number
  libelle   ledger_entry_lines.label (à défaut ledger_entries.label)
  debit     ledger_entry_lines.debit ; credit : ledger_entry_lines.credit (Decimal, jamais float)
  tiers     numéro du compte quand il commence par 40 ou 41 (compte auxiliaire), sinon vide
  lettrage  comptes 40 et 41 : groupe lu par lettered_ledger_entry_lines.url, identifiant L<plus petit id>
  echeance  absente des écritures Pennylane : vide
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, deque
from datetime import date
from decimal import Decimal, InvalidOperation

BASE = "https://app.pennylane.com/api/external/v2"
COLONNES_ECRITURES = ["dossier", "exercice", "date", "journal", "piece", "compte", "libelle", "debit", "credit",
                      "tiers", "lettrage", "echeance"]
COLONNES_EXERCICES = ["dossier", "debut", "fin", "duree_mois"]

# Liste blanche (décision 0011) : seul le dossier de test peut être lu.
DOSSIERS_AUTORISES = ("PENNY-TEST",)

# Statuts d'écriture (ledger_entries.status). Relevés sur le dossier de test le 24 novembre 2026 :
# complete, validation_needed, accounting_needed, et des écritures sans statut. Ce sont les états de
# traitement comptable de la pièce liée (mêmes valeurs que accounting_status des factures : draft, entry,
# validation_needed, complete, archived). Depuis les changements 2026 de l'API, la liste renvoie toutes les
# écritures, brouillons compris.
STATUTS_VALIDES = ("complete", "archived", "validated", "completed", "posted", "locked", "closed")
STATUTS_BROUILLARD = ("draft", "entry", "validation_needed", "accounting_needed", "pending", "incomplete",
                      "to_validate", "in_progress")
# Écriture sans statut : aucune pièce en attente de traitement (opérations diverses, banque, à-nouveaux...).
# Reprise comme validée ; comptée à part dans le rapport, par type de journal, pour contrôle.
SANS_STATUT = "(sans statut)"
SANS_STATUT_VALIDE = True
INTROUVABLE = "(écriture introuvable)"
MODES = ("valides", "tous")
LIBELLES_MODES = {"valides": "Écritures validées seulement", "tous": "Écritures validées et brouillard"}

PREFIXES_TIERS = ("40", "41")
LIMITE_REQUETES, FENETRE_SECONDES = 25, 5.0


class ErreurPennylane(Exception):
    pass


# --------------------------------------------------------------------------------------------- client

def _ouvrir_http(url, entetes):
    """Envoie la requête GET ; renvoie (code, en-têtes, texte). Remplaçable dans les tests."""
    req = urllib.request.Request(url, headers=entetes, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as rep:
            return rep.status, dict(rep.headers), rep.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read().decode("utf-8", "replace")


class Client:
    """Client minimal de l'API v2 : GET, pagination par curseur, limite de débit, reprise sur 429."""

    def __init__(self, jeton, ouvrir=_ouvrir_http, dormir=time.sleep, horloge=time.monotonic, base=BASE):
        if not jeton:
            raise ErreurPennylane("jeton Pennylane absent")
        self._jeton = jeton
        self._ouvrir, self._dormir, self._horloge = ouvrir, dormir, horloge
        self.base = base.rstrip("/")
        self._instants = deque()
        self.requetes = 0

    def _attendre_tour(self):
        maintenant = self._horloge()
        while self._instants and maintenant - self._instants[0] >= FENETRE_SECONDES:
            self._instants.popleft()
        if len(self._instants) >= LIMITE_REQUETES:
            self._dormir(FENETRE_SECONDES - (maintenant - self._instants[0]) + 0.05)
            maintenant = self._horloge()
            while self._instants and maintenant - self._instants[0] >= FENETRE_SECONDES:
                self._instants.popleft()
        self._instants.append(self._horloge())

    def get_url(self, url):
        # Seules les adresses de l'API Pennylane sont suivies (un lien reçu ne peut pas emmener le jeton ailleurs).
        if not url.startswith(self.base + "/"):
            raise ErreurPennylane("adresse hors de l'API Pennylane refusée")
        entetes = {"Authorization": "Bearer " + self._jeton, "Accept": "application/json",
                   # Comportement 2026 de l'API (seul disponible depuis le 1er juillet 2026), rendu explicite.
                   "X-Use-2026-API-Changes": "true"}
        for essai in range(6):
            self._attendre_tour()
            self.requetes += 1
            code, hdr, texte = self._ouvrir(url, entetes)
            if code == 429:
                attente = hdr.get("Retry-After") or hdr.get("retry-after") or "5"
                try:
                    attente = float(attente)
                except ValueError:
                    attente = 5.0
                self._dormir(min(max(attente, 1.0), 60.0))
                continue
            if code == 401:
                raise ErreurPennylane("jeton refusé (401) : jeton expiré, supprimé ou mal copié")
            if code == 403:
                raise ErreurPennylane("accès interdit (403) : droits du jeton insuffisants")
            if code != 200:
                # Le corps de la réponse n'est jamais affiché (il pourrait contenir des données).
                raise ErreurPennylane(f"réponse inattendue de Pennylane (code {code}) sur {_chemin(url, self.base)}")
            try:
                return json.loads(texte)
            except ValueError:
                raise ErreurPennylane(f"réponse illisible sur {_chemin(url, self.base)}") from None
        raise ErreurPennylane(f"trop de requêtes (429) répétées sur {_chemin(url, self.base)}")

    def get(self, chemin, params=None):
        url = self.base + chemin
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return self.get_url(url)

    def lister(self, chemin, limite=100):
        """Tous les éléments d'une liste paginée par curseur (items, has_more, next_cursor)."""
        curseur, pages = None, 0
        while True:
            params = {"limit": limite}
            if curseur:
                params["cursor"] = curseur
            rep = self.get(chemin, params)
            pages += 1
            if isinstance(rep, list):
                yield from rep
                return
            yield from rep.get("items") or []
            curseur = rep.get("next_cursor")
            if not rep.get("has_more") or not curseur:
                return
            if pages >= 10000:
                raise ErreurPennylane(f"pagination anormale sur {chemin}")


def _chemin(url, base):
    return url[len(base):].split("?")[0] if url.startswith(base) else "(adresse externe)"


# ------------------------------------------------------------------------------------- traduction

def _montant(v):
    if v in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(v))
    except InvalidOperation:
        raise ErreurPennylane("montant illisible dans une ligne d'écriture") from None


def _texte_montant(d):
    return "" if d == 0 else str(d.quantize(Decimal("0.01")))


def _ident(texte):
    """Identifiant conforme à l'invariant 11 ([A-Z0-9_-])."""
    return re.sub(r"[^A-Z0-9_-]", "_", str(texte).upper())


def _mois_entre(debut, fin):
    return (fin.year - debut.year) * 12 + fin.month - debut.month + 1


def _duree_mois(debut, fin):
    """Durée en mois civils couverts par l'exercice réel (un exercice de neuf mois reste de neuf mois)."""
    return _mois_entre(debut, fin)


def _date(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def choisir_exercice(exercices, aujourdhui):
    """Exercice de référence du dossier : celui qui contient la date du jour, sinon le plus récent commencé."""
    contient = [e for e in exercices if e[0] <= aujourdhui <= e[1]]
    if contient:
        return contient[0]
    commences = [e for e in exercices if e[0] <= aujourdhui]
    return max(commences or exercices, key=lambda e: e[0])


def extraire(client, dossier, mode="valides", depuis=None, aujourdhui=None, periode=None):
    """Lit le dossier et renvoie (lignes ecritures.csv, ligne exercices.csv, rapport).

    mode : "valides" (écritures validées seulement) ou "tous" (validées et brouillard).
    depuis : date minimale imposée par le site (frise) ; les écritures antérieures sont comptées.
    periode : (premier jour, dernier jour) de la période d'import choisie dans la page (lot 18b), ou None.
    Le rapport ne contient aucun montant, sauf rapport["brouillard"] (sommes des écritures en brouillard),
    destiné à la base et jamais affiché dans les journaux.
    """
    if dossier not in DOSSIERS_AUTORISES:
        raise ErreurPennylane(f"dossier {dossier} hors de la liste blanche (décision 0011)")
    if mode not in MODES:
        raise ErreurPennylane(f"mode inconnu : {mode} (attendu : {', '.join(MODES)})")
    aujourdhui = aujourdhui or date.today()
    rapport = {"dossier": dossier, "mode": mode, "libelle_mode": LIBELLES_MODES[mode]}

    # Exercices réels
    exercices = []
    for fy in client.lister("/fiscal_years"):
        d, f = _date(fy.get("start")), _date(fy.get("finish"))
        if d and f and d <= f:
            exercices.append((d, f))
    if not exercices:
        raise ErreurPennylane("aucun exercice lisible dans le dossier")
    exercices.sort()
    rapport["exercices"] = len(exercices)

    liste_journaux = list(client.lister("/journals"))
    journaux = {j.get("id"): str(j.get("code") or "").strip() for j in liste_journaux}
    types_journaux = {j.get("id"): str(j.get("type") or "(vide)") for j in liste_journaux}
    comptes_types = Counter(str(a.get("type") or "(vide)") for a in client.lister("/ledger_accounts"))
    rapport["types_de_comptes"] = dict(sorted(comptes_types.items()))

    entetes = {}
    for e in client.lister("/ledger_entries"):
        entetes[e.get("id")] = e
    rapport["ecritures_pennylane"] = len(entetes)

    statuts = Counter()
    statuts_par_type = Counter()
    lignes, ecartees, hors_exercice, anterieures, hors_periode = [], Counter(), 0, 0, 0
    brouillard = {"lignes": 0, "charges": Decimal("0"), "produits": Decimal("0")}
    a_lettrer = []
    for l in client.lister("/ledger_entry_lines"):
        id_entree = (l.get("ledger_entry") or {}).get("id")
        ent = entetes.get(id_entree)
        if ent is None:
            ent, statut = {}, INTROUVABLE
        else:
            statut = str(ent.get("status") or "").strip() or SANS_STATUT
        statuts[statut] += 1
        journal_ligne = (l.get("journal") or {}).get("id") or ent.get("journal_id")
        statuts_par_type[(statut, types_journaux.get(journal_ligne, "(inconnu)"))] += 1
        valide = statut in STATUTS_VALIDES or (statut == SANS_STATUT and SANS_STATUT_VALIDE)
        jour = _date(l.get("date") or ent.get("date"))
        if jour is None:
            ecartees["(date absente)"] += 1
            continue
        if depuis and jour < depuis:
            anterieures += 1
            continue
        if periode and not (periode[0] <= jour <= periode[1]):
            hors_periode += 1
            continue
        exo = next((e for e in exercices if e[0] <= jour <= e[1]), None)
        if exo is None:
            hors_exercice += 1
            continue
        compte = str((l.get("ledger_account") or {}).get("number") or "").strip()
        if not compte:
            ecartees["(compte absent)"] += 1
            continue
        if statut in STATUTS_BROUILLARD:
            brouillard["lignes"] += 1
            solde = _montant(l.get("debit")) - _montant(l.get("credit"))
            if compte.startswith("6"):
                brouillard["charges"] += solde
            elif compte.startswith("7"):
                brouillard["produits"] -= solde
        if mode == "valides" and not valide:
            ecartees[statut] += 1
            continue
        piece = str(ent.get("piece_number") or ent.get("invoice_number") or "").strip()
        if not piece:
            piece = f"PL{ent.get('id') or (l.get('ledger_entry') or {}).get('id') or ''}"
        journal_id = (l.get("journal") or {}).get("id") or ent.get("journal_id") or (ent.get("journal") or {}).get("id")
        ligne = {
            "dossier": dossier,
            "exercice": f"{exo[0].isoformat()}/{exo[1].isoformat()}",
            "date": jour.isoformat(),
            "journal": _ident(journaux.get(journal_id) or "") if journaux.get(journal_id) else "",
            "piece": _ident(piece),
            "compte": compte,
            "libelle": str(l.get("label") or ent.get("label") or "").replace("\n", " ").replace(";", ","),
            "debit": _texte_montant(_montant(l.get("debit"))),
            "credit": _texte_montant(_montant(l.get("credit"))),
            "tiers": _ident(compte) if compte.startswith(PREFIXES_TIERS) else "",
            "lettrage": "",
            "echeance": "",
            "_id": l.get("id"),
        }
        lignes.append(ligne)
        url = (l.get("lettered_ledger_entry_lines") or {}).get("url")
        if url and compte.startswith(PREFIXES_TIERS):
            a_lettrer.append((ligne, url))

    # Lettrage : un appel par groupe (les autres membres du groupe sont reconnus sans nouvel appel).
    groupe_de = {}
    groupes = 0
    for ligne, url in a_lettrer:
        if ligne["_id"] in groupe_de:
            ligne["lettrage"] = groupe_de[ligne["_id"]]
            continue
        rep = client.get_url(url)
        membres = rep if isinstance(rep, list) else (rep.get("items") or [])
        ids = {m.get("id") for m in membres if m.get("id") is not None}
        if not ids:
            continue
        ids.add(ligne["_id"])
        code = "L" + str(min(ids, key=lambda x: (str(type(x)), x)))
        for i in ids:
            groupe_de[i] = code
        ligne["lettrage"] = code
        groupes += 1

    for ligne in lignes:
        ligne.pop("_id", None)
    lignes.sort(key=lambda x: (x["date"], x["piece"], x["compte"]))

    exo = choisir_exercice(exercices, aujourdhui)
    exercice_csv = {"dossier": dossier, "debut": exo[0].isoformat(), "fin": exo[1].isoformat(),
                    "duree_mois": str(_duree_mois(*exo))}

    debit = sum((_montant(x["debit"]) for x in lignes), Decimal("0"))
    credit = sum((_montant(x["credit"]) for x in lignes), Decimal("0"))
    rapport.update({
        "statuts": {s: {"lignes": n, "traitement": _traitement(s),
                        "par_type_de_journal": {tj: k for (st, tj), k in sorted(statuts_par_type.items()) if st == s}}
                    for s, n in sorted(statuts.items())},
        "lignes_lues": sum(statuts.values()),
        "lignes_reprises": len(lignes),
        "lignes_ecartees": dict(sorted(ecartees.items())),
        "lignes_hors_exercice": hors_exercice,
        "lignes_anterieures": anterieures,
        "lignes_hors_periode": hors_periode,
        "periode": [periode[0].isoformat(), periode[1].isoformat()] if periode else None,
        "brouillard": {"lignes": brouillard["lignes"], "masque": mode == "valides",
                       "charges": str(brouillard["charges"].quantize(Decimal("0.01"))),
                       "produits": str(brouillard["produits"].quantize(Decimal("0.01")))},
        "comptes": len({x["compte"] for x in lignes}),
        "comptes_tiers": len({x["compte"] for x in lignes if x["tiers"]}),
        "longueurs_comptes_tiers": dict(sorted(Counter(len(x["compte"]) for x in lignes if x["tiers"]).items())),
        "groupes_lettrage": groupes,
        "equilibre": debit == credit,
        "exercice_retenu": f"{exo[0].isoformat()} au {exo[1].isoformat()}",
        "requetes": client.requetes,
    })
    statuts_inconnus = [s for s in statuts if s not in STATUTS_VALIDES and s not in STATUTS_BROUILLARD
                        and s != SANS_STATUT]
    rapport["statuts_inconnus"] = sorted(statuts_inconnus)
    return lignes, exercice_csv, rapport


def _traitement(statut):
    if statut in STATUTS_VALIDES:
        return "validé"
    if statut == SANS_STATUT:
        return "sans pièce à traiter, repris comme validé" if SANS_STATUT_VALIDE else "non validé"
    if statut in STATUTS_BROUILLARD:
        return "à traiter (brouillard)"
    return "inconnu, traité comme non validé"


def texte_rapport(rapport):
    """Rapport lisible pour les journaux GitHub Actions : nombres et contrôles, aucun montant ni libellé."""
    r = rapport
    out = [f"Dossier : {r['dossier']} - mode : {r['libelle_mode']}",
           f"Exercices lus : {r['exercices']} ; exercice retenu : {r['exercice_retenu']}",
           f"Écritures Pennylane : {r['ecritures_pennylane']} ; lignes lues : {r['lignes_lues']} ; "
           f"lignes reprises : {r['lignes_reprises']}",
           "Statuts des écritures (nombre de lignes) :"]
    for s, v in r["statuts"].items():
        detail = ", ".join(f"{tj} {k}" for tj, k in v.get("par_type_de_journal", {}).items())
        out.append(f"  - {s} : {v['lignes']} ({v['traitement']})" + (f" - par type de journal : {detail}" if detail else ""))
    if r["statuts_inconnus"]:
        out.append("ATTENTION : statut(s) inconnu(s), traité(s) comme non validé(s) : " + ", ".join(r["statuts_inconnus"]))
    for motif, n in r["lignes_ecartees"].items():
        out.append(f"Lignes écartées - {motif} : {n}")
    if r["lignes_anterieures"]:
        out.append(f"Lignes antérieures à la frise du site, non reprises : {r['lignes_anterieures']}")
    if r.get("lignes_hors_periode"):
        out.append(f"Lignes hors de la période d'import ({r['periode'][0]} au {r['periode'][1]}), non reprises : "
                   f"{r['lignes_hors_periode']}")
    b = r.get("brouillard") or {}
    if b:
        out.append(f"Lignes en brouillard dans la période : {b['lignes']} ({'masquées' if b['masque'] else 'reprises'})")
    if r["lignes_hors_exercice"]:
        out.append(f"Lignes hors de tout exercice, non reprises : {r['lignes_hors_exercice']}")
    out.append(f"Comptes mouvementés : {r['comptes']} ; comptes de tiers (40, 41) : {r['comptes_tiers']}"
               f" ; longueurs de leurs numéros : {r['longueurs_comptes_tiers'] or 'aucun'}")
    out.append(f"Types de comptes Pennylane : {r['types_de_comptes']}")
    out.append(f"Groupes de lettrage : {r['groupes_lettrage']}")
    out.append(f"Lignes reprises équilibrées (débits = crédits) : {'oui' if r['equilibre'] else 'NON'}")
    out.append(f"Requêtes envoyées à Pennylane : {r['requetes']}")
    return "\n".join(out)
