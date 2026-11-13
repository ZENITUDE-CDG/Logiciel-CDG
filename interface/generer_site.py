"""Génère la page d'accueil du site (index.html à la racine du dépôt), affichée par GitHub Pages.

Le navigateur n'exécute aucune formule : tous les chiffres sont calculés ici par le moteur réel
(lots 5 et 6) sur le jeu de démonstration fictif (interface/demo, voir generer_demo.py), puis
intégrés à la page sous forme de résultats.
Le gabarit visuel est dans interface/gabarit.html.

Usage : python interface/generer_site.py [sortie.html]   (par défaut : index.html à la racine)
"""
import json
from decimal import Decimal
import os
import sys
import tempfile
from datetime import datetime

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from zenitude.config import controles as c, couverture, publication  # noqa: E402
from zenitude.config.versions import Depot  # noqa: E402
from zenitude.kpi import moteur  # noqa: E402
from zenitude.kpi.mesures import Source, bornes, charger_exploitation, liste_mois, libelle_mois  # noqa: E402

DEMO = os.path.join(RACINE, "interface", "demo")
GABARIT = os.path.join(RACINE, "interface", "gabarit.html")
LOGO = os.path.join(RACINE, "interface", "logo_zenitude.png")
ANNEE = 2026
ORDRE_KPI = ["TO-SEN", "PRIX-MOYEN", "REVPAR", "REVPAC", "DMS", "CAPTAGE-PDJ"]
# Dernier mois importé de la comptabilité (démonstration) : les mois suivants sont affichés en projection.
# Tant que le module Budgets n'existe pas, la projection reprend les écritures fictives de ces mois.
DERNIER_MOIS_IMPORTE = f"{ANNEE}-10"

# Présentation du tableau EBITDA (lot 8). Provisoire : à reporter dans l'onglet Rubriques du classeur
# de configuration et à valider par le contrôle de gestion. Chaque compte de classe 6 ou 7 doit tomber
# dans une seule ligne ; un compte non couvert apparaît dans « Comptes non classés ».
LIGNES_EBITDA = [
    # code, libellé, préfixes de comptes ou formule, sens (produit / charge / total), niveau
    ("CA_HEB", "CA hébergement", ["706"], "produit", 2),
    ("CA_SERV", "CA autres services", ["708"], "produit", 2),
    ("CA_NET", "Montant net du chiffre d'affaires", ("+", "CA_HEB", "CA_SERV"), "total", 1),
    ("PERSO", "Charges de personnel", ["641", "645"], "charge", 2),
    ("ACHATS", "Achats consommés et énergies", ["606"], "charge", 2),
    ("MAINT", "Entretien et maintenance", ["615"], "charge", 2),
    ("TELECOM", "Frais postaux et télécommunications", ["626"], "charge", 2),
    ("DEPL", "Déplacements, missions et réceptions", ["625"], "charge", 2),
    ("AUTRES", "Autres charges de gestion courante", ["658"], "charge", 2),
    ("FRAIS_OP", "Frais opérationnels", ("+", "PERSO", "ACHATS", "MAINT", "TELECOM", "DEPL", "AUTRES"), "total", 1),
    ("GOP", "Résultat brut d'exploitation (GOP)", ("-", "CA_NET", "FRAIS_OP"), "total", 1),
    ("LOYERS", "Loyers immobiliers", ["6132"], "charge", 2),
    ("EBITDA", "EBITDA", ("-", "GOP", "LOYERS"), "total", 0),
    ("FIN", "Charges financières", ["661"], "charge", 2),
    ("RCAI", "Résultat courant avant impôt", ("-", "EBITDA", "FIN"), "total", 1),
]
LIBELLES_JOURNAUX = {"VT": "Ventes", "HA": "Achats", "BQ": "Banque", "OD": "Opérations diverses", "AN": "À-nouveaux"}


def _depot(config):
    d = Depot(os.path.join(tempfile.mkdtemp(), "store"))
    vid = d.deposer(config, "alice")
    d.approuver(vid, "bob")
    d.appliquer(vid, "bob")
    return d


def _feuilles(classeur):
    ctx = c._Ctx(c.Rapport(chemin=classeur), set(), None)
    c._lire(ctx, classeur)
    return ctx.feuilles


def _periodes():
    out = [{"id": m, "libelle": libelle_mois(m).capitalize(), "mois": [m], "type": "mois"}
           for m in liste_mois(f"{ANNEE}-01", f"{ANNEE}-12")]
    for t in range(4):
        mois = liste_mois(f"{ANNEE}-{3 * t + 1:02d}", f"{ANNEE}-{3 * t + 3:02d}")
        out.append({"id": f"T{t + 1}-{ANNEE}", "libelle": f"{t + 1}{'er' if t == 0 else 'e'} trimestre {ANNEE}",
                    "mois": mois, "type": "trimestre"})
    out.append({"id": f"A-{ANNEE}", "libelle": f"Année civile {ANNEE}",
                "mois": liste_mois(f"{ANNEE}-01", f"{ANNEE}-12"), "type": "annee"})
    return out


def _resume(res):
    return {k["code"]: {"statut": k["statut"], "affichage": k["affichage"], "valeur": k["valeur"],
                        "motif": k["motif"]} for k in res}


def _ligne_du_compte(compte):
    """Ligne EBITDA d'un compte (préfixe le plus long), ou None si non couvert."""
    meilleur = None
    for code, _, regle, sens, _ in LIGNES_EBITDA:
        if isinstance(regle, list):
            for pref in regle:
                if compte.startswith(pref) and (meilleur is None or len(pref) > meilleur[1]):
                    meilleur = (code, len(pref))
    return meilleur[0] if meilleur else None


def _ebitda(ecritures, dossiers, mois):
    """Tableau EBITDA par mois (montants en Decimal arrondis au centime, chaînes dans la page)."""
    dossiers = set(dossiers)
    brut = {m: {} for m in mois}
    non_classes = set()
    for e in ecritures:
        if e["dossier"] not in dossiers:
            continue
        m = e["date"][:7]
        if m not in brut or not e["compte"][:1] in ("6", "7"):
            continue
        ligne = _ligne_du_compte(e["compte"])
        if ligne is None:
            non_classes.add(e["compte"])
            continue
        montant = Decimal(e["credit"] or 0) - Decimal(e["debit"] or 0)
        brut[m][ligne] = brut[m].get(ligne, Decimal("0")) + montant
    sens = {code: s for code, _, _, s, _ in LIGNES_EBITDA}

    def calc(valeurs):
        out = {}
        for code, _, regle, s, _ in LIGNES_EBITDA:
            if isinstance(regle, list):
                v = valeurs.get(code)
                out[code] = None if v is None else (v if s == "produit" else -v)
            else:
                op, *termes = regle
                vals = [out[t] for t in termes]
                if all(v is None for v in vals):
                    out[code] = None
                    continue
                vals = [v or Decimal("0") for v in vals]
                out[code] = sum(vals, Decimal("0")) if op == "+" else vals[0] - sum(vals[1:], Decimal("0"))
        return out

    def chaine(d):
        return {k: (None if v is None else str(v.quantize(Decimal("0.01")))) for k, v in d.items()}

    def taux(d):
        if d.get("CA_NET") in (None, Decimal("0")) or d.get("EBITDA") is None:
            return None
        return str((d["EBITDA"] / d["CA_NET"] * 100).quantize(Decimal("0.1")))

    par_mois, cumul_r, cumul_t = {}, {}, {}
    for m in mois:
        d = calc(brut[m])
        par_mois[m] = dict(chaine(d), TAUX_EBITDA=taux(d))
        for code in brut[m]:
            cumul_t[code] = cumul_t.get(code, Decimal("0")) + brut[m][code]
            if m <= DERNIER_MOIS_IMPORTE:
                cumul_r[code] = cumul_r.get(code, Decimal("0")) + brut[m][code]
    tr, tt = calc(cumul_r), calc(cumul_t)
    return {"mois": par_mois, "realise": dict(chaine(tr), TAUX_EBITDA=taux(tr)),
            "total": dict(chaine(tt), TAUX_EBITDA=taux(tt)), "non_classes": sorted(non_classes)}


def _groupes_crees(feuille, residences):
    """Groupes actifs de l'onglet Groupes (manuels ou dynamiques)."""
    out = []
    par_code = {r["code"]: r for r in residences}
    attributs = {"Activité": "activite", "Région": "region"}
    for g in feuille:
        if str(g.get("Statut") or "").strip() != "actif":
            continue
        membres = set()
        if str(g.get("Type") or "").strip() == "dynamique":
            criteres = []
            for col in ("Critère 1 (attribut = valeur)", "Critère 2"):
                txt = str(g.get(col) or "").strip()
                if "=" in txt:
                    a, v = (x.strip() for x in txt.split("=", 1))
                    if a in attributs:
                        criteres.append((attributs[a], v))
            et = str(g.get("Opérateur (ET / OU)") or "ET").strip().upper() != "OU"
            for r in residences:
                tests = [r[a] == v for a, v in criteres]
                if tests and (all(tests) if et else any(tests)):
                    membres.add(r["code"])
        for x in str(g.get("Inclusions manuelles (codes RES, séparés par ;)") or "").split(";"):
            if x.strip() in par_code:
                membres.add(x.strip())
        for x in str(g.get("Exclusions (codes RES, séparés par ;)") or "").split(";"):
            membres.discard(x.strip())
        if membres:
            out.append({"id": "GRP-" + str(g["Code groupe"]).strip(), "libelle": str(g["Nom"]).strip(),
                        "type": "groupe-cree", "dossiers": sorted(par_code[c]["dossier"] for c in membres)})
    return out


def _decaler(d, n):
    from datetime import date as _d
    m = d.month - 1 + n
    return _d(d.year + m // 12, m % 12 + 1, d.day)


def construire(demo=DEMO):
    ECR, EXE, MES, CONFIG = (os.path.join(demo, n) for n in
                             ("ecritures.csv", "exercices.csv", "mesures.csv", "configuration.xlsx"))
    depot = _depot(CONFIG)
    etat = depot._lire()
    version = next(v for v in etat["versions"] if v["id"] == etat["courante"])
    classeur = os.path.join(depot.fichiers, version["empreinte"] + ".xlsx")
    f = _feuilles(classeur)
    ecritures = couverture.charger_ecritures(ECR)
    exploitation = charger_exploitation(MES)
    source = Source(f.get("Rubriques", []), ecritures, exploitation)
    exercices = couverture.charger_exercices(EXE)

    residences = []
    for r in f.get("Referentiel", []):
        if str(r.get("Statut") or "").strip() != "actif":
            continue
        dossier = str(r["Dossier Pennylane (identifiant)"]).strip()
        debut, fin = exercices.get(dossier, (None, None))
        residences.append({"dossier": dossier, "code": str(r.get("Identifiant interne") or "").strip(), "nom": str(r["Nom de la résidence"]).strip(),
                           "activite": str(r["Activité"]).strip(), "region": str(r.get("Région") or "").strip(),
                           "exercice": [debut.isoformat(), fin.isoformat()] if debut else None})
    residences.sort(key=lambda x: x["nom"])

    perimetres = [{"id": "GROUPE", "libelle": "Groupe Zenitude", "type": "groupe",
                   "dossiers": [r["dossier"] for r in residences]}]
    for act in sorted({r["activite"] for r in residences}):
        perimetres.append({"id": "ACT-" + act.upper(), "libelle": f"Activité {act}", "type": "activite",
                           "dossiers": [r["dossier"] for r in residences if r["activite"] == act]})
    for reg in sorted({r["region"] for r in residences if r["region"]}):
        perimetres.append({"id": "REG-" + reg.upper().replace(" ", "-"), "libelle": reg, "type": "region",
                           "dossiers": [r["dossier"] for r in residences if r["region"] == reg]})
    perimetres += _groupes_crees(f.get("Groupes", []), residences)
    for r in residences:
        perimetres.append({"id": r["dossier"], "libelle": r["nom"], "type": "residence",
                           "dossiers": [r["dossier"]]})

    periodes = _periodes()
    resultats = {}
    for p in perimetres:
        for per in periodes:
            res = moteur.calculer(f.get("KPI", []), source, p["dossiers"], per["mois"])
            resultats[f"{p['id']}|{per['id']}"] = _resume(res)
        if p["type"] == "residence" and p["dossiers"][0] in exercices:
            mois = liste_mois(*exercices[p["dossiers"][0]])
            res = moteur.calculer(f.get("KPI", []), source, p["dossiers"], mois)
            resultats[f"{p['id']}|EXERCICE"] = _resume(res)

    actifs = moteur.kpis_actifs(f.get("KPI", []), *bornes(liste_mois(f"{ANNEE}-01", f"{ANNEE}-12")))
    codes = [k for k in ORDRE_KPI if k in actifs] + sorted(k for k in actifs if k not in ORDRE_KPI)
    kpi_defs = [{"code": k, "nom": str(actifs[k].get("Nom") or ""), "formule": str(actifs[k].get("Formule") or ""),
                 "definition": str(actifs[k].get("Définition") or ""), "unite": str(actifs[k].get("Unité") or ""),
                 "approbateur": str(actifs[k].get("Approbateur") or ""), "principal": k in ORDRE_KPI}
                for k in codes]

    # Compte de résultat (lot 5) : une publication par dossier sur son exercice
    finance = []
    for r in residences:
        try:
            _, inst = publication.publier(depot, ECR, EXE, r["dossier"], "carol")
            finance.append({"dossier": r["dossier"], "nom": r["nom"], "exercice": inst["exercice"],
                            "resultat": inst["resultat"], "statut": "publié"})
        except publication.PublicationBloquee as e:
            finance.append({"dossier": r["dossier"], "nom": r["nom"], "statut": "bloqué",
                            "motif": "comptes non classés : " + ", ".join(e.non_classes)})

    # Couverture des données par dossier et par mois
    mois_annee = liste_mois(f"{ANNEE}-01", f"{ANNEE}-12")
    mois_ecr = {(e["dossier"], e["date"][:7]) for e in ecritures}
    noms_mesures = sorted({k[2] for k in exploitation})
    couv = {}
    for r in residences:
        d = r["dossier"]
        couv[d] = {m: {"compta": (d, m) in mois_ecr,
                       "exploitation": sum((d, m, x) in exploitation for x in noms_mesures),
                       "attendu": len(noms_mesures)} for m in mois_annee}

    # Tableau EBITDA (lot 8) par périmètre, mois civils de l'année
    ebitda = {p["id"]: _ebitda(ecritures, p["dossiers"], mois_annee) for p in perimetres}

    # Import comptable : exercices N-1, N, N+1 de chaque dossier et volume d'écritures
    imports = {}
    for r in residences:
        d = r["dossier"]
        if d not in exercices:
            continue
        debut, fin = exercices[d]
        lignes_d = [e for e in ecritures if e["dossier"] == d]
        rangs = []
        for rang, n in (("N-1", -12), ("N", 0), ("N+1", 12)):
            db, fn = _decaler(debut, n), _decaler(fin, n)
            # Seules les écritures jusqu'au dernier mois importé comptent comme importées ;
            # les mois suivants servent de projection (démonstration)
            dedans = [e for e in lignes_d if db.isoformat() <= e["date"] <= fn.isoformat()
                      and e["date"][:7] <= DERNIER_MOIS_IMPORTE]
            dates = sorted(e["date"] for e in dedans)
            rangs.append({"rang": rang, "debut": db.isoformat(), "fin": fn.isoformat(), "ecritures": len(dedans),
                          "periode_importee": [dates[0], dates[-1]] if dates else None})
        imports[d] = rangs

    # Journaux et plan comptable (comptes de classes 6 et 7 présents dans les écritures)
    journaux, comptes = {}, {}
    rubriques = f.get("Rubriques", [])
    for e in ecritures:
        j = journaux.setdefault(e["journal"], {"code": e["journal"], "libelle": LIBELLES_JOURNAUX.get(e["journal"], ""),
                                               "lignes": 0, "dossiers": set()})
        j["lignes"] += 1
        j["dossiers"].add(e["dossier"])
        c_ = comptes.setdefault(e["compte"], {"compte": e["compte"], "lignes": 0})
        c_["lignes"] += 1
    libelles = {l[0]: l[1] for l in LIGNES_EBITDA}
    plan = []
    for num in sorted(comptes):
        rub = [r for r in rubriques if num.startswith(str(r.get("Préfixe ou plage de comptes") or "#"))]
        ligne = _ligne_du_compte(num) if num[:1] in "67" else None
        plan.append({"compte": num, "classe": num[0], "lignes": comptes[num]["lignes"],
                     "rubrique": rub[0]["Code rubrique"] if rub else None,
                     "agregat": rub[0]["Agrégat de base"] if rub else None,
                     "ligne_ebitda": libelles.get(ligne) if ligne else None})
    journaux = [dict(j, dossiers=len(j["dossiers"])) for j in sorted(journaux.values(), key=lambda x: x["code"])]

    statut = depot.statut()
    return {
        "meta": {"version_config": version["id"], "empreinte_config": version["empreinte"],
                 "genere_le": datetime.now().strftime("%d/%m/%Y à %H:%M"), "annee": ANNEE,
                 "periode_defaut": DERNIER_MOIS_IMPORTE,
                 "nb_ecritures": len(ecritures), "nb_mesures": len(exploitation),
                 "mesures": noms_mesures, "donnees": "fictives (phase test)",
                 "dernier_mois_importe": DERNIER_MOIS_IMPORTE},
        "residences": residences, "perimetres": perimetres, "periodes": periodes,
        "kpi": kpi_defs, "resultats": resultats, "finance": finance, "couverture": couv,
        "mois": mois_annee,
        "lignes_ebitda": [{"code": c_, "libelle": l, "niveau": n, "sens": s_} for c_, l, _, s_, n in LIGNES_EBITDA],
        "ebitda": ebitda, "imports": imports, "journaux": journaux, "plan": plan,
        "versions": statut["versions"], "journal": statut["journal"],
    }


def main(sortie, demo=DEMO):
    if not os.path.exists(os.path.join(demo, "configuration.xlsx")):
        sys.path.insert(0, os.path.join(RACINE, "interface"))
        import generer_demo
        generer_demo.main(demo)
    donnees = construire(demo)
    gabarit = open(GABARIT, encoding="utf-8").read()
    texte = json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    import base64
    with open(LOGO, "rb") as fh:
        logo = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    with open(sortie, "w", encoding="utf-8") as fh:
        fh.write(gabarit.replace("__LOGO__", logo).replace("/*__DONNEES__*/null", texte))
    print("site écrit :", sortie)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "index.html"))
