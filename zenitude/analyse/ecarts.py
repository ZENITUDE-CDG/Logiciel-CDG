"""Lots 28 à 30 - Analyse des écarts : référence Python des calculs de la page « Analyse des écarts ».

Décision : `docs/decisions/0022-analyse-des-ecarts.md`. Règles : `docs/analyse_ecarts.md`.

La page (interface/gabarit.html, fonction anCalculer) refait exactement ces calculs dans le navigateur, comme
les ajustements (décision 0002) ; `tests/test_lot28_page.py` vérifie que les deux donnent le même résultat.
Seule la vue réelle est rejouée ici (la vue ajustée et la cohérence avec la paie restent dans la page).

Principes :
- montants en centimes entiers, sens naturel (produits et charges en positif, comme le tableau EBITDA) ;
- une résidence n'entre dans un écart que si tous les mois de la période ET de la référence sont couverts par la
  comptabilité (une absence de donnée n'est jamais zéro) ; dans un mois couvert, une ligne sans écriture vaut 0 ;
- les ratios se calculent sur des sommes (jamais une moyenne de ratios) ;
- un écart devient un « constat » à expliquer quand il dépasse les seuils (montant ET pourcentage) ;
- chaque constat a une clé stable (code, résidence, objet, période, référence) qui porte son suivi.
"""
import math

from zenitude.socle.paquet import calc_lignes, centimes, ecart_jours, ligne_du_compte

VERSION = 1

REFERENCES = {
    "n1": "Même période N-1",
    "prec": "Période précédente de même durée",
    "moy12": "Moyenne des 12 mois précédents",
}

SEUILS_DEFAUT = {
    "pct": 0.10,           # écart relatif minimal (10 %)
    "montant": 200000,     # écart minimal en centimes (2 000 €)
    "sigma": 2.0,          # anomalie : écart à la moyenne > 2 écarts-types
    "ecriture": 3.0,       # écriture inhabituelle : > 3 fois la médiane du compte
    "coherence": 0.15,     # ratio compta / KPI : variation de 15 %
    "rapprochement": 0.02,  # CA comptable / CA Mews : 2 %
    "etalement": 0.6,      # charge à étaler : écriture >= 60 % des 12 derniers mois du compte
    "historique": 6,       # nombre minimal de mois d'historique couverts
}

BLOCS = {
    "natures": "Coûts par nature",
    "volume": "Volume et prix",
    "fournisseurs": "Fournisseurs",
    "anomalies": "Anomalies et cut-off",
    "coherence": "Cohérence compta et KPI",
    "benchmark": "Comparaison des résidences",
    "social": "Cohérence compta et paie",
}

CODES = {
    "N1": ("natures", "Poste en écart"),
    "V1": ("volume", "CA hébergement : volume et prix"),
    "F1": ("fournisseurs", "Nouveau fournisseur"),
    "F2": ("fournisseurs", "Fournisseur disparu"),
    "F3": ("fournisseurs", "Fournisseur en forte variation"),
    "F4": ("fournisseurs", "Facture en double possible"),
    "F5": ("fournisseurs", "Fournisseur récurrent sans facture"),
    "A1": ("anomalies", "Poste hors de sa tendance"),
    "A2": ("anomalies", "Écriture inhabituelle"),
    "A3": ("anomalies", "Compte nouveau"),
    "A4": ("anomalies", "Charge à étaler"),
    "A5": ("anomalies", "Mois sans comptabilité"),
    "A6": ("anomalies", "Mois sans chiffre d’affaires"),
    "A7": ("anomalies", "Mois sans paie"),
    "K1": ("coherence", "Ratio compta / activité en écart"),
    "R1": ("coherence", "CA comptable différent du CA Mews"),
    "B1": ("benchmark", "Poste au-dessus des résidences comparables"),
    "S1": ("social", "Brut DSN différent des comptes 641"),
    "S2": ("social", "Masse salariale : effectif et coût moyen"),
    "S3": ("social", "Intérim en hausse sans hausse des arrêts"),
    "S4": ("social", "Coût horaire en écart"),
}

# Lignes de charges dont on regarde la part liée à l'activité (descendants de « Total charges variables »).
RACINE_VARIABLES = "CV"
# Lignes de charges suivies pour la comparaison des résidences (descendants de ces totaux).
RACINES_CHARGES = ("CV", "CF", "SIEGE", "LOYERS")
# Comptes dont une grosse écriture annuelle se lisse habituellement (assurances, taxes, charges locatives,
# contrats de maintenance, cotisations).
COMPTES_ETALEMENT = ("616", "635", "614", "6156", "6281")

# Ratios compta / activité : (code, libellé, numérateur (lignes), dénominateur (ligne ou mesure), sens)
# sens « charge » : une hausse du ratio dégrade l'EBITDA ; « produit » : l'améliore.
RATIOS = [
    ("K_PRIX", "Prix moyen comptable par nuitée vendue", ["CA_HEB"], ("mes", ["LN_VENDUES"]), "produit"),
    ("K_COMM", "Commissions en % du CA hébergement", ["COMM"], ("lig", ["CA_HEB"]), "charge"),
    ("K_MEN", "Ménage par nuitée vendue", ["MEN"], ("mes", ["LN_VENDUES"]), "charge"),
    ("K_BLANCH", "Blanchissage par nuitée vendue", ["BLANCH"], ("mes", ["LN_VENDUES"]), "charge"),
    ("K_ACCUEIL", "Produits d’accueil par client présent", ["PROD_ACC"], ("mes", ["NUITEES_CLIENTS"]), "charge"),
    ("K_PDJ", "Achats restauration par petit-déjeuner servi", ["ACH_REST"], ("mes", ["COUVERTS_PDJ"]), "charge"),
    ("K_FOOD", "Coût matière en % du CA restauration", ["ACH_REST"], ("lig", ["CA_REST"]), "charge"),
    ("K_ENERGIE", "Énergie par logement-nuit disponible", ["ENERGIE"], ("mes", ["LN_DISPONIBLES"]), "charge"),
    ("K_PERS", "Frais de personnel en % du CA", ["PERS_HB", "MEN", "CF_REST"], ("lig", ["CA"]), "charge"),
]
# Rapprochements CA comptable / CA Mews : (code objet, libellé, lignes comptables, données Mews)
RAPPROCHEMENTS = [
    ("CA", "CA total comptable / CA total Mews", ["CA"], ["CA_MEWS_TOTAL"]),
    ("CA_REST", "CA restauration comptable / CA restaurant et petit-déjeuner Mews", ["CA_REST"], ["CA_MEWS_RESTO", "CA_MEWS_PDJ"]),
]
BASES_BENCH = {
    "ca": ("En % du chiffre d’affaires", ("lig", ["CA"])),
    "nuitee": ("Par nuitée vendue", ("mes", ["LN_VENDUES"])),
    "capacite": ("Par logement-nuit disponible", ("mes", ["LN_DISPONIBLES"])),
}


# --------------------------------------------------------------------------------------------------
# Outils (mêmes règles que la page)
# --------------------------------------------------------------------------------------------------

def arr(x):
    """Arrondi au plus proche, demi loin de zéro (même règle que la page)."""
    s = -1 if x < 0 else 1
    return s * math.floor(abs(x) + 0.5 + 1e-9)


def aj_mois(m, n):
    y, k = int(m[:4]), int(m[5:7]) - 1 + n
    y += k // 12
    k %= 12
    return f"{y:04d}-{k + 1:02d}"


def mois_reference(mois, reference):
    """Mois de la référence et facteur d'échelle (moyenne de 12 mois ramenée à la durée de la période)."""
    n = len(mois)
    if reference == "n1":
        return [aj_mois(m, -12) for m in mois], 1.0
    if reference == "prec":
        return [aj_mois(mois[0], -n + i) for i in range(n)], 1.0
    if reference == "moy12":
        return [aj_mois(mois[0], -12 + i) for i in range(12)], n / 12
    raise ValueError(f"référence inconnue : {reference}")


def mediane(vals):
    v = sorted(vals)
    k = len(v)
    if not k:
        return None
    return v[k // 2] if k % 2 else (v[k // 2 - 1] + v[k // 2]) / 2


def cle(code, dossier, objet, mois, reference):
    return f"{code}|{dossier}|{objet}|{mois[0]}|{mois[-1]}|{reference}"


def seuils_complets(seuils):
    s = dict(SEUILS_DEFAUT)
    for k, v in (seuils or {}).items():
        if k in s and v is not None:
            s[k] = v
    return s


# --------------------------------------------------------------------------------------------------
# Données
# --------------------------------------------------------------------------------------------------

class Donnees:
    """Accès aux données publiées du site (même forme que D dans la page), vue réelle."""

    def __init__(self, donnees, exploitation=None):
        calcul = donnees["calcul"]
        self.lignes = donnees["lignes_ebitda"]
        self.defs = {l["code"]: l for l in self.lignes}
        self.compta = {d: {m: {c: centimes(v) for c, v in cs.items()} for m, cs in ms.items()}
                       for d, ms in calcul["compta"].items()}
        self.couv = {d: set(ms) for d, ms in calcul["couverts"].items()}
        ex = exploitation if exploitation is not None else calcul["exploitation"]
        self.expl = {d: {m: {k: float(v) for k, v in ks.items() if v is not None and v != ""} for m, ks in ms.items()}
                     for d, ms in ex.items()}
        self.ecr = donnees.get("ecritures") or {}
        self.residences = {r["dossier"]: r for r in donnees["residences"]}
        lib = {p["compte"]: str(p["libelle_compte"]).upper() for p in donnees.get("plan", []) if p.get("libelle_compte")}
        self._ligne = {}
        self._lib = lib
        self._mens = {}
        # Parents des lignes (pour savoir si une ligne est une charge variable ou une charge)
        self.parent = {}
        for l in self.lignes:
            for t in (l["regle"].get("termes") or []):
                self.parent.setdefault(t[1], l["code"])

    def ligne_de(self, c):
        if c not in self._ligne:
            self._ligne[c] = ligne_du_compte(c, self.lignes, self._lib.get(c, ""))
        return self._ligne[c]

    def ancetres(self, code):
        out, x = [], self.parent.get(code)
        while x:
            out.append(x)
            x = self.parent.get(x)
        return out

    def couvert(self, d, mois):
        c = self.couv.get(d, set())
        return all(m in c for m in mois)

    def postes(self, d, mois, facteur=1):
        """Valeur de chaque ligne EBITDA pour une résidence, sommée sur les mois (None = aucune écriture).

        facteur (moyenne de 12 mois ramenée à la période) : appliqué et arrondi sur chaque ligne de base, avant les
        totaux, pour que les totaux restent la somme exacte de leurs lignes."""
        brut = {}
        for m in mois:
            for c, v in ((self.compta.get(d) or {}).get(m) or {}).items():
                l = self.ligne_de(c)
                if l is None:
                    continue
                brut[l] = brut.get(l, 0) + v
        if facteur != 1:
            brut = {k: arr(v * facteur) for k, v in brut.items()}
        return calc_lignes(self.lignes, brut)

    def postes_mois(self, d, m):
        k = (d, m)
        if k not in self._mens:
            self._mens[k] = self.postes(d, [m])
        return self._mens[k]

    def mesure(self, d, codes, mois):
        """Somme de données d'exploitation (None si une valeur manque)."""
        t = 0.0
        for m in mois:
            x = (self.expl.get(d) or {}).get(m) or {}
            for k in codes:
                if k not in x:
                    return None
                t += x[k]
        return t


def val0(p, code):
    v = p.get(code)
    return 0 if v is None else v


def somme_lignes(p, codes):
    return sum(val0(p, c) for c in codes)


def base_de(D, d, P, spec, mois):
    genre, codes = spec
    if genre == "lig":
        return somme_lignes(P, codes)
    return D.mesure(d, codes, mois)


# --------------------------------------------------------------------------------------------------
# Analyse
# --------------------------------------------------------------------------------------------------

def analyser(donnees, dossiers, mois, reference="n1", seuils=None, exploitation=None):
    """Toutes les analyses d'un périmètre (liste de dossiers) sur une période (liste de mois consécutifs)."""
    S = seuils_complets(seuils)
    D = Donnees(donnees, exploitation)
    dossiers = sorted(set(dossiers))
    mref, facteur = mois_reference(mois, reference)
    constats = []

    def constat(code, d, objet, valeur, ref, impact, info=None, mois_c=None):
        ecart = None if valeur is None or ref is None else valeur - ref
        pct = None if ecart is None or not ref else ecart / abs(ref)
        constats.append({"cle": cle(code, d, objet, mois, reference), "bloc": CODES[code][0], "code": code, "dossier": d,
                         "objet": objet, "mois": mois_c or "", "valeur": valeur, "reference": ref, "ecart": ecart,
                         "pct": pct, "impact": impact, "info": info or {}})

    # ---- Disponibilité et postes par résidence ----
    res = {}
    for d in dossiers:
        dv, dr = D.couvert(d, mois), D.couvert(d, mref)
        x = {"dispo": dv and dr, "motif": None if dv and dr else ("période" if not dv else "référence")}
        if dv:
            x["pv"] = D.postes(d, mois)
        if x["dispo"]:
            x["pr"] = D.postes(d, mref, facteur)
            x["nv"] = D.mesure(d, ["LN_VENDUES"], mois)
            nr = D.mesure(d, ["LN_VENDUES"], mref)
            x["nr"] = None if nr is None else nr * facteur
        res[d] = x
    dispo = [d for d in dossiers if res[d]["dispo"]]

    # ---- Bloc 1 : coûts par nature ----
    natures = []
    for l in D.lignes:
        code = l["code"]
        anc = D.ancetres(code)
        variable = RACINE_VARIABLES in anc
        charge = l["sens"] == "charge" or any(a in RACINES_CHARGES for a in anc) or code in RACINES_CHARGES
        v = r = 0
        vu = False
        ea, ea_ok = 0, True
        for d in dispo:
            a, b = res[d]["pv"].get(code), res[d]["pr"].get(code)
            if a is None and b is None:
                continue
            vu = True
            a, b = a or 0, b or 0
            v += a
            r += b
            if variable:
                nv, nr = res[d]["nv"], res[d]["nr"]
                if nv is None or not nr:
                    ea_ok = False
                else:
                    ea += arr(b * (nv / nr - 1))
        if not vu:
            continue
        cav = sum(val0(res[d]["pv"], "CA") for d in dispo)
        car = sum(val0(res[d]["pr"], "CA") for d in dispo)
        nv = [res[d]["nv"] for d in dispo]
        nr = [res[d]["nr"] for d in dispo]
        nv = None if any(x is None for x in nv) else sum(nv)
        nr = None if any(x is None for x in nr) else sum(nr)
        natures.append({
            "code": code, "niveau": l["niveau"], "sens": l["sens"], "variable": variable, "charge": charge,
            "v": v, "r": r, "ecart": v - r, "pct": (v - r) / abs(r) if r else None,
            "ca_v": v / cav if cav else None, "ca_r": r / car if car else None,
            "nuit_v": v / nv if nv else None, "nuit_r": r / nr if nr else None,
            "effet_activite": (ea if ea_ok else None) if variable else None,
            "effet_cout": (v - r - ea if ea_ok else None) if variable else None,
        })

    for d in dispo:
        P, R = res[d]["pv"], res[d]["pr"]
        for l in D.lignes:
            if l["regle"].get("prefixes") is None or l["sens"] not in ("charge", "produit"):
                continue
            code = l["code"]
            if P.get(code) is None and R.get(code) is None:
                continue
            a, b = val0(P, code), val0(R, code)
            e = a - b
            if abs(e) < S["montant"] or (b and abs(e) / abs(b) < S["pct"]):
                continue
            info = {}
            if RACINE_VARIABLES in D.ancetres(code) and res[d]["nv"] is not None and res[d]["nr"]:
                info["effet_activite"] = arr(b * (res[d]["nv"] / res[d]["nr"] - 1))
            constat("N1", d, code, a, b, e if l["sens"] == "produit" else -e, info)

    # ---- Bloc 3 : cascade de l'EBITDA ----
    etapes_def = [("CA_HEB", 1), ("CA_ANN", 1), ("CA_REST", 1), ("CV_HEB", -1), ("CV_REST", -1), ("CF_HEB", -1),
                  ("CF_REST", -1), ("SIEGE", -1), ("LOYERS", -1)]
    etapes = []
    for code, sg in etapes_def:
        e = sum(val0(res[d]["pv"], code) - val0(res[d]["pr"], code) for d in dispo)
        etapes.append([code, sg * e])
    cascade = {
        "ebitda_v": sum(val0(res[d]["pv"], "EBITDA") for d in dispo),
        "ebitda_r": sum(val0(res[d]["pr"], "EBITDA") for d in dispo),
        "etapes": etapes,
        "residences": [[d, val0(res[d]["pv"], "EBITDA"), val0(res[d]["pr"], "EBITDA")] for d in dispo],
    }

    # ---- Bloc 2 : volume et prix du CA hébergement ----
    volprix = []
    for d in dispo:
        P, R = res[d]["pv"], res[d]["pr"]
        cv, cr = val0(P, "CA_HEB"), val0(R, "CA_HEB")
        nv, nr = res[d]["nv"], res[d]["nr"]
        kv = D.mesure(d, ["LN_DISPONIBLES"], mois)
        kr = D.mesure(d, ["LN_DISPONIBLES"], mref)
        kr = None if kr is None else kr * facteur
        av = val0(P, "CA_ANN") + val0(P, "CA_REST")
        ar = val0(R, "CA_ANN") + val0(R, "CA_REST")
        x = {"dossier": d, "ca_v": cv, "ca_r": cr, "n_v": nv, "n_r": nr, "k_v": kv, "k_r": kr, "ann_v": av, "ann_r": ar,
             "volume": None, "prix": None, "capacite": None, "occupation": None, "ann_volume": None, "panier": None}
        if nv is not None and nr:
            x["volume"] = arr((nv - nr) * cr / nr)
            x["prix"] = (cv - cr) - x["volume"]
            x["ann_volume"] = arr((nv - nr) * ar / nr)
            x["panier"] = (av - ar) - x["ann_volume"]
            if kv is not None and kr:
                x["capacite"] = arr((kv - kr) * (nr / kr) * cr / nr)
                x["occupation"] = x["volume"] - x["capacite"]
        volprix.append(x)
        e = cv - cr
        if abs(e) >= S["montant"] and (not cr or abs(e) / abs(cr) >= S["pct"]):
            constat("V1", d, "CA_HEB", cv, cr, e, {k: x[k] for k in ("volume", "prix", "capacite", "occupation")})

    # ---- Bloc 4 : fournisseurs ----
    fournisseurs = []
    smois, sref = set(mois), set(mref)
    for d in dossiers:
        ecr = D.ecr.get(d, [])
        pieces = {}
        for e in ecr:
            pieces.setdefault(e[3], []).append(e)
        fo = {}  # (tiers, mois) -> [charges, nb]
        comptes = {}
        for p in sorted(pieces):
            ls = pieces[p]
            m = ls[0][1][:7]
            tr = next((e[7] for e in ls if e[4].startswith("40") and e[7]), None)
            ch = [e for e in ls if e[4].startswith("6")]
            if not tr or not ch:
                continue
            x = fo.setdefault((tr, m), [0, 0])
            x[0] += sum(-e[6] for e in ch)
            x[1] += 1
            comptes.setdefault(tr, set()).update(e[4] for e in ch)
        if res[d]["dispo"]:
            tiers = sorted({t for (t, m) in fo if m in smois or m in sref})
            for t in tiers:
                v = sum(fo[(t, m)][0] for m in mois if (t, m) in fo)
                nb_v = sum(fo[(t, m)][1] for m in mois if (t, m) in fo)
                r0 = sum(fo[(t, m)][0] for m in mref if (t, m) in fo)
                nb_r = sum(fo[(t, m)][1] for m in mref if (t, m) in fo)
                r = arr(r0 * facteur) if facteur != 1 else r0
                e = v - r
                statut = "stable"
                if not nb_r and nb_v:
                    statut = "nouveau"
                elif nb_r and not nb_v:
                    statut = "disparu"
                elif r and abs(e) / abs(r) >= S["pct"]:
                    statut = "variation"
                fournisseurs.append({"dossier": d, "tiers": t, "v": v, "r": r, "nb_v": nb_v, "nb_r": nb_r,
                                     "comptes": "|".join(sorted(comptes.get(t, set()))), "statut": statut})
                if statut == "nouveau" and v >= S["montant"]:
                    constat("F1", d, t, v, r, -e, {"nb_v": nb_v})
                elif statut == "disparu" and r >= S["montant"]:
                    constat("F2", d, t, v, r, -e, {"nb_r": nb_r})
                elif statut == "variation" and abs(e) >= S["montant"]:
                    constat("F3", d, t, v, r, -e, {"nb_v": nb_v, "nb_r": nb_r})
        # F5 : fournisseur récurrent sans facture (règle du contrôle C04, sur les mois couverts de la période)
        couverts_p = [m for m in mois if m in D.couv.get(d, set())]
        n = len(couverts_p)
        if n >= 3:
            par_tiers = {}
            for (t, m), x in fo.items():
                if m in couverts_p:
                    par_tiers.setdefault(t, {})[m] = x[0]
            seuil = max(3, (n + 1) // 2)
            for t in sorted(par_tiers):
                ms = par_tiers[t]
                k = len(ms)
                if k < seuil or k >= n:
                    continue
                vals = sorted(ms.values())
                med = vals[(k - 1) // 2]
                for m in couverts_p:
                    if m not in ms and med >= S["montant"] / 10:
                        constat("F5", d, t + "|" + m, None, med, -med, {"mois_factures": k, "mois_couverts": n}, m)
        # F4 : factures en double possibles (règle du contrôle C05, pièces de la période)
        debut, fin = mois[0] + "-01", mois[-1] + "-31"
        fact = [e for e in ecr if e[4].startswith("40") and e[7] and e[6] > 0 and e[2] != "AN" and e[1] <= fin]
        grp = {}
        for e in fact:
            grp.setdefault((e[7], e[6]), []).append(e)
        for (t, mt) in sorted(grp):
            ls = sorted(grp[(t, mt)], key=lambda e: (e[1], e[3]))
            for a, b in zip(ls, ls[1:]):
                if a[3] != b[3] and ecart_jours(a[1], b[1]) <= 5 and b[1] >= debut:
                    constat("F4", d, t + "|" + a[3] + "|" + b[3], mt, None, -mt, {"date_a": a[1], "date_b": b[1]}, b[1][:7])

    # ---- Bloc 5 : anomalies et cut-off ----
    feuilles = [l for l in D.lignes if l["regle"].get("prefixes") is not None and l["sens"] in ("charge", "produit")]
    for d in dossiers:
        couv = D.couv.get(d, set())
        ecr = D.ecr.get(d, [])
        # A5 à A7 : mois sans données
        for m in mois:
            if m not in couv:
                constat("A5", d, m, None, None, 0, {}, m)
        par_mois = {}
        for e in ecr:
            par_mois.setdefault(e[1][:7], []).append(e)
        a_paie = any(e[4].startswith("641") for m in list(mois) + [aj_mois(mois[0], -i) for i in range(1, 13)]
                     for e in par_mois.get(m, []))
        for m in mois:
            if m not in couv:
                continue
            ls = par_mois.get(m, [])
            if not any(e[4].startswith("7") and e[6] for e in ls):
                constat("A6", d, m, None, None, 0, {}, m)
            if a_paie and not any(e[4].startswith("641") for e in ls):
                constat("A7", d, m, None, None, 0, {}, m)
        # A1 : poste hors de sa tendance (12 mois précédant chaque mois)
        for m in mois:
            if m not in couv:
                continue
            hist = [aj_mois(m, -i) for i in range(12, 0, -1)]
            hist = [h for h in hist if h in couv]
            if len(hist) < S["historique"]:
                continue
            P = D.postes_mois(d, m)
            for l in feuilles:
                code = l["code"]
                xs = [val0(D.postes_mois(d, h), code) for h in hist]
                v = val0(P, code)
                if v == 0 and not any(xs):
                    continue
                mu = sum(xs) / len(xs)
                sg = math.sqrt(sum((x - mu) * (x - mu) for x in xs) / len(xs))
                dev = v - mu
                if abs(dev) >= S["montant"] and abs(dev) > S["sigma"] * sg:
                    constat("A1", d, code + "|" + m, v, arr(mu), arr(dev) if l["sens"] == "produit" else -arr(dev),
                            {"sigma": arr(sg), "n": len(hist)}, m)
        # A2 : écriture inhabituelle ; A4 : charge à étaler
        par_compte = {}
        for e in ecr:
            if e[4][:1] in ("6", "7"):
                par_compte.setdefault(e[4], []).append(e)
        for c in sorted(par_compte):
            ls = par_compte[c]
            for e in ls:
                m = e[1][:7]
                if m not in smois:
                    continue
                hist = {aj_mois(m, -i) for i in range(1, 13)}
                h = [abs(x[6]) for x in ls if x[1][:7] in hist]
                ma = abs(e[6])
                if len(h) >= 3 and ma >= S["montant"]:
                    med = mediane(h)
                    if ma > S["ecriture"] * med:
                        constat("A2", d, e[0], ma, arr(med), e[6], {"compte": c, "piece": e[3], "date": e[1], "n": len(h)}, m)
                if c.startswith(COMPTES_ETALEMENT) and e[6] < 0 and -e[6] >= S["montant"]:
                    fen = {aj_mois(m, -i) for i in range(12)}
                    nb_couv = sum(1 for x in fen if x in couv)
                    tot = sum(-x[6] for x in ls if x[1][:7] in fen)
                    if nb_couv >= S["historique"] and tot > 0 and -e[6] >= S["etalement"] * tot:
                        constat("A4", d, e[0], -e[6], arr(-e[6] / 12), -(-e[6] - arr(-e[6] / 12)),
                                {"compte": c, "piece": e[3], "date": e[1], "part": -e[6] / tot}, m)
        # A3 : compte nouveau (aucune écriture sur les 12 mois précédant la période)
        hist = [aj_mois(mois[0], -i) for i in range(1, 13)]
        if sum(1 for h in hist if h in couv) >= S["historique"]:
            for c in sorted(par_compte):
                ls = par_compte[c]
                dans = [e for e in ls if e[1][:7] in smois]
                if not dans or any(e[1][:7] in set(hist) for e in ls):
                    continue
                t = sum(e[6] for e in dans)
                if abs(t) >= S["montant"]:
                    constat("A3", d, c, abs(t), 0, t, {"nb": len(dans)})

    # ---- Bloc 6 : cohérence compta / KPI ----
    coherence = []
    for d in dispo:
        P, R = res[d]["pv"], res[d]["pr"]
        for code, _lib, num, den, sens in RATIOS:
            nv, nr = somme_lignes(P, num), somme_lignes(R, num)
            dv = base_de(D, d, P, den, mois)
            dr = base_de(D, d, R, den, mref)
            if den[0] == "mes" and dr is not None:
                dr = dr * facteur
            rv = nv / dv if dv else None
            rr = nr / dr if dr else None
            if not nv and not nr:
                continue
            impact = None
            if rv is not None and rr is not None:
                impact = arr((rv - rr) * dv)
                if sens == "charge":
                    impact = -impact
            coherence.append({"dossier": d, "code": code, "num_v": nv, "num_r": nr, "den_v": dv, "den_r": dr,
                              "ratio_v": rv, "ratio_r": rr, "impact": impact})
            if rv is not None and rr and abs(rv / rr - 1) >= S["coherence"] and abs(impact) >= S["montant"]:
                constat("K1", d, code, None, None, impact, {"ratio_v": rv, "ratio_r": rr})
    for d in dossiers:
        couv = D.couv.get(d, set())
        for code, _lib, lignes, mews in RAPPROCHEMENTS:
            for m in mois:
                if m not in couv:
                    continue
                me = D.mesure(d, mews, [m])
                if me is None:
                    continue
                cpt = somme_lignes(D.postes_mois(d, m), lignes)
                mc = arr(me * 100)
                e = cpt - mc
                if abs(e) >= S["montant"] / 10 and (not mc or abs(e) / abs(mc) > S["rapprochement"]):
                    constat("R1", d, code + "|" + m, cpt, mc, e, {}, m)

    # ---- Bloc 8 : comparaison des résidences ----
    benchmark = []
    disp_v = [d for d in dossiers if "pv" in res[d]]
    if len(disp_v) >= 2:
        charges = [l for l in D.lignes
                   if l["code"] in RACINES_CHARGES or any(a in RACINES_CHARGES for a in D.ancetres(l["code"]))]
        acts = {d: D.residences.get(d, {}).get("activite", "") for d in disp_v}
        for base, (_lib, spec) in BASES_BENCH.items():
            dens = {d: base_de(D, d, res[d]["pv"], spec, mois) for d in disp_v}
            for l in charges:
                code = l["code"]
                ratios = {}
                for d in disp_v:
                    v = res[d]["pv"].get(code)
                    if dens[d] and v is not None:
                        ratios[d] = v / dens[d]
                if len(ratios) < 2:
                    continue
                for d in sorted(ratios):
                    comp = [x for x in ratios if acts[x] == acts[d]]
                    groupe = "activite"
                    if len(comp) < 3:
                        comp, groupe = list(ratios), "perimetre"
                    med = mediane([ratios[x] for x in comp])
                    rang = 1 + sum(1 for x in comp if ratios[x] < ratios[d])
                    pot = arr((ratios[d] - med) * dens[d]) if ratios[d] > med else 0
                    benchmark.append({"base": base, "code": code, "dossier": d, "ratio": ratios[d], "mediane": med,
                                      "comparables": len(comp), "groupe": groupe, "rang": rang, "potentiel": pot})
                    if (base == "ca" and l["regle"].get("prefixes") is not None and len(comp) >= 3 and med > 0
                            and ratios[d] > med * (1 + S["pct"]) and pot >= S["montant"]):
                        constat("B1", d, code, res[d]["pv"].get(code), arr(med * dens[d]), -pot,
                                {"ratio": ratios[d], "mediane": med, "comparables": len(comp), "groupe": groupe})

    constats.sort(key=lambda x: (-abs(x["impact"] or 0), x["cle"]))
    return {
        "version": VERSION, "reference": reference, "mois": list(mois), "mois_ref": mref, "facteur": facteur,
        "seuils": S, "dispo": dispo,
        "exclues": [[d, res[d]["motif"]] for d in dossiers if not res[d]["dispo"]],
        "natures": natures, "cascade": cascade, "volprix": volprix, "fournisseurs": fournisseurs,
        "coherence": coherence, "benchmark": benchmark, "constats": constats,
    }
