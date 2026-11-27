"""Lot 26 - Lecture de la DSN brute (norme NEODeS) et indicateurs sociaux par établissement et par mois.

Référence Python des calculs que la page refait dans le navigateur (`interface/gabarit.html`, « Lot 26 :
social »). Un test compare les deux, à l'octet près, sur des DSN fictives (`tests/test_lot26_page.py`).
Décision : `docs/decisions/0020-dsn-et-indicateurs-sociaux.md`. Règles : `docs/dsn.md`.

Principe de confidentialité
    Le fichier DSN contient des données nominatives (noms, NIR, salaires individuels). Il est lu sur le poste
    de la personne qui l'importe et n'est jamais envoyé ni conservé. Seuls des totaux par établissement et
    par mois sont gardés (`contenu`), plus, pour suivre les arrêts de travail d'un mois sur l'autre, une clé
    anonyme par arrêt (empreinte tronquée sans nom ni NIR) et ses dates. Aucun nom, NIR, matricule ou salaire
    individuel n'en sort.

Lecture
    Une ligne = `RUBRIQUE,'valeur'` (ex. `S21.G00.40.001,'01032026'`). Une nouvelle occurrence de bloc commence
    quand le bloc change ou quand le numéro de rubrique ne progresse pas. Un envoi peut contenir plusieurs
    déclarations (une par bloc S20.G00.05). Une ligne illisible refuse le fichier entier (rien n'est importé).
    Une déclaration non mensuelle, d'annulation ou fractionnée est refusée seule, avec son motif.

Montants en centimes entiers, heures en centièmes, ETP en millièmes : aucun calcul en virgule flottante, la
page et ce module donnent exactement les mêmes nombres.

Codes de la norme utilisés : voir `docs/dsn.md` (à confirmer sur un premier fichier réel exporté de Silae).
"""
from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import json
import re

VERSION = 2
RE_LIGNE = re.compile(r"^(S[0-9]{2}\.G[0-9]{2}\.[0-9]{2})\.([0-9]{3}),'(.*)'$")
RE_MONTANT = re.compile(r"^-?[0-9]{1,12}(\.[0-9]{1,2})?$")
RE_SIRET = re.compile(r"^[0-9]{14}$")
RE_CHIFFRES = re.compile(r"^[0-9]+$")

TYPES_ACCEPTES = {"01": "normale", "02": "néant", "03": "annule et remplace", "05": "annule et remplace néant"}
NATURES_HORS_EFFECTIF = {"29", "80"}  # convention de stage, mandataire social
DISPOSITIFS_ALTERNANCE = {"61", "64", "65"}  # professionnalisation, apprentissage
CATEGORIES = ["CDI", "CDD", "ALTERNANCE", "AUTRE"]
MOTIFS_SORTIE = ["DEMISSION", "RUPTURE_CONVENTIONNELLE", "LICENCIEMENT", "FIN_CDD", "PERIODE_ESSAI", "RETRAITE", "AUTRE"]
MOTIFS_ARRET = ["MALADIE", "AT_MP", "PARENTALITE", "AUTRE"]
TRANCHES_AGE = ["<26", "26-44", "45-54", "55+"]
TRANCHES_ANCIENNETE = ["<1", "1-3", "3-10", "10+"]


class ErreurDSN(ValueError):
    """Fichier illisible : rien n'est importé."""


# ---------------------------------------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------------------------------------
def decoder(octets: bytes) -> str:
    """UTF-8 si possible (BOM retiré), sinon ISO-8859-1 (encodage habituel des fichiers DSN)."""
    if octets.startswith(b"\xef\xbb\xbf"):
        octets = octets[3:]
    try:
        return octets.decode("utf-8")
    except UnicodeDecodeError:
        return octets.decode("latin-1")


def date_dsn(v):
    """JJMMAAAA -> date, ou None si absente ou invalide."""
    if not v or not re.fullmatch(r"[0-9]{8}", v):
        return None
    try:
        return dt.date(int(v[4:]), int(v[2:4]), int(v[:2]))
    except ValueError:
        return None


def entier_echelle(v, ou):
    """'1234.5' -> 123450 (centièmes), exact. Valeur absente -> None ; illisible -> ValueError."""
    if v is None or v == "":
        return None
    if not RE_MONTANT.match(v):
        raise ValueError(f"montant illisible « {v} » ({ou})")
    neg = v.startswith("-")
    if neg:
        v = v[1:]
    ent, _, dec = v.partition(".")
    n = int(ent) * 100 + int((dec + "00")[:2])
    return -n if neg else n


def annees_entre(debut: dt.date, fin: dt.date) -> int:
    n = fin.year - debut.year
    if (fin.month, fin.day) < (debut.month, debut.day):
        n -= 1
    return n


def tranche_age(a):
    return "<26" if a <= 25 else "26-44" if a <= 44 else "45-54" if a <= 54 else "55+"


def tranche_anciennete(a):
    return "<1" if a < 1 else "1-3" if a < 3 else "3-10" if a < 10 else "10+"


def categorie_contrat(c):
    if c.get("008") in DISPOSITIFS_ALTERNANCE:
        return "ALTERNANCE"
    n = c.get("007")
    if n in ("01", "07"):
        return "CDI"
    if n in ("02", "08", "09", "10"):
        return "CDD"
    return "AUTRE"


def motif_sortie(code):
    code = code or ""
    if code == "059":
        return "DEMISSION"
    if code == "043":
        return "RUPTURE_CONVENTIONNELLE"
    if code in ("031", "032"):
        return "FIN_CDD"
    if code in ("034", "035"):
        return "PERIODE_ESSAI"
    if code in ("038", "039"):
        return "RETRAITE"
    if len(code) == 3 and code[:2] in ("01", "02"):
        return "LICENCIEMENT"
    return "AUTRE"


def motif_arret(code):
    if code == "01":
        return "MALADIE"
    if code in ("04", "05", "06"):
        return "AT_MP"
    if code in ("02", "03"):
        return "PARENTALITE"
    return "AUTRE"


def cle_arret(siret, dernier, motif, naissance, sexe):
    """Clé anonyme d'un arrêt : relie ses déclarations successives sans nom ni NIR."""
    texte = f"{siret}|{dernier}|{motif}|{naissance}|{sexe}"
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]


def pseudonyme(siren, r, rang):
    """Identifiant stable d'un salarié dans une société, sans nom ni NIR (empreinte tronquée)."""
    ident = ("N:" + r["001"]) if r.get("001") else ("M:" + r["019"]) if r.get("019") else f"I:{rang}"
    return hashlib.sha256(f"SAL|{siren}|{ident}".encode("utf-8")).hexdigest()[:12]


RE_BLANCS = re.compile(r"[ \t\n\r\f\v]+")


def normaliser_emploi(v):
    """Libellé d'emploi : espaces réduits, majuscules (sert de clé au référentiel des postes)."""
    return RE_BLANCS.sub(" ", v or "").strip(" ").upper()


def mois_entre(a, b):
    """Mois révolus de a à b."""
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def iso(d):
    return d.isoformat() if d else None


# ---------------------------------------------------------------------------------------------------------
# Lecture du fichier
# ---------------------------------------------------------------------------------------------------------
def lire(texte: str) -> dict:
    """Découpe un envoi DSN en déclarations. ErreurDSN si une ligne est illisible ou mal placée."""
    decls, avert = [], []
    cur = indiv = contrat = occ = None
    prec_bloc, prec_rub, n_lignes, total = None, 0, 0, {}
    for num, brut in enumerate(texte.splitlines(), start=1):
        ligne = brut.strip()
        if not ligne:
            continue
        n_lignes += 1
        m = RE_LIGNE.match(ligne)
        if not m:
            raise ErreurDSN(f"ligne {num} illisible : ce n’est pas une rubrique DSN (RUBRIQUE,'valeur').")
        bloc, rub, val = m.group(1), m.group(2), m.group(3)
        nouveau = bloc != prec_bloc or int(rub) <= prec_rub
        prec_bloc, prec_rub = bloc, int(rub)
        if bloc == "S90.G00.90":
            total[rub] = val
            occ = None
            continue
        if bloc.startswith("S10"):
            occ = None
            continue
        if nouveau:
            if bloc == "S20.G00.05":
                cur = {"s20": {}, "s06": {}, "s11": {}, "ops": [], "individus": [], "ligne": num}
                decls.append(cur)
                indiv = contrat = None
                occ = cur["s20"]
            elif cur is None:
                raise ErreurDSN(f"ligne {num} : rubrique {bloc}.{rub} avant le début d’une déclaration (bloc S20.G00.05).")
            elif bloc == "S21.G00.06":
                occ = cur["s06"]
            elif bloc == "S21.G00.11":
                occ = cur["s11"]
            elif bloc == "S21.G00.20":
                occ = {}
                cur["ops"].append(occ)
            elif bloc == "S21.G00.30":
                indiv = {"r": {}, "contrats": [], "versements": [], "remunerations": [], "primes": []}
                cur["individus"].append(indiv)
                contrat = None
                occ = indiv["r"]
            elif bloc in ("S21.G00.40", "S21.G00.50", "S21.G00.51", "S21.G00.52", "S21.G00.60", "S21.G00.62"):
                if indiv is None:
                    raise ErreurDSN(f"ligne {num} : bloc {bloc} sans individu (bloc S21.G00.30).")
                occ = {}
                if bloc == "S21.G00.40":
                    contrat = {"r": occ, "arrets": [], "fin": None}
                    indiv["contrats"].append(contrat)
                elif bloc == "S21.G00.50":
                    indiv["versements"].append(occ)
                elif bloc == "S21.G00.51":
                    indiv["remunerations"].append(occ)
                elif bloc == "S21.G00.52":
                    indiv["primes"].append(occ)
                else:
                    if contrat is None:
                        raise ErreurDSN(f"ligne {num} : bloc {bloc} sans contrat (bloc S21.G00.40).")
                    if bloc == "S21.G00.60":
                        contrat["arrets"].append(occ)
                    else:
                        contrat["fin"] = occ
            else:
                occ = None  # bloc non utilisé (bases, cotisations individuelles, etc.)
        if occ is not None:
            occ[rub] = val
    if not decls:
        raise ErreurDSN("aucune déclaration (bloc S20.G00.05) : ce fichier n’est pas une DSN.")
    if "001" in total and RE_CHIFFRES.match(total["001"]) and int(total["001"]) != n_lignes:
        avert.append(f"le fichier annonce {int(total['001'])} rubriques et en contient {n_lignes} (fichier peut-être incomplet).")
    if "002" in total and RE_CHIFFRES.match(total["002"]) and int(total["002"]) != len(decls):
        avert.append(f"le fichier annonce {int(total['002'])} déclarations et en contient {len(decls)}.")
    return {"declarations": decls, "avertissements": avert, "lignes": n_lignes}


# ---------------------------------------------------------------------------------------------------------
# Indicateurs d'une déclaration
# ---------------------------------------------------------------------------------------------------------
def entete(decl) -> dict:
    s20, s06, s11 = decl["s20"], decl["s06"], decl["s11"]
    siret = (s06.get("001") or "") + (s11.get("001") or "")
    d = date_dsn(s20.get("005"))
    mois = f"{d.year:04d}-{d.month:02d}" if d else None
    refus = None
    if s20.get("001") != "01":
        refus = f"déclaration de nature {s20.get('001') or '?'} (seule la DSN mensuelle, nature 01, est lue)"
    elif s20.get("002") not in TYPES_ACCEPTES:
        refus = ("déclaration d’annulation (type 04) : non prise en compte, le mois déjà importé est conservé"
                 if s20.get("002") == "04" else f"type de déclaration {s20.get('002') or '?'} inconnu")
    elif s20.get("003") not in (None, "", "11"):
        refus = f"DSN fractionnée (fraction {s20.get('003')}) : non prise en charge"
    elif not RE_SIRET.match(siret):
        refus = f"SIRET de l’établissement illisible (« {siret} »)"
    elif not mois:
        refus = f"mois déclaré illisible (« {s20.get('005') or ''} »)"
    return {"siret": siret, "mois": mois, "type": s20.get("002"), "nature": s20.get("001"), "refus": refus}


def agreger(decl, siret, mois) -> dict:
    """Totaux anonymes d'une déclaration mensuelle. ValueError (motif) si un montant est illisible."""
    an, mo = int(mois[:4]), int(mois[5:])
    F, L = dt.date(an, mo, 1), dt.date(an, mo, calendar.monthrange(an, mo)[1])
    s11 = decl["s11"]
    eff_decl = s11.get("008")
    R = {
        "version": VERSION, "nature": decl["s20"].get("001"), "type": decl["s20"].get("002"),
        "effectif_declare": int(eff_decl) if eff_decl and RE_CHIFFRES.match(eff_decl) else None,
        "effectif_fin": 0, "stagiaires_fin": 0,
        "categories": {k: 0 for k in CATEGORIES}, "femmes": 0, "hommes": 0, "cadres": 0,
        "age_somme": 0, "age_nb": 0, "tranches_age": {k: 0 for k in TRANCHES_AGE},
        "anciennete": {k: 0 for k in TRANCHES_ANCIENNETE},
        "etp_milli": 0, "etp_incomplet": 0,
        "entrees": {k: 0 for k in CATEGORIES}, "sorties": {k: 0 for k in MOTIFS_SORTIE},
        "brut": 0, "net_verse": 0, "pas": 0, "primes": 0, "cotisations_organismes": 0,
        "heures_payees": 0, "hs_heures": 0, "hs_montant": 0, "salaries_payes": 0,
        "arrets": [], "alertes": [], "salaries": [],
    }
    siren = decl["s06"].get("001") or ""
    sans_debut = 0
    for o in decl["ops"]:
        R["cotisations_organismes"] += entier_echelle(o.get("005"), "versement à un organisme") or 0
    arrets = {}
    for rang, ind in enumerate(decl["individus"]):
        r = ind["r"]
        sexe, naissance = r.get("005"), date_dsn(r.get("006"))
        sid = pseudonyme(siren, r, rang)
        etp_ind, entree, sortie = None, False, None
        S = {"brut": 0, "heures": 0, "hs_heures": 0, "hs_montant": 0, "primes": 0, "net": 0}
        cs = []
        for c in ind["contrats"]:
            debut = date_dsn(c["r"].get("001"))
            if debut is None:
                sans_debut += 1
                continue
            fin = date_dsn(c["fin"].get("001")) if c["fin"] else None
            cs.append({"r": c["r"], "debut": debut, "fin": fin, "motif_fin": (c["fin"] or {}).get("002"),
                       "arrets": c["arrets"], "hors": c["r"].get("007") in NATURES_HORS_EFFECTIF})
        utiles = [c for c in cs if not c["hors"]]
        presents = [c for c in utiles if c["debut"] <= L and (c["fin"] is None or c["fin"] >= L)]
        if presents:
            princ = min(presents, key=lambda c: c["debut"])  # min garde le premier en cas d'égalité
            R["effectif_fin"] += 1
            R["categories"][categorie_contrat(princ["r"])] += 1
            if sexe == "02":
                R["femmes"] += 1
            elif sexe == "01":
                R["hommes"] += 1
            if princ["r"].get("003") in ("01", "02"):
                R["cadres"] += 1
            if naissance and naissance <= L:
                a = annees_entre(naissance, L)
                R["age_somme"] += a
                R["age_nb"] += 1
                R["tranches_age"][tranche_age(a)] += 1
            R["anciennete"][tranche_anciennete(annees_entre(min(c["debut"] for c in utiles), L))] += 1
            milli, complet = 0, True
            for c in presents:
                q = entier_echelle(c["r"].get("013"), "quotité du contrat")
                ref = entier_echelle(c["r"].get("012"), "quotité de référence")
                if q is None or ref is None or ref <= 0 or q < 0:
                    complet = False
                    continue
                milli += min(1000, (2 * 1000 * q + ref) // (2 * ref))
            if complet:
                etp_ind = min(1000, milli)
                R["etp_milli"] += etp_ind
            else:
                R["etp_incomplet"] += 1
        elif any(c["debut"] <= L and (c["fin"] is None or c["fin"] >= L) for c in cs if c["r"].get("007") == "29"):
            R["stagiaires_fin"] += 1
        for c in utiles:
            if F <= c["debut"] <= L and not any(o["debut"] < c["debut"] for o in utiles if o is not c):
                R["entrees"][categorie_contrat(c["r"])] += 1
                entree = True
        if not presents:
            finis = [c for c in utiles if c["fin"] is not None and F <= c["fin"] <= L]
            if finis:
                sortie = motif_sortie(max(finis, key=lambda c: c["fin"])["motif_fin"])
                R["sorties"][sortie] += 1
        for rem in ind["remunerations"]:
            t = rem.get("011")
            mt = entier_echelle(rem.get("013"), "rémunération") or 0
            h = entier_echelle(rem.get("012"), "nombre d’heures") or 0
            if t == "001":
                S["brut"] += mt
            elif t == "002":
                S["heures"] += h
            elif t in ("017", "018"):
                S["hs_heures"] += h
                S["hs_montant"] += mt
        for p in ind["primes"]:
            S["primes"] += entier_echelle(p.get("002"), "prime") or 0
        for v in ind["versements"]:
            S["net"] += entier_echelle(v.get("004"), "net versé") or 0
            R["pas"] += entier_echelle(v.get("009"), "prélèvement à la source") or 0
        R["brut"] += S["brut"]
        R["heures_payees"] += S["heures"]
        R["hs_heures"] += S["hs_heures"]
        R["hs_montant"] += S["hs_montant"]
        R["primes"] += S["primes"]
        R["net_verse"] += S["net"]
        if ind["versements"]:
            R["salaries_payes"] += 1
        for c in utiles:
            for a in c["arrets"]:
                dernier = date_dsn(a.get("002"))
                if dernier is None:
                    R["alertes"].append("arrêt de travail sans date du dernier jour travaillé : ignoré")
                    continue
                motif = a.get("001") or ""
                cle = cle_arret(siret, iso(dernier), motif, iso(naissance) or "", sexe or "")
                x = {"cle": cle, "motif": motif, "debut": iso(dernier + dt.timedelta(days=1)),
                     "fin_prevue": iso(date_dsn(a.get("003"))), "reprise": iso(date_dsn(a.get("010"))), "sal": sid}
                if cle not in arrets or (x["reprise"] and not arrets[cle]["reprise"]):
                    arrets[cle] = x
        if utiles:
            if presents:
                ref_c = min(presents, key=lambda c: c["debut"])
            else:
                avec_fin = [c for c in utiles if c["fin"] is not None]
                ref_c = max(avec_fin, key=lambda c: c["fin"]) if avec_fin else min(utiles, key=lambda c: c["debut"])
            rc = ref_c["r"]
            R["salaries"].append({
                "id": sid, "emploi": normaliser_emploi(rc.get("006")), "pcs": rc.get("004") or "", "statut": rc.get("002") or "",
                "niveau": (rc.get("041") or "").strip(), "idcc": rc.get("017") or "", "cadre": rc.get("003") in ("01", "02"),
                "contrat": categorie_contrat(rc), "sexe": "F" if sexe == "02" else "H" if sexe == "01" else "",
                "age": annees_entre(naissance, L) if naissance and naissance <= L else None,
                "anc_mois": mois_entre(min(c["debut"] for c in utiles), L),
                "present": bool(presents), "complet": any(c["debut"] <= F for c in presents),
                "entree": entree, "sortie": sortie, "etp_milli": etp_ind, **S})
    R["arrets"] = sorted(arrets.values(), key=lambda x: (x["debut"], x["cle"]))
    if sans_debut:
        R["alertes"].append(f"{sans_debut} contrat(s) sans date de début : ignoré(s)")
    if R["etp_incomplet"]:
        R["alertes"].append(f"{R['etp_incomplet']} salarié(s) sans quotité de travail lisible : ETP non calculable")
    if R["effectif_declare"] is not None and R["effectif_declare"] != R["effectif_fin"]:
        R["alertes"].append(f"effectif déclaré {R['effectif_declare']}, effectif recalculé {R['effectif_fin']} (stagiaires et mandataires exclus du recalcul)")
    return R


def analyser(octets: bytes) -> dict:
    """Fichier -> {empreinte, avertissements, declarations: [{siret, mois, type, nature, contenu | refus}]}.
    ErreurDSN si le fichier est illisible. Une même déclaration (SIRET, mois) répétée : la dernière l'emporte."""
    lu = lire(decoder(octets))
    sortie = []
    for decl in lu["declarations"]:
        e = entete(decl)
        if not e["refus"]:
            try:
                e["contenu"] = agreger(decl, e["siret"], e["mois"])
            except ValueError as err:
                e["refus"] = str(err)
        if e["refus"]:
            e.pop("contenu", None)
        else:
            e.pop("refus")
        if "contenu" in e:
            sortie = [x for x in sortie if "refus" in x or (x["siret"], x["mois"]) != (e["siret"], e["mois"])]
        sortie.append(e)
    return {"empreinte": hashlib.sha256(octets).hexdigest(), "avertissements": lu["avertissements"],
            "declarations": sortie}


# ---------------------------------------------------------------------------------------------------------
# Arrêts de travail sur plusieurs mois
# ---------------------------------------------------------------------------------------------------------
def jours_arret(contenus: dict, mois: str):
    """Jours calendaires d'arrêt par motif dans `mois`, pour un établissement.

    `contenus` : {mois: contenu} de tous les mois importés de l'établissement. Les déclarations d'un même
    arrêt (même clé) sont réunies : date de reprise connue -> fin la veille ; sinon fin prévisionnelle ; sinon
    arrêt en cours jusqu'à la fin du dernier mois importé. None si le mois n'est pas importé."""
    if mois not in contenus:
        return None
    dernier_mois = max(contenus)
    an, mo = int(dernier_mois[:4]), int(dernier_mois[5:])
    fin_connue = dt.date(an, mo, calendar.monthrange(an, mo)[1])
    reunis = {}
    for m in sorted(contenus):
        for a in contenus[m].get("arrets", []):
            x = reunis.setdefault(a["cle"], {"motif": a["motif"], "debut": a["debut"], "fin_prevue": None, "reprise": None})
            if a.get("fin_prevue"):
                x["fin_prevue"] = a["fin_prevue"]
            if a.get("reprise"):
                x["reprise"] = a["reprise"]
    an, mo = int(mois[:4]), int(mois[5:])
    F, L = dt.date(an, mo, 1), dt.date(an, mo, calendar.monthrange(an, mo)[1])
    jours = {k: 0 for k in MOTIFS_ARRET}
    for x in reunis.values():
        debut = dt.date.fromisoformat(x["debut"])
        if x["reprise"]:
            fin = dt.date.fromisoformat(x["reprise"]) - dt.timedelta(days=1)
        elif x["fin_prevue"]:
            fin = dt.date.fromisoformat(x["fin_prevue"])
        else:
            fin = fin_connue
        a, b = max(debut, F), min(fin, L)
        if a <= b:
            jours[motif_arret(x["motif"])] += (b - a).days + 1
    return jours


def jours_du_mois(mois: str) -> int:
    return calendar.monthrange(int(mois[:4]), int(mois[5:]))[1]


def canonique(x) -> str:
    """JSON trié et compact : forme de comparaison avec la page."""
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
