"""Analyse des formules KPI selon la grammaire de docs/configuration.md section 3.

Aucune évaluation de texte : tokenisation et analyse récursive uniquement.
"""
import re
from dataclasses import dataclass, field

MESURES = {
    "CA_HEBERGEMENT": "€", "CA_SERVICES": "€", "PL_CHARGES": "€", "PL_PRODUITS": "€",
    "EBITDA_AJUSTE": "€", "TRESORERIE": "€",
    "LN_VENDUES": "logements-nuits", "LN_DISPONIBLES": "logements-nuits",
}
ARITE = {"SOMME": 1, "RATIO": 2, "MOYENNE_PONDEREE": 2, "DERNIERE": 1, "SI": 3}

_TOKEN = re.compile(r"""
 (?P<ws>\s+)
|(?P<nombre>\d+(?:\.\d+)?)
|(?P<mesure>\[[^\]]*\])
|(?P<kpi>\{[^}]*\})
|(?P<fonc>[A-Za-z_][A-Za-z0-9_]*(?=\())
|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)
|(?P<cmp><=|>=|<>|[<>=])
|(?P<op>[+\-*/();])
""", re.X)


class FormuleError(Exception):
    """Syntaxe invalide : contrôle B16."""


@dataclass
class Analyse:
    refs_kpi: list = field(default_factory=list)
    erreurs: list = field(default_factory=list)  # (code, message)
    unite: object = None


def _tokens(texte):
    pos, out = 0, []
    while pos < len(texte):
        m = _TOKEN.match(texte, pos)
        if not m:
            raise FormuleError(f"caractère non autorisé « {texte[pos]} »")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        val = m.group(kind)
        if kind == "mesure":
            nom = val[1:-1]
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", nom):
                raise FormuleError(f"identifiant de mesure invalide « [{nom}] »")
        if kind == "kpi":
            code = val[1:-1]
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9_\-]*", code):
                raise FormuleError(f"identifiant KPI invalide « {{{code}}} »")
        if kind == "ident":
            raise FormuleError(f"identifiant « {val} » sans parenthèse ouvrante")
        out.append((kind, val))
    return out


class _Parseur:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, attendu=None):
        tok = self.peek()
        if attendu is not None and tok[1] != attendu:
            raise FormuleError(f"« {attendu} » attendu, trouvé « {tok[1] or 'fin de formule'} »")
        self.i += 1
        return tok

    def expr(self, autorise_cmp=False):
        node = self.terme()
        if autorise_cmp and self.peek()[0] == "cmp":
            op = self.take()[1]
            node = ("cmp", op, node, self.expr())
        return node

    def terme(self):
        node = self.facteur_bin()
        while self.peek()[1] in ("+", "-") and self.peek()[0] == "op":
            op = self.take()[1]
            node = ("bin", op, node, self.facteur_bin())
        return node

    def facteur_bin(self):
        node = self.facteur()
        while self.peek()[1] in ("*", "/") and self.peek()[0] == "op":
            op = self.take()[1]
            node = ("bin", op, node, self.facteur())
        return node

    def facteur(self):
        kind, val = self.peek()
        if kind == "nombre":
            self.take()
            return ("num", val)
        if kind == "mesure":
            self.take()
            return ("mesure", val[1:-1])
        if kind == "kpi":
            self.take()
            return ("kpi", val[1:-1])
        if kind == "op" and val == "-":
            self.take()
            return ("neg", self.facteur())
        if kind == "op" and val == "(":
            self.take()
            node = self.expr()
            self.take(")")
            return node
        if kind == "fonc":
            self.take()
            self.take("(")
            args = []
            if self.peek()[1] != ")":
                args.append(self.expr(autorise_cmp=(val == "SI")))
                while self.peek() == ("op", ";"):
                    self.take(";")
                    args.append(self.expr())
            self.take(")")
            return ("fonc", val, args)
        raise FormuleError(f"élément inattendu « {val or 'fin de formule'} »")


def analyser(texte, mesures, kpi_unites):
    """Retourne un Analyse. Lève FormuleError si la syntaxe est invalide."""
    res = Analyse()
    toks = _tokens(texte)
    p = _Parseur(toks)
    arbre = p.expr()
    if p.i != len(toks):
        raise FormuleError(f"élément en trop « {toks[p.i][1]} »")
    res.unite = _unite(arbre, mesures, kpi_unites, res)
    return res


def _unite(n, mesures, kpi_unites, res):
    k = n[0]
    if k == "num":
        return "nombre"
    if k == "mesure":
        if n[1] not in mesures:
            res.erreurs.append(("B16", f"mesure inconnue [{n[1]}]"))
            return None
        return mesures[n[1]]
    if k == "kpi":
        res.refs_kpi.append(n[1])
        if n[1] not in kpi_unites:
            res.erreurs.append(("B16", f"KPI inconnu {{{n[1]}}}"))
            return None
        return kpi_unites[n[1]]
    if k == "neg":
        return _unite(n[1], mesures, kpi_unites, res)
    if k == "cmp":
        _unite(n[2], mesures, kpi_unites, res)
        _unite(n[3], mesures, kpi_unites, res)
        return "booleen"
    if k == "bin":
        u1 = _unite(n[2], mesures, kpi_unites, res)
        u2 = _unite(n[3], mesures, kpi_unites, res)
        if n[1] in ("+", "-"):
            if u1 == "nombre":
                return u2
            if u2 == "nombre":
                return u1
            if u1 == u2:
                return u1
            if u1 is not None and u2 is not None:
                res.erreurs.append(("B18", f"unités incompatibles : {u1} et {u2}"))
            return None
        if u1 == "nombre":
            return u2
        if u2 == "nombre":
            return u1
        return None
    if k == "fonc":
        nom, args = n[1], n[2]
        if nom not in ARITE:
            res.erreurs.append(("B16", f"fonction inconnue « {nom} »"))
            for a in args:
                _unite(a, mesures, kpi_unites, res)
            return None
        if len(args) != ARITE[nom]:
            res.erreurs.append(("B16", f"{nom} attend {ARITE[nom]} argument(s), reçu {len(args)}"))
        if nom == "SI" and args and args[0][0] != "cmp":
            res.erreurs.append(("B16", "SI : la première partie doit être une condition"))
        unites = [_unite(a, mesures, kpi_unites, res) for a in args]
        if nom == "RATIO":
            return None
        if nom == "SI":
            return unites[1] if len(unites) == 3 and unites[1] == unites[2] else None
        return unites[0] if unites else None
    raise FormuleError("arbre inconnu")
