"""Publie les chiffres calculés par le moteur dans la base de test Supabase (lot 13, décision 0007).

Lancé par GitHub Actions après les tests, à chaque dépôt sur main (ou à la main : onglet Actions,
« Run workflow »). Rien ne tourne sur un poste de travail.

1. Le moteur Python calcule tout, comme pour le site (generer_site.construire) : compte de résultat
   PCG figé, montants mensuels par compte, trésorerie, couverture, KPI...
2. Les résultats sont découpés : une partie commune (paramètres, sans aucune donnée de résidence)
   et une partie par résidence. La base ne laisse lire à chacun que les résidences de son parc
   (migrations/004_donnees_ajustements.sql).
3. Les deux parties sont écrites dans donnees_communes et donnees_residences avec la clé secrète,
   lue dans la variable d'environnement SUPABASE_SECRET_KEY (secret GitHub, jamais dans le dépôt).

Garde-fous : seules les résidences déjà créées dans la base et marquées « fictif » reçoivent des
données ; la publication s'arrête si l'une d'elles est marquée réelle (invariant 8).

Usage :
  python interface/publier_supabase.py             publie (SUPABASE_SECRET_KEY obligatoire)
  python interface/publier_supabase.py --essai DIR  écrit les lignes dans DIR, sans rien envoyer
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from copy import deepcopy

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "interface"))
sys.path.insert(0, RACINE)

import generer_site  # noqa: E402
from zenitude.config import couverture  # noqa: E402
from zenitude.kpi.mesures import charger_exploitation  # noqa: E402

# Clés des données du site propres à une résidence ou calculées sur un périmètre de résidences :
# elles ne vont jamais dans la partie commune.
PAR_RESIDENCE = ("residences", "perimetres", "resultats", "ebitda", "sig", "finance", "couverture",
                 "imports", "plan", "journaux")


class PublicationRefusee(Exception):
    pass


def empreinte(objet):
    texte = json.dumps(objet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def decouper(donnees, ecritures, exploitation):
    """Découpe les données du site en (commun, {dossier: contenu}).

    La page en ligne recompose exactement les données du site à partir de ces morceaux, pour les
    seules résidences visibles (fonction assemblerDonnees de interface/gabarit.html).
    """
    commun = {k: deepcopy(v) for k, v in donnees.items() if k not in PAR_RESIDENCE}
    for k in ("nb_ecritures", "nb_mesures"):
        commun["meta"].pop(k, None)
    for k in ("compta", "couverts", "exploitation"):
        commun["calcul"].pop(k, None)
    commun["tresorerie"].pop("dossiers", None)
    # Classement des comptes (configuration) sans les volumes, qui dépendent des résidences.
    commun["plan_comptes"] = {p["compte"]: {k: v for k, v in p.items() if k not in ("compte", "lignes")}
                              for p in donnees["plan"]}
    commun["journaux_libelles"] = {j["code"]: j["libelle"] for j in donnees["journaux"]}
    # Groupes de l'onglet Groupes de la configuration : libellés dans la partie commune (dans leur ordre),
    # appartenance dans la partie de chaque résidence (une liste de membres révélerait les autres résidences).
    crees = [p for p in donnees["perimetres"] if p["type"] == "groupe-cree"]
    commun["groupes_config"] = [{"id": p["id"], "libelle": p["libelle"]} for p in crees]

    finance = {f["dossier"]: f for f in donnees["finance"]}
    calcul, treso = donnees["calcul"], donnees["tresorerie"]["dossiers"]
    par = {}
    for r in donnees["residences"]:
        d = r["dossier"]
        lignes = [e for e in ecritures if e["dossier"] == d]
        comptes, journaux = {}, {}
        for e in lignes:
            comptes[e["compte"]] = comptes.get(e["compte"], 0) + 1
            journaux[e["journal"]] = journaux.get(e["journal"], 0) + 1
        par[d] = {
            "residence": r,
            "finance": finance.get(d),
            "tresorerie": treso.get(d),
            "couverture": donnees["couverture"].get(d),
            "imports": donnees["imports"].get(d),
            "compta": calcul["compta"].get(d, {}),
            "couverts": calcul["couverts"].get(d, []),
            "exploitation": calcul["exploitation"].get(d, {}),
            "groupes_config": [p["id"] for p in crees if d in p["dossiers"]],
            "comptes_lignes": comptes,
            "journaux_lignes": journaux,
            "nb_ecritures": len(lignes),
            "nb_mesures": sum(1 for k in exploitation if k[0] == d),
        }
    return commun, par


def lignes_a_publier(commun, par, residences_base):
    """Lignes à écrire, d'après les résidences déjà présentes dans la base.

    residences_base : [{"id", "dossier_pennylane", "fictif"}]. Renvoie (ligne commune, lignes par
    résidence, avertissements). Refuse toute résidence marquée réelle.
    """
    reelles = [r["id"] for r in residences_base if r.get("dossier_pennylane") in par and not r.get("fictif")]
    if reelles:
        raise PublicationRefusee("résidences marquées réelles (fictif = false) : " + ", ".join(sorted(reelles))
                                 + ". Phase test : aucune donnée n'est publiée sur une résidence réelle.")
    par_dossier = {}
    for r in residences_base:
        if r.get("dossier_pennylane"):
            par_dossier.setdefault(r["dossier_pennylane"], []).append(r["id"])
    doubles = {d: ids for d, ids in par_dossier.items() if len(ids) > 1 and d in par}
    if doubles:
        raise PublicationRefusee("dossier Pennylane rattaché à plusieurs résidences : "
                                 + "; ".join(f"{d} ({', '.join(sorted(i))})" for d, i in sorted(doubles.items())))
    lignes, avert = [], []
    for d in sorted(par):
        if d not in par_dossier:
            avert.append(f"dossier {d} calculé mais absent de la base (aucune résidence) : non publié")
            continue
        contenu = par[d]
        lignes.append({"residence_id": par_dossier[d][0], "contenu": contenu, "empreinte": empreinte(contenu),
                       "fictif": True})
    for r in residences_base:
        if r.get("dossier_pennylane") not in par:
            avert.append(f"résidence {r['id']} sans données calculées (dossier {r.get('dossier_pennylane') or 'non renseigné'})")
    if not lignes:
        raise PublicationRefusee("aucune résidence de la base ne correspond aux dossiers calculés. "
                                 "Lancer d'abord scripts/installation_supabase.sql dans Supabase.")
    commune = {"id": "SITE", "contenu": commun, "empreinte": empreinte(commun), "fictif": True}
    return commune, lignes, avert


# ---------------------------------------------------------------------------- Supabase (REST)

def url_supabase():
    texte = open(os.path.join(RACINE, "app", "config.js"), encoding="utf-8").read()
    m = re.search(r'supabaseUrl:\s*"(https://[^"]+)"', texte)
    if not m:
        raise PublicationRefusee("adresse Supabase introuvable dans app/config.js")
    return m.group(1).rstrip("/")


def entetes(cle):
    """Clé secrète récente (sb_secret_...) : en-tête apikey seul. Ancienne clé service_role (jeton) :
    apikey et Authorization."""
    h = {"apikey": cle, "Content-Type": "application/json"}
    if cle.startswith("eyJ"):
        h["Authorization"] = "Bearer " + cle
    return h


def requete(methode, url, cle, corps=None, prefer=None):
    h = entetes(cle)
    if prefer:
        h["Prefer"] = prefer
    data = None if corps is None else json.dumps(corps, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=60) as rep:
            texte = rep.read().decode("utf-8")
            return json.loads(texte) if texte else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise PublicationRefusee(f"Supabase a refusé {methode} {url.split('/rest/v1/')[-1]} "
                                 f"(code {e.code}) : {detail}") from None


def publier(base, cle, commune, lignes, envoyer=requete):
    rest = base + "/rest/v1/"
    envoyer("POST", rest + "donnees_communes?on_conflict=id", cle, [commune],
            "resolution=merge-duplicates,return=minimal")
    for ligne in lignes:
        envoyer("POST", rest + "donnees_residences?on_conflict=residence_id", cle, [ligne],
                "resolution=merge-duplicates,return=minimal")


def calculer(demo=generer_site.DEMO):
    if not os.path.exists(os.path.join(demo, "configuration.xlsx")):
        import generer_demo
        generer_demo.main(demo)
    donnees = generer_site.construire(demo)
    ecritures = couverture.charger_ecritures(os.path.join(demo, "ecritures.csv"))
    exploitation = charger_exploitation(os.path.join(demo, "mesures.csv"))
    return decouper(donnees, ecritures, exploitation)


def main(argv):
    commun, par = calculer()
    if len(argv) >= 2 and argv[0] == "--essai":
        dossier = argv[1]
        os.makedirs(dossier, exist_ok=True)
        base = [{"id": r["residence"]["code"], "dossier_pennylane": d, "fictif": True} for d, r in par.items()]
        commune, lignes, avert = lignes_a_publier(commun, par, base)
        with open(os.path.join(dossier, "donnees_communes.json"), "w", encoding="utf-8") as fh:
            json.dump(commune, fh, ensure_ascii=False)
        with open(os.path.join(dossier, "donnees_residences.json"), "w", encoding="utf-8") as fh:
            json.dump(lignes, fh, ensure_ascii=False)
        print(f"essai : {len(lignes)} résidences écrites dans {dossier}, rien n'est envoyé")
        return 0
    cle = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    if not cle:
        print("ERREUR : secret SUPABASE_SECRET_KEY absent. Dans GitHub : Settings, Secrets and variables, "
              "Actions, New repository secret.", file=sys.stderr)
        return 1
    if cle.startswith("sb_publishable_"):
        print("ERREUR : SUPABASE_SECRET_KEY contient la clé publique. Il faut la clé secrète (sb_secret_...).",
              file=sys.stderr)
        return 1
    base = url_supabase()
    try:
        residences = requete("GET", base + "/rest/v1/residences?select=id,dossier_pennylane,fictif", cle) or []
        commune, lignes, avert = lignes_a_publier(commun, par, residences)
        publier(base, cle, commune, lignes)
    except PublicationRefusee as e:
        print("ERREUR : " + str(e), file=sys.stderr)
        return 1
    for a in avert:
        print("avertissement : " + a)
    print(f"publié : données communes et {len(lignes)} résidence(s) : "
          + ", ".join(l["residence_id"] for l in lignes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
