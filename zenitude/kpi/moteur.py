"""Moteur de KPI (lot 6).

Évalue les formules de l'onglet KPI de la configuration appliquée, sur un périmètre
(un ou plusieurs dossiers) et une période (liste de mois), sans `eval` ni `exec` :
la formule est analysée par zenitude.config.formules puis parcourue nœud par nœud.

Règles (CLAUDE.md) :
- invariant 1 : une absence de donnée donne « non calculable » avec motif, jamais zéro ;
- invariant 2 : une division par zéro donne « non calculable », motif « dénominateur nul » ;
- invariant 4 : les mesures sont d'abord sommées sur tout le périmètre, puis la formule est
  appliquée. Un ratio groupe est donc toujours un ratio de sommes, jamais une moyenne de ratios ;
- aucun arrondi intermédiaire : l'arrondi n'est appliqué qu'à l'affichage.

Limite du lot 6 : MOYENNE_PONDEREE et DERNIERE demandent des données au grain fin (jour, ligne)
et rendent « non calculable » avec un motif explicite.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, getcontext

from zenitude.config import controles as c
from zenitude.config import formules
from .mesures import NonCalculable

getcontext().prec = 28


def _nc(*valeurs):
    """Premier NonCalculable rencontré (motifs combinés), sinon None."""
    motifs = []
    for v in valeurs:
        if isinstance(v, NonCalculable) and v.motif not in motifs:
            motifs.append(v.motif)
    return NonCalculable(" ; ".join(motifs)) if motifs else None


class Evaluateur:
    def __init__(self, kpis, source, dossiers, mois):
        self.kpis = kpis            # {code: ligne de l'onglet KPI}
        self.source = source
        self.dossiers = list(dossiers)
        self.mois = list(mois)
        self.mesures_utilisees = {}
        self._cache = {}

    def kpi(self, code):
        if code in self._cache:
            return self._cache[code]
        if code not in self.kpis:
            v = NonCalculable(f"KPI {code} inactif ou absent sur la période")
        else:
            arbre = formules.arbre(str(self.kpis[code]["Formule"]))
            v = self._eval(arbre)
        self._cache[code] = v
        return v

    def _eval(self, n):
        k = n[0]
        if k == "num":
            return Decimal(n[1])
        if k == "mesure":
            v = self.source.somme(n[1], self.dossiers, self.mois)
            self.mesures_utilisees[n[1]] = v
            return v
        if k == "kpi":
            return self.kpi(n[1])
        if k == "neg":
            v = self._eval(n[1])
            return v if isinstance(v, NonCalculable) else -v
        if k == "bin":
            a, b = self._eval(n[2]), self._eval(n[3])
            nc = _nc(a, b)
            if nc:
                return nc
            op = n[1]
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if b == 0:
                return NonCalculable("dénominateur nul")
            return a / b
        if k == "cmp":
            a, b = self._eval(n[2]), self._eval(n[3])
            nc = _nc(a, b)
            if nc:
                return nc
            return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b,
                    "<=": a <= b, ">=": a >= b}[n[1]]
        if k == "fonc":
            return self._fonction(n[1], n[2])
        raise ValueError(f"nœud inconnu : {k}")

    def _fonction(self, nom, args):
        if nom == "SOMME":
            # Les mesures sont déjà sommées sur le périmètre et la période.
            return self._eval(args[0])
        if nom == "RATIO":
            num, den = self._eval(args[0]), self._eval(args[1])
            nc = _nc(num, den)
            if nc:
                return nc
            if den == 0:
                return NonCalculable("dénominateur nul")
            return num / den
        if nom == "SI":
            cond = self._eval(args[0])
            if isinstance(cond, NonCalculable):
                return cond
            return self._eval(args[1] if cond else args[2])
        if nom in ("MOYENNE_PONDEREE", "DERNIERE"):
            return NonCalculable(f"fonction {nom} non prise en charge au lot 6")
        return NonCalculable(f"fonction inconnue {nom}")


def kpis_actifs(lignes_kpi, debut, fin):
    """KPI au statut « actif » en vigueur sur la période : {code: ligne}."""
    retenus = {}
    for k in lignes_kpi:
        if str(k.get("Statut") or "").strip() != "actif":
            continue
        code = str(k.get("Code KPI") or "").strip().upper()
        eff = c._date(k.get("Date d'effet")) or date.min
        fin_k = c._date(k.get("Date de fin")) or date.max
        if eff <= fin and debut <= fin_k:
            if code not in retenus or eff > (c._date(retenus[code].get("Date d'effet")) or date.min):
                retenus[code] = k
    return retenus


def affichage(valeur, unite):
    """Arrondi unique, à l'affichage (docs/configuration.md §3.3)."""
    if isinstance(valeur, NonCalculable):
        return "non calculable"
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if unite == "%":
        return f"{(valeur * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)} %".replace(".", ",")
    if unite == "€":
        v = valeur.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return f"{v:,}".replace(",", " ") + " €"
    v = valeur.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{v} {unite}".replace(".", ",").strip()


def calculer(lignes_kpi, source, dossiers, mois):
    """Calcule tous les KPI actifs sur le périmètre. Retourne une liste de résultats (dict)."""
    from .mesures import bornes
    debut, fin = bornes(mois)
    kpis = kpis_actifs(lignes_kpi, debut, fin)
    ev = Evaluateur(kpis, source, dossiers, mois)
    resultats = []
    for code in sorted(kpis):
        k = kpis[code]
        ev.mesures_utilisees = {}
        v = ev.kpi(code)
        unite = str(k.get("Unité") or "").strip()
        r = {
            "code": code,
            "nom": str(k.get("Nom") or "").strip(),
            "formule": str(k.get("Formule") or "").strip(),
            "unite": unite,
            "statut": "non calculable" if isinstance(v, NonCalculable) else "calculé",
            "valeur": None if isinstance(v, NonCalculable) else str(v),
            "affichage": affichage(v, unite),
            "motif": v.motif if isinstance(v, NonCalculable) else None,
            "mesures": {m: (str(x) if not isinstance(x, NonCalculable) else "non calculable")
                        for m, x in sorted(ev.mesures_utilisees.items())},
        }
        resultats.append(r)
    return resultats
