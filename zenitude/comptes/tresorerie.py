"""Trésorerie, créances clients et dettes fournisseurs (lot 11).

Calcul par dossier, à partir des écritures, avec trois colonnes facultatives :
  tiers     compte auxiliaire (client ou fournisseur) ;
  lettrage  code de lettrage Pennylane (vide = non lettré) ;
  echeance  échéance de la pièce (AAAA-MM-JJ), si elle est exportée.

Définitions (documentées dans docs/tresorerie.md) :
- créance = ligne au débit d'un compte client (411, 413, 416, 418) ; dette = ligne au crédit d'un compte
  fournisseur (401, 403). Règlement = ligne de sens inverse portant le même lettrage chez le même tiers ;
- une pièce est soldée à la date d'arrêté A si son groupe de lettrage est équilibré et si le dernier
  mouvement du groupe est daté au plus de A. Sinon elle est ouverte à A (un lettrage partiel laisse la
  pièce ouverte pour son montant total) ;
- les lignes de sens inverse non lettrées (avoirs, acomptes, règlements à affecter) sont comptées à part ;
- échéance : celle de la pièce (mode « piece », « échéance inconnue » si elle manque) ou date de la pièce
  + 30, 45 ou 60 jours. Une pièce est échue si son échéance est antérieure à A ;
- retards : 1 à 30 jours, 31 à 60, 61 à 90, plus de 90 ;
- à-nouveaux (journal AN) : suivis à part, datés de l'ouverture ;
- position de trésorerie : solde des comptes 51 et 53 (disponibilités nettes des concours bancaires
  courants, valeurs mobilières de placement exclues), encaissements et décaissements = mouvements des
  comptes de disponibilités hors à-nouveaux ;
- sans aucun lettrage dans les écritures d'un dossier, créances et dettes sont « non calculables »
  (invariant 1) ; une échéance absente en mode « piece » donne « échéance inconnue », jamais « non échu » ;
- montants en centimes entiers ; les ratios se calculent sur des sommes (invariant 4), jamais en moyenne.

Les agrégats sont additifs par dossier : la page les somme sur un périmètre, sans refaire de calcul comptable.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal

CLIENTS = ("411", "413", "416", "418")
FOURNISSEURS = ("401", "403")
DISPONIBILITES = ("51", "53")
MODES = ("30", "45", "60", "piece")
TRANCHES = ("non_echu", "b1", "b2", "b3", "b4", "inconnue")
LIBELLES_TRANCHES = {"non_echu": "Non échu", "b1": "1 à 30 j", "b2": "31 à 60 j", "b3": "61 à 90 j",
                     "b4": "Plus de 90 j", "inconnue": "Échéance inconnue"}
ZERO = Decimal("0")


def _cents(v):
    return int((v * 100).quantize(Decimal("1")))


def fin_de_mois(mois):
    a, m = int(mois[:4]), int(mois[5:7])
    return date(a, m, calendar.monthrange(a, m)[1])


def _date(s):
    s = (s or "").strip()
    return date.fromisoformat(s[:10]) if s else None


def _lignes(ecritures, dossier, prefixes):
    out = []
    for e in ecritures:
        if e["dossier"] != dossier or not e["compte"].startswith(prefixes):
            continue
        out.append({"date": date.fromisoformat(e["date"]), "journal": e["journal"], "compte": e["compte"],
                    "debit": Decimal(e["debit"] or 0), "credit": Decimal(e["credit"] or 0),
                    "tiers": (e.get("tiers") or "").strip(), "lettrage": (e.get("lettrage") or "").strip(),
                    "echeance": _date(e.get("echeance"))})
    return out


def _groupes(lignes):
    g = {}
    for l in lignes:
        if l["lettrage"]:
            s = g.setdefault((l["tiers"] or l["compte"], l["lettrage"]), {"solde": ZERO, "date": date.min})
            s["solde"] += l["debit"] - l["credit"]
            s["date"] = max(s["date"], l["date"])
    return g


def _solde_a(l, groupes, arrete):
    g = groupes.get((l["tiers"] or l["compte"], l["lettrage"])) if l["lettrage"] else None
    return bool(g and g["solde"] == 0 and g["date"] <= arrete)


def _tranche(echeance, arrete):
    if echeance is None:
        return "inconnue"
    if echeance >= arrete:
        return "non_echu"
    retard = (arrete - echeance).days
    return "b1" if retard <= 30 else "b2" if retard <= 60 else "b3" if retard <= 90 else "b4"


def _analyse(lignes, groupes, arrete, mois, creance):
    """Un arrêté : historique par mois de pièce, à-nouveaux, ouvert par tranche et mode, crédits non affectés."""
    facture_k, regl_k = ("debit", "credit") if creance else ("credit", "debit")
    hist = {m: [ZERO, ZERO] for m in mois}
    an = [ZERO, ZERO, ZERO]
    ouvert = {mode: {t: ZERO for t in TRANCHES} for mode in MODES}
    non_affectes = ZERO
    for l in lignes:
        if l["date"] > arrete:
            continue
        if l[facture_k] == 0:
            if l[regl_k] and not l["lettrage"]:
                non_affectes += l[regl_k]
            continue
        montant = l[facture_k]
        soldee = _solde_a(l, groupes, arrete)
        if l["journal"] == "AN":
            an[0] += montant
            an[1 if soldee else 2] += montant
        else:
            m = l["date"].isoformat()[:7]
            if m in hist:
                hist[m][0] += montant
                if soldee:
                    hist[m][1] += montant
        if not soldee:
            for mode in MODES:
                ech = l["echeance"] if mode == "piece" else l["date"] + timedelta(days=int(mode))
                ouvert[mode][_tranche(ech, arrete)] += montant
    return {"hist": {m: [_cents(a), _cents(b)] for m, (a, b) in hist.items()},
            "an": [_cents(x) for x in an],
            "ouvert": {mode: [_cents(ouvert[mode][t]) for t in TRANCHES] for mode in MODES},
            "credits_non_affectes": _cents(non_affectes)}


def _position(lignes, mois):
    out = {}
    for m in mois:
        fin = fin_de_mois(m)
        solde = sum((l["debit"] - l["credit"] for l in lignes if l["date"] <= fin), ZERO)
        enc = sum((l["debit"] for l in lignes if l["journal"] != "AN" and l["date"].isoformat()[:7] == m), ZERO)
        dec = sum((l["credit"] for l in lignes if l["journal"] != "AN" and l["date"].isoformat()[:7] == m), ZERO)
        out[m] = [_cents(solde), _cents(enc), _cents(dec)]
    return out


def calculer_dossier(ecritures, dossier, mois):
    """Agrégats de trésorerie d'un dossier pour chaque mois de `mois` (arrêtés = fins de mois)."""
    cli, fou, dispo = (_lignes(ecritures, dossier, p) for p in (CLIENTS, FOURNISSEURS, DISPONIBILITES))
    lettre = any(l["lettrage"] for l in cli + fou)
    res = {"lettrage": lettre, "echeance": any(l["echeance"] for l in cli + fou),
           "position": _position(dispo, mois) if dispo else None, "creances": None, "dettes": None}
    if lettre:
        gc, gf = _groupes(cli), _groupes(fou)
        res["creances"] = {m: _analyse(cli, gc, fin_de_mois(m), mois, True) for m in mois}
        res["dettes"] = {m: _analyse(fou, gf, fin_de_mois(m), mois, False) for m in mois}
    return res
