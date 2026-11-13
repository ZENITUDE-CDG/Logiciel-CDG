"""Génère la page d'accueil du site (index.html à la racine du dépôt), affichée par GitHub Pages.

Le navigateur n'exécute aucune formule : tous les chiffres sont calculés ici par le moteur réel
(lots 5 et 6) sur le jeu de démonstration fictif (interface/demo, voir generer_demo.py), puis
intégrés à la page sous forme de résultats.
Le gabarit visuel est dans interface/gabarit.html.

Usage : python interface/generer_site.py [sortie.html]   (par défaut : index.html à la racine)
"""
import json
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
ANNEE = 2026
ORDRE_KPI = ["TO-SEN", "PRIX-MOYEN", "REVPAR", "REVPAC", "DMS", "CAPTAGE-PDJ"]


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
        residences.append({"dossier": dossier, "nom": str(r["Nom de la résidence"]).strip(),
                           "activite": str(r["Activité"]).strip(), "region": str(r.get("Région") or "").strip(),
                           "exercice": [debut.isoformat(), fin.isoformat()] if debut else None})
    residences.sort(key=lambda x: x["nom"])

    perimetres = [{"id": "GROUPE", "libelle": "Groupe complet", "type": "groupe",
                   "dossiers": [r["dossier"] for r in residences]}]
    for act in sorted({r["activite"] for r in residences}):
        perimetres.append({"id": "ACT-" + act.upper(), "libelle": f"Activité {act}", "type": "activite",
                           "dossiers": [r["dossier"] for r in residences if r["activite"] == act]})
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

    statut = depot.statut()
    return {
        "meta": {"version_config": version["id"], "empreinte_config": version["empreinte"],
                 "genere_le": datetime.now().strftime("%d/%m/%Y à %H:%M"), "annee": ANNEE,
                 "periode_defaut": f"{ANNEE}-10",
                 "nb_ecritures": len(ecritures), "nb_mesures": len(exploitation),
                 "mesures": noms_mesures, "donnees": "fictives (phase test)"},
        "residences": residences, "perimetres": perimetres, "periodes": periodes,
        "kpi": kpi_defs, "resultats": resultats, "finance": finance, "couverture": couv,
        "mois": mois_annee,
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
    with open(sortie, "w", encoding="utf-8") as fh:
        fh.write(gabarit.replace("/*__DONNEES__*/null", texte))
    print("site écrit :", sortie)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "index.html"))
