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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, deque
from datetime import date, datetime, timedelta, timezone
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


class RequeteRefusee(ErreurPennylane):
    """Requête refusée comme invalide (400, 422) : paramètre non accepté (taille de page, filtre)."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


# Lot 18c : vitesse. Pages de 1 000 éléments si Pennylane les accepte (sinon 100), filtre de dates
# demandé à Pennylane (sinon filtrage ici), lectures en parallèle dans la limite de débit, lettrage mémorisé.
TAILLES_PAGE = (1000, 500, 250, 200, 100)
LECTURES_PARALLELES = 5
VALIDITE_LETTRAGE = timedelta(days=7)


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
        self._verrou = threading.Lock()

    def _attendre_tour(self):
        with self._verrou:  # plusieurs lectures en parallèle partagent la même limite de débit
            self.requetes += 1
            self._attendre_tour_seul()

    def _attendre_tour_seul(self):
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
            if code in (400, 404, 422):
                raise RequeteRefusee(f"requête refusée par Pennylane (code {code}) sur {_chemin(url, self.base)}", code)
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

    def tout_lire(self, chemin, filtres=None, taille_connue=None):
        """Toute une liste, en essayant d'abord les grandes pages et le filtre, avec repli automatique.

        taille_connue : taille de page acceptée lors d'une synchronisation précédente, essayée en premier.
        Renvoie (éléments, {"taille_page", "filtre"}) : filtre = True si Pennylane a accepté le filtre.
        """
        tailles = list(TAILLES_PAGE)
        if taille_connue in tailles:
            tailles = [t for t in tailles if t <= taille_connue]
        essais = [(n, filtres) for n in tailles] if filtres else []
        essais += [(n, None) for n in tailles]
        derniere = None
        for taille, f in essais:
            try:
                return list(self.lister(chemin, taille, f)), {"taille_page": taille, "filtre": bool(f)}
            except RequeteRefusee as e:
                derniere = e
        raise derniere

    def journal(self, chemin, depuis_iso):
        """Journal des modifications Pennylane (changelogs) depuis une date (4 semaines au plus).

        Première page avec start_date, suivantes avec le seul curseur (les deux ensemble sont refusés).
        """
        out, curseur, pages = [], None, 0
        while True:
            params = {"limit": 1000}
            if curseur:
                params["cursor"] = curseur
            else:
                params["start_date"] = depuis_iso
            rep = self.get(chemin, params)
            pages += 1
            out.extend(rep if isinstance(rep, list) else (rep.get("items") or []))
            if isinstance(rep, list):
                return out
            curseur = rep.get("next_cursor")
            if not rep.get("has_more") or not curseur or pages >= 1000:
                return out

    def par_ids(self, chemin, ids):
        """Éléments d'une liste par identifiants : filtre « in » par paquets de 100, sinon un par un."""
        ids = sorted(set(ids), key=str)
        out = []
        for k in range(0, len(ids), 100):
            paquet = ids[k:k + 100]
            try:
                out.extend(self.lister(chemin, 100, [{"field": "id", "operator": "in", "value": paquet}]))
            except RequeteRefusee:
                def un(i):
                    try:
                        return self.get(f"{chemin}/{i}")
                    except RequeteRefusee:
                        return None  # supprimé entre-temps
                with ThreadPoolExecutor(max_workers=LECTURES_PARALLELES) as ex:
                    out.extend(x for x in ex.map(un, paquet) if x)
        return out

    def lister(self, chemin, limite=100, filtres=None):
        """Tous les éléments d'une liste paginée par curseur (items, has_more, next_cursor)."""
        curseur, pages = None, 0
        while True:
            params = {"limit": limite}
            if filtres:
                params["filter"] = json.dumps(filtres, separators=(",", ":"))
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


def _filtres_dates(debut, fin):
    f = []
    if debut:
        f.append({"field": "date", "operator": "gteq", "value": debut.isoformat()})
    if fin and fin.year < 9999:
        f.append({"field": "date", "operator": "lteq", "value": fin.isoformat()})
    return f or None


def _date_heure(v):
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


CHAMPS_LIGNE = ("id", "date", "label", "debit", "credit", "updated_at")
CHAMPS_ECRITURE = ("id", "date", "label", "piece_number", "invoice_number", "status", "journal_id", "updated_at")


def reduire_ligne(l):
    """Ligne brute réduite aux champs utiles, pour la conserver entre deux synchronisations (lot 18d)."""
    r = {k: l.get(k) for k in CHAMPS_LIGNE}
    r["ledger_account"] = {"number": (l.get("ledger_account") or {}).get("number")}
    r["journal"] = {"id": (l.get("journal") or {}).get("id")}
    r["ledger_entry"] = {"id": (l.get("ledger_entry") or {}).get("id")}
    lettre = l.get("lettered_ledger_entry_lines") or {}
    r["lettered_ledger_entry_lines"] = {k: lettre[k] for k in ("ids", "url") if k in lettre}
    return r


def reduire_ecriture(e):
    r = {k: e.get(k) for k in CHAMPS_ECRITURE}
    if r.get("journal_id") is None and isinstance(e.get("journal"), dict):
        r["journal_id"] = e["journal"].get("id")
    return r


def _evenements(items, cle):
    """Identifiants modifiés et supprimés d'après un journal des modifications."""
    maj, suppr = set(), set()
    for it in items:
        obj = it.get(cle)
        rid = obj.get("id") if isinstance(obj, dict) else None
        if rid is None:
            rid = it.get("record_id", it.get("id"))
        if rid is None:
            raise ErreurPennylane("journal des modifications illisible")
        op = str(it.get("operation") or it.get("event") or it.get("action") or "").lower()
        if op.startswith("del") or op.startswith("destroy"):
            suppr.add(rid)
            maj.discard(rid)
        else:
            maj.add(rid)
            suppr.discard(rid)
    return maj, suppr


def _dans(jour, bas, haut):
    return jour is not None and (bas is None or jour >= bas) and (haut is None or jour <= haut)


def _bornes(magasin):
    b = (magasin or {}).get("bornes") or [None, None]
    return _date(b[0]) if b[0] else None, _date(b[1]) if b[1] else None


def _valeur(v):
    if isinstance(v, dict):
        v = v.get("amount", v.get("value"))
    return _montant(v)


def _balance_identique(client, lignes, bas, haut, exercices):
    """Compare la balance de Pennylane (débits, crédits par compte) à celle des lignes conservées."""
    debut = bas or min((_date(l.get("date")) for l in lignes if _date(l.get("date"))), default=exercices[0][0])
    fin = haut if haut and haut.year < 9999 else max(e[1] for e in exercices)
    nous = {}
    for l in lignes:
        if not _dans(_date(l.get("date")), debut, fin):
            continue
        n = str((l.get("ledger_account") or {}).get("number") or "").strip()
        d, c = nous.get(n, (Decimal("0"), Decimal("0")))
        nous[n] = (d + _montant(l.get("debit")), c + _montant(l.get("credit")))
    eux, curseur = {}, None
    while True:
        params = {"period_start": debut.isoformat(), "period_end": fin.isoformat(), "limit": 1000}
        if curseur:
            params["cursor"] = curseur
        rep = client.get("/trial_balance", params)
        for it in (rep.get("items") if isinstance(rep, dict) else rep) or []:
            n = str(it.get("number") or it.get("formatted_number") or "").strip()
            d, c = eux.get(n, (Decimal("0"), Decimal("0")))
            eux[n] = (d + _valeur(it.get("debits")), c + _valeur(it.get("credits")))
        curseur = rep.get("next_cursor") if isinstance(rep, dict) else None
        if not (isinstance(rep, dict) and rep.get("has_more") and curseur):
            break
    zero = (Decimal("0"), Decimal("0"))
    ecarts = [n for n in set(nous) | set(eux)
              if abs(nous.get(n, zero)[0] - eux.get(n, zero)[0]) > Decimal("0.01")
              or abs(nous.get(n, zero)[1] - eux.get(n, zero)[1]) > Decimal("0.01")]
    return not ecarts, len(ecarts)


def _increment(client, magasin, exercices, rapport):
    """Applique le journal des modifications aux données conservées. None si la balance ne concorde pas."""
    depuis = magasin["increment_depuis"]
    sb, sh = _bornes(magasin)
    maj_l, sup_l = _evenements(client.journal("/changelogs/ledger_entry_lines", depuis), "ledger_entry_line")
    try:
        maj_e, sup_e = _evenements(client.journal("/changelogs/ledger_entries", depuis), "ledger_entry")
        journal_ecritures = True
    except RequeteRefusee:
        journal_ecritures = False
    lignes = dict(magasin.get("lignes") or {})
    entrees = dict(magasin.get("entrees") or {})
    upsert_l, suppr_l = {}, set(sup_l)
    for i in sup_l:
        lignes.pop(i, None)
    for l in (client.par_ids("/ledger_entry_lines", maj_l) if maj_l else []):
        if _dans(_date(l.get("date")), sb, sh):
            lignes[l["id"]] = upsert_l[l["id"]] = l
        else:
            lignes.pop(l["id"], None)
            suppr_l.add(l["id"])
    upsert_e, suppr_e = {}, set()
    if journal_ecritures:
        suppr_e |= sup_e
        for i in sup_e:
            entrees.pop(i, None)
        a_lire = set(maj_e)
    else:
        nouvelles, _ = client.tout_lire("/ledger_entries", _filtres_dates(sb, sh), magasin.get("taille_page"))
        neuves = {e["id"]: e for e in nouvelles}
        suppr_e |= set(entrees) - set(neuves)
        upsert_e.update(neuves)
        entrees = dict(neuves)
        a_lire = set()
    a_lire |= {(l.get("ledger_entry") or {}).get("id") for l in lignes.values()} - set(entrees) - {None}
    for e in (client.par_ids("/ledger_entries", a_lire) if a_lire else []):
        entrees[e["id"]] = upsert_e[e["id"]] = e
    identique, ecarts = _balance_identique(client, list(lignes.values()), sb, sh, exercices)
    rapport["controle_balance"] = "identique" if identique else f"différente sur {ecarts} compte(s)"
    if not identique:
        return None
    rapport["lecture"] = {"mode": "modifications", "depuis": depuis, "lignes_modifiees": len(upsert_l),
                          "lignes_supprimees": len(suppr_l), "journal_ecritures": journal_ecritures,
                          "taille_page": magasin.get("taille_page") or 100, "filtre_dates": True}
    rapport["_magasin_maj"] = {"mode": "increment", "lignes": {i: reduire_ligne(l) for i, l in upsert_l.items()}, "lignes_suppr": sorted(suppr_l, key=str),
                               "entrees": {i: reduire_ecriture(e) for i, e in upsert_e.items()},
                               "entrees_suppr": sorted(suppr_e, key=str),
                               "bornes": (magasin.get("bornes") or [None, None]),
                               "taille_page": magasin.get("taille_page")}
    return list(lignes.values()), list(entrees.values())


def _lire_donnees(client, magasin, bas, haut, exercices, rapport):
    """Lignes et écritures brutes : par modifications si possible, sinon lecture complète."""
    taille = (magasin or {}).get("taille_page")
    if magasin and magasin.get("increment_depuis"):
        try:
            r = _increment(client, magasin, exercices, rapport)
            if r is not None:
                return r
            rapport["lecture_motif"] = "balance différente de celle de Pennylane : relecture complète"
        except RequeteRefusee:
            rapport["lecture_motif"] = "journal des modifications indisponible : relecture complète"
    elif magasin is not None:
        rapport["lecture_motif"] = magasin.get("motif") or "relecture complète"
    comptes_lus, _ = client.tout_lire("/ledger_accounts", taille_connue=taille)
    rapport["types_de_comptes"] = dict(sorted(Counter(str(a.get("type") or "(vide)") for a in comptes_lus).items()))
    filtres = _filtres_dates(bas, haut)
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_entrees = ex.submit(client.tout_lire, "/ledger_entries", filtres, taille)
        f_lignes = ex.submit(client.tout_lire, "/ledger_entry_lines", filtres, taille)
        liste_entrees, info_e = f_entrees.result()
        liste_lignes, info_l = f_lignes.result()
    taille_ok = min(info_e["taille_page"], info_l["taille_page"])
    rapport["lecture"] = {"mode": "complète", "taille_page": taille_ok,
                          "filtre_dates": bool(filtres) and info_e["filtre"] and info_l["filtre"]}
    rapport["_magasin_maj"] = {"mode": "complet", "lignes": {l["id"]: reduire_ligne(l) for l in liste_lignes},
                               "entrees": {e["id"]: reduire_ecriture(e) for e in liste_entrees},
                               "bornes": [bas.isoformat() if bas else None, haut.isoformat() if haut else None],
                               "taille_page": taille_ok}
    return liste_lignes, liste_entrees


def extraire(client, dossier, mode="valides", depuis=None, aujourdhui=None, periode=None, lettrage_memo=None,
             magasin=None):
    """Lit le dossier et renvoie (lignes ecritures.csv, ligne exercices.csv, rapport).

    mode : "valides" (écritures validées seulement) ou "tous" (validées et brouillard).
    depuis : date minimale imposée par le site (frise) ; les écritures antérieures sont comptées.
    periode : (premier jour, dernier jour) de la période d'import choisie dans la page (lot 18b), ou None.
    lettrage_memo : {id de ligne: {"maj", "groupe", "lu_le"}} déjà connus (lot 18c) ; un groupe n'est redemandé
    que si la ligne a changé (updated_at) ou si le relevé a plus de 7 jours. Les relevés nouveaux sont
    renvoyés dans rapport["_lettrage_a_memoriser"] (jamais affiché).
    magasin : écritures et lignes brutes conservées de la synchronisation précédente (lot 18d) :
    {"lignes": {id: ligne}, "entrees": {id: écriture}, "bornes": [début, fin], "taille_page": n,
     "increment_depuis": date ISO ou None}. Avec increment_depuis, seules les modifications depuis cette date
    sont demandées à Pennylane (journal des modifications), puis la balance de Pennylane est comparée à celle
    des lignes conservées : en cas d'écart, relecture complète automatique. Les changements à conserver sont
    renvoyés dans rapport["_magasin_maj"] (jamais affiché).
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

    liste_journaux, _ = client.tout_lire("/journals", taille_connue=(magasin or {}).get("taille_page"))
    journaux = {j.get("id"): str(j.get("code") or "").strip() for j in liste_journaux}
    types_journaux = {j.get("id"): str(j.get("type") or "(vide)") for j in liste_journaux}
    bas = max([x for x in (depuis, periode[0] if periode else None) if x], default=None)
    haut = periode[1] if periode else None
    liste_lignes, liste_entrees = _lire_donnees(client, magasin, bas, haut, exercices, rapport)
    entetes = {e.get("id"): e for e in liste_entrees}
    rapport["ecritures_pennylane"] = len(entetes)

    statuts = Counter()
    statuts_par_type = Counter()
    lignes, ecartees, hors_exercice, anterieures, hors_periode = [], Counter(), 0, 0, 0
    brouillard = {"lignes": 0, "charges": Decimal("0"), "produits": Decimal("0")}
    a_lettrer, lettrage_direct = [], 0
    for l in liste_lignes:
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
        lettre = l.get("lettered_ledger_entry_lines") or {}
        if compte.startswith(PREFIXES_TIERS):
            if isinstance(lettre.get("ids"), list):  # groupe donné par la ligne elle-même : aucun appel
                ids = [i for i in lettre["ids"] if i is not None]
                ligne["lettrage"] = ("L" + str(min(ids, key=lambda x: (str(type(x)), x)))) if ids else ""
                lettrage_direct += 1
            elif lettre.get("url"):
                a_lettrer.append((ligne, lettre["url"], str(l.get("updated_at") or "")))

    # Lettrage : groupes mémorisés réutilisés ; les autres demandés en parallèle (un appel par groupe, les autres
    # membres du groupe sont reconnus sans nouvel appel).
    memo = lettrage_memo or {}
    maintenant = datetime.now(timezone.utc)
    groupe_de, verrou, a_demander, depuis_memo = {}, threading.Lock(), [], 0
    for ligne, url, maj in a_lettrer:
        m = memo.get(ligne["_id"]) or memo.get(str(ligne["_id"]))
        lu = _date_heure(m.get("lu_le")) if m else None
        if m and maj and m.get("maj") == maj and lu and maintenant - lu < VALIDITE_LETTRAGE:
            ligne["lettrage"] = m.get("groupe") or ""
            depuis_memo += 1
        else:
            a_demander.append((ligne, url, maj))

    def demander(element):
        ligne, url, _ = element
        with verrou:
            if ligne["_id"] in groupe_de:
                return
        rep = client.get_url(url)
        membres = rep if isinstance(rep, list) else (rep.get("items") or [])
        ids = {m.get("id") for m in membres if m.get("id") is not None}
        if not ids:
            with verrou:
                groupe_de.setdefault(ligne["_id"], "")
            return
        ids.add(ligne["_id"])
        code = "L" + str(min(ids, key=lambda x: (str(type(x)), x)))
        with verrou:
            for i in ids:
                groupe_de[i] = code

    with ThreadPoolExecutor(max_workers=LECTURES_PARALLELES) as ex:
        list(ex.map(demander, a_demander))
    a_memoriser = {}
    for ligne, url, maj in a_demander:
        ligne["lettrage"] = groupe_de.get(ligne["_id"], "")
        a_memoriser[ligne["_id"]] = {"maj": maj, "groupe": ligne["lettrage"]}
    rapport["_lettrage_a_memoriser"] = a_memoriser
    rapport["lettrage"] = {"lignes": len(a_lettrer) + lettrage_direct, "depuis_ligne": lettrage_direct,
                           "depuis_memoire": depuis_memo, "demandees": len(a_demander)}

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
        "groupes_lettrage": len({l["lettrage"] for l in lignes if l["lettrage"]}),
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
    if r.get("types_de_comptes"):
        out.append(f"Types de comptes Pennylane : {r['types_de_comptes']}")
    out.append(f"Groupes de lettrage : {r['groupes_lettrage']}")
    lt = r.get("lettrage")
    if lt:
        out.append(f"Lettrage : {lt['lignes']} ligne(s) de tiers, {lt.get('depuis_ligne', 0)} lue(s) sur la ligne, "
                   f"{lt['depuis_memoire']} reprise(s) de la mémoire, {lt['demandees']} demandée(s) à Pennylane")
    lec = r.get("lecture")
    if lec and lec.get("mode") == "modifications":
        out.append(f"Lecture : par modifications depuis {lec['depuis']} : {lec['lignes_modifiees']} ligne(s) modifiée(s) "
                   f"ou ajoutée(s), {lec['lignes_supprimees']} supprimée(s) ; journal des écritures : "
                   f"{'oui' if lec['journal_ecritures'] else 'non (écritures relues)'}")
    elif lec:
        out.append(f"Lecture : complète{' (' + r['lecture_motif'] + ')' if r.get('lecture_motif') else ''} ; pages de "
                   f"{lec['taille_page']} éléments ; filtre de dates appliqué par Pennylane : "
                   f"{'oui' if lec['filtre_dates'] else 'non'}")
    if r.get("controle_balance"):
        out.append(f"Contrôle de la balance Pennylane : {r['controle_balance']}")
    out.append(f"Lignes reprises équilibrées (débits = crédits) : {'oui' if r['equilibre'] else 'NON'}")
    out.append(f"Requêtes envoyées à Pennylane : {r['requetes']}")
    return "\n".join(out)
