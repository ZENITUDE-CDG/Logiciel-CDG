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

Lot 18 (décision 0011) : si le secret PENNYLANE_TOKEN_PILOTE est présent, le dossier Pennylane de test
(PENNY-TEST, résidence RES-TEST) est lu par le connecteur et publié avec la démonstration. Mode des
écritures : variable PENNYLANE_MODE (« valides » par défaut, ou « tous »). Sans --pennylane, une erreur de
lecture Pennylane n'empêche pas la publication de la démonstration (avertissement).

Lot 18b (décision 0012) : période d'import et masquage du brouillard lus dans la table parametres_import ;
--demande ID traite une demande de la table synchronisations (lancée depuis la page par la fonction serveur
lancer-synchro) : statut « en cours », puis « terminée » ou « échec », avec un résultat sans montant par
résidence (sauf les sommes du brouillard, affichées dans la page).

Usage :
  python interface/publier_supabase.py                 publie (SUPABASE_SECRET_KEY obligatoire)
  python interface/publier_supabase.py --pennylane     publie ; lecture du dossier de test obligatoire
  python interface/publier_supabase.py --demande ID    traite la demande de synchronisation ID
  python interface/publier_supabase.py --essai DIR     écrit les lignes dans DIR, sans rien envoyer
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
                 "imports", "plan", "journaux", "ecritures")


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
            "ecritures": donnees["ecritures"].get(d, []),
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


def calculer(demo=generer_site.DEMO, pennylane=None):
    """Calcule et découpe. pennylane = (lignes, exercice, rapport) du dossier de test (lot 18) ou None.

    Avec le dossier de test, le moteur tourne sur une copie temporaire : démonstration inchangée +
    dossier de test (interface/source_pennylane.py). Rien n'est écrit dans le dépôt.
    """
    if not os.path.exists(os.path.join(demo, "configuration.xlsx")):
        import generer_demo
        generer_demo.main(demo)
    source, provisoires = demo, []
    if pennylane is not None:
        import tempfile
        import source_pennylane
        lignes, exercice, rapport = pennylane
        source = os.path.join(tempfile.mkdtemp(prefix="zen-l18-"), "source")
        provisoires = source_pennylane.assembler(demo, source, lignes, exercice)
    donnees = generer_site.construire(source)
    ecritures = couverture.charger_ecritures(os.path.join(source, "ecritures.csv"))
    exploitation = charger_exploitation(os.path.join(source, "mesures.csv"))
    commun, par = decouper(donnees, ecritures, exploitation)
    if pennylane is not None:
        import source_pennylane
        d = source_pennylane.DOSSIER_TEST
        if d in par:
            par[d]["source"] = {"type": "pennylane", "mode": rapport["mode"], "libelle_mode": rapport["libelle_mode"],
                                "synchronise_le": rapport.get("synchronise_le"),
                                "exercice_retenu": rapport["exercice_retenu"],
                                "comptes_provisoires": provisoires}
    return commun, par


def lire_memo_lettrage(base, cle, dossier, envoyer=None):
    """Groupes de lettrage déjà relevés (table lettrages_pennylane, lot 18c), par pages de 1 000. {} si absente."""
    envoyer = envoyer or requete
    memo, offset = {}, 0
    while True:
        try:
            rep = envoyer("GET", base + f"/rest/v1/lettrages_pennylane?dossier=eq.{dossier}"
                          f"&select=ligne_id,maj,groupe,lu_le&order=ligne_id&limit=1000&offset={offset}", cle) or []
        except PublicationRefusee as e:
            if "PGRST205" in str(e) or "(code 404)" in str(e) or "does not exist" in str(e):
                print("avertissement : migration 008 non appliquée (lettrage relu en entier)")
                return {}
            raise
        for r in rep:
            memo[r["ligne_id"]] = {"maj": r.get("maj") or "", "groupe": r.get("groupe") or "", "lu_le": r.get("lu_le")}
        if len(rep) < 1000:
            return memo
        offset += 1000


def ecrire_memo_lettrage(base, cle, dossier, a_ecrire, envoyer=None):
    """Mémorise les groupes de lettrage relevés (lu_le posé par la base), par paquets de 1 000."""
    envoyer = envoyer or requete
    lignes = [{"dossier": dossier, "ligne_id": i, "maj": v["maj"], "groupe": v["groupe"]} for i, v in a_ecrire.items()]
    for k in range(0, len(lignes), 1000):
        envoyer("POST", base + "/rest/v1/lettrages_pennylane?on_conflict=dossier,ligne_id", cle, lignes[k:k + 1000],
                "resolution=merge-duplicates,return=minimal")


# ------------------------------------------------- écritures conservées (lot 18d, lecture par modifications)

RELECTURE_COMPLETE = 7      # jours : relecture complète au moins une fois par semaine
RETENTION_JOURNAL = 27      # jours : Pennylane garde 4 semaines de modifications


def _absente(e):
    return "PGRST205" in str(e) or "(code 404)" in str(e) or "does not exist" in str(e)


def _tout_lire_table(base, cle, table, dossier, envoyer):
    out, offset = [], 0
    while True:
        rep = envoyer("GET", base + f"/rest/v1/{table}?dossier=eq.{dossier}&select=id,contenu&order=id"
                      f"&limit=1000&offset={offset}", cle) or []
        out.extend(rep)
        if len(rep) < 1000:
            return out
        offset += 1000


def lire_magasin(base, cle, dossier, envoyer=None):
    """Écritures conservées et état de la dernière lecture ; None si rien, False si la migration 009 manque."""
    envoyer = envoyer or requete
    try:
        etat = envoyer("GET", base + f"/rest/v1/pennylane_etat?dossier=eq.{dossier}&select=*", cle) or []
    except PublicationRefusee as e:
        if _absente(e):
            print("avertissement : migration 009 non appliquée (lecture complète à chaque synchronisation)")
            return False
        raise
    if not etat:
        return None
    lignes = {r["id"]: r["contenu"] for r in _tout_lire_table(base, cle, "pennylane_lignes", dossier, envoyer)}
    entrees = {r["id"]: r["contenu"] for r in _tout_lire_table(base, cle, "pennylane_ecritures", dossier, envoyer)}
    e = etat[0]
    return {"lignes": lignes, "entrees": entrees, "bornes": [e.get("borne_debut"), e.get("borne_fin")],
            "taille_page": e.get("taille_page"), "derniere_lecture": e.get("derniere_lecture"),
            "derniere_complete": e.get("derniere_complete")}


def preparer_magasin(m, bas, haut, maintenant):
    """Lecture par modifications si les données conservées sont récentes et couvrent la période demandée."""
    from datetime import date, datetime, timedelta
    if not m:
        return None

    def instant(v):
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=maintenant.tzinfo)
        except (TypeError, ValueError):
            return None

    def jour(v):
        return date.fromisoformat(str(v)[:10]) if v else None
    lecture, complete = instant(m.get("derniere_lecture")), instant(m.get("derniere_complete"))
    sb, sh = (jour(x) for x in (m.get("bornes") or [None, None]))
    motif = None
    if not lecture or not complete:
        motif = "état de la dernière lecture illisible"
    elif maintenant - complete > timedelta(days=RELECTURE_COMPLETE):
        motif = f"relecture complète hebdomadaire (dernière il y a plus de {RELECTURE_COMPLETE} jours)"
    elif maintenant - lecture > timedelta(days=RETENTION_JOURNAL):
        motif = "dernière lecture trop ancienne pour le journal des modifications"
    elif not ((sb is None or (bas is not None and bas >= sb)) and (sh is None or (haut is not None and haut <= sh))):
        motif = "période demandée plus large que celle déjà lue"
    if motif:
        return {"taille_page": m.get("taille_page"), "motif": motif}
    return dict(m, increment_depuis=(lecture - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"))


def ecrire_magasin(base, cle, dossier, maj, debut_lecture, envoyer=None):
    """Conserve les écritures lues (complet : tout remplacer ; modifications : seulement les changements).

    L'état est effacé avant une réécriture complète et écrit en dernier : une interruption provoque une
    relecture complète à la synchronisation suivante, jamais des données incomplètes.
    """
    envoyer = envoyer or requete
    r = base + "/rest/v1/"

    def paquets(table, elements):
        lignes = [{"dossier": dossier, "id": i, "contenu": c} for i, c in elements.items()]
        for k in range(0, len(lignes), 1000):
            envoyer("POST", r + f"{table}?on_conflict=dossier,id", cle, lignes[k:k + 1000],
                    "resolution=merge-duplicates,return=minimal")

    def effacer(table, ids):
        ids = list(ids)
        for k in range(0, len(ids), 200):
            envoyer("DELETE", r + f"{table}?dossier=eq.{dossier}&id=in.({','.join(str(i) for i in ids[k:k + 200])})", cle)
    etat = {"dossier": dossier, "derniere_lecture": debut_lecture,
            "borne_debut": (maj.get("bornes") or [None, None])[0], "borne_fin": (maj.get("bornes") or [None, None])[1],
            "taille_page": maj.get("taille_page")}
    if maj["mode"] == "complet":
        envoyer("DELETE", r + f"pennylane_etat?dossier=eq.{dossier}", cle)
        envoyer("DELETE", r + f"pennylane_lignes?dossier=eq.{dossier}", cle)
        envoyer("DELETE", r + f"pennylane_ecritures?dossier=eq.{dossier}", cle)
        paquets("pennylane_lignes", maj["lignes"])
        paquets("pennylane_ecritures", maj["entrees"])
        etat["derniere_complete"] = debut_lecture
        envoyer("POST", r + "pennylane_etat?on_conflict=dossier", cle, [etat], "resolution=merge-duplicates,return=minimal")
    else:
        paquets("pennylane_lignes", maj["lignes"])
        paquets("pennylane_ecritures", maj["entrees"])
        effacer("pennylane_lignes", maj.get("lignes_suppr") or [])
        effacer("pennylane_ecritures", maj.get("entrees_suppr") or [])
        envoyer("PATCH", r + f"pennylane_etat?dossier=eq.{dossier}", cle,
                {"derniere_lecture": debut_lecture, "taille_page": maj.get("taille_page")}, "return=minimal")


def lire_pennylane(demo=generer_site.DEMO, jeton=None, mode="valides", client=None, periode=None, memo=None,
                   magasin=None):
    """Lit le dossier de test par le connecteur (lot 18). Renvoie (lignes, exercice, rapport).

    periode : (premier jour, dernier jour) choisis dans la page (lot 18b), ou None.
    """
    from datetime import datetime, timezone
    import source_pennylane
    from zenitude.connecteurs import pennylane as pl
    if not os.path.exists(os.path.join(demo, "configuration.xlsx")):
        import generer_demo
        generer_demo.main(demo)
    client = client or pl.Client(jeton)
    depuis = source_pennylane.debut_frise(demo)
    if magasin is not None:
        bas = max([x for x in (depuis, periode[0] if periode else None) if x], default=None)
        magasin = preparer_magasin(magasin, bas, periode[1] if periode else None, datetime.now(timezone.utc))
    lignes, exercice, rapport = pl.extraire(client, source_pennylane.DOSSIER_TEST, mode, depuis=depuis,
                                            periode=periode, lettrage_memo=memo, magasin=magasin)
    rapport["synchronise_le"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return lignes, exercice, rapport


# ---------------------------------------------------------- paramètres et demandes (lot 18b, décision 0012)

def periode_de(param):
    """(premier jour, dernier jour) d'après mois_debut / mois_fin d'une ligne de parametres_import, ou None."""
    import calendar
    from datetime import date
    if not param:
        return None
    md, mf = param.get("mois_debut"), param.get("mois_fin")
    if not md and not mf:
        return None
    d = date(int(md[:4]), int(md[5:7]), 1) if md else date(1900, 1, 1)
    f = date(int(mf[:4]), int(mf[5:7]), calendar.monthrange(int(mf[:4]), int(mf[5:7]))[1]) if mf else date(9999, 12, 31)
    return d, f


def lire_facultatif(base, cle, chemin, envoyer=None):
    """Lecture d'une table du lot 18b ; None si la migration 007 n'est pas encore appliquée."""
    envoyer = envoyer or requete
    try:
        return envoyer("GET", base + "/rest/v1/" + chemin, cle) or []
    except PublicationRefusee as e:
        if "PGRST205" in str(e) or "(code 404)" in str(e) or "does not exist" in str(e):
            print("avertissement : migration 007 non appliquée (paramètres d'import et synchronisations ignorés)")
            return None
        raise


def maj_demande(base, cle, ident, valeurs, envoyer=None):
    envoyer = envoyer or requete
    envoyer("PATCH", base + f"/rest/v1/synchronisations?id=eq.{int(ident)}", cle, valeurs, "return=minimal")


def _maintenant():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _execution():
    s, r, i = (os.environ.get(k, "") for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{s}/{r}/actions/runs/{i}" if s and r and i else None


def _resultat_demande(demande, par, pennylane):
    """Résultat par dossier demandé, sans montant (sauf le brouillard, destiné à la page)."""
    import source_pennylane
    out = {}
    for d in demande.get("dossiers") or []:
        if d == source_pennylane.DOSSIER_TEST and pennylane is not None and d in par:
            r = pennylane[2]
            out[d] = {"statut": "synchronisée", "lignes_reprises": r["lignes_reprises"], "lignes_lues": r["lignes_lues"],
                      "brouillard": r.get("brouillard"), "periode": r.get("periode"), "mode": r["mode"]}
        elif d == source_pennylane.DOSSIER_TEST:
            out[d] = {"statut": "échec", "motif": "lecture Pennylane impossible"}
        else:
            out[d] = {"statut": "non connectée", "motif": "aucun jeton Pennylane pour ce dossier"}
    return out


def main(argv):
    if "--essai" in argv:
        commun, par = calculer()
        dossier = argv[argv.index("--essai") + 1]
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
    ident = argv[argv.index("--demande") + 1].strip() if "--demande" in argv and argv.index("--demande") + 1 < len(argv) else ""
    ident = ident if ident.isdigit() else ""
    demande = None
    try:
        if ident:
            rep = requete("GET", base + f"/rest/v1/synchronisations?id=eq.{ident}&select=*", cle) or []
            if not rep:
                print(f"ERREUR : demande de synchronisation {ident} introuvable.", file=sys.stderr)
                return 1
            demande = rep[0]
            maj_demande(base, cle, ident, {"statut": "en cours", "debut": _maintenant(), "execution": _execution()})
            print(f"Demande {ident} : {demande.get('perimetre') or ''} ({len(demande.get('dossiers') or [])} résidence(s))")
        code = _publier_tout(argv, base, cle, demande)
    except Exception as e:  # la demande ne doit jamais rester « en cours »
        if demande is not None:
            try:
                maj_demande(base, cle, ident, {"statut": "échec", "fin": _maintenant(), "message": str(e)[:300]})
            except Exception:
                pass
        raise
    return code


def _publier_tout(argv, base, cle, demande):
    import source_pennylane
    from zenitude.connecteurs import pennylane as pl
    params = lire_facultatif(base, cle, "parametres_import?select=*") or []
    param = next((p for p in params if p.get("dossier") == source_pennylane.DOSSIER_TEST), None)
    jeton = os.environ.get("PENNYLANE_TOKEN_PILOTE", "").strip()
    obligatoire = "--pennylane" in argv or demande is not None
    pennylane, erreur, debut_lecture = None, None, None
    if jeton:
        if demande is not None:
            mode = "valides" if demande.get("masquer_brouillard", True) else "tous"
        elif os.environ.get("PENNYLANE_MODE", "").strip() in pl.MODES:
            mode = os.environ["PENNYLANE_MODE"].strip()  # choix au lancement manuel du workflow
        else:
            mode = "valides" if (param or {}).get("masquer_brouillard", True) else "tous"
        periode = periode_de(demande) if demande is not None else periode_de(param)
        try:
            import time
            t0 = time.monotonic()
            from datetime import datetime, timezone
            debut_lecture = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            memo = lire_memo_lettrage(base, cle, source_pennylane.DOSSIER_TEST)
            magasin = lire_magasin(base, cle, source_pennylane.DOSSIER_TEST)
            t1 = time.monotonic()
            if magasin:
                print(f"Écritures conservées relues dans la base : {len(magasin['lignes'])} ligne(s) en {t1 - t0:.0f} s")
            pennylane = lire_pennylane(jeton=jeton, mode=mode, periode=periode, memo=memo,
                                       magasin=None if magasin is False else (magasin or {}))
            if magasin is False:
                pennylane[2].pop("_magasin_maj", None)
            print(pl.texte_rapport(pennylane[2]))
            print(f"Durée de lecture Pennylane : {time.monotonic() - t1:.0f} s")
        except pl.ErreurPennylane as e:
            erreur = str(e)
            if obligatoire:
                print("ERREUR Pennylane : " + erreur, file=sys.stderr)
            else:
                print("avertissement : dossier Pennylane de test non lu (" + erreur + ") ; publication sans lui")
    elif obligatoire:
        erreur = "secret PENNYLANE_TOKEN_PILOTE absent"
        print("ERREUR : " + erreur + ".", file=sys.stderr)
    if obligatoire and pennylane is None and (demande is None or source_pennylane.DOSSIER_TEST in (demande.get("dossiers") or [])):
        if demande is not None:
            maj_demande(base, cle, demande["id"], {"statut": "échec", "fin": _maintenant(), "message": erreur})
        return 1

    commun, par = calculer() if pennylane is None else calculer(pennylane=pennylane)
    if pennylane is not None:
        src = par.get(source_pennylane.DOSSIER_TEST, {}).get("source")
        if src is not None:
            r = pennylane[2]
            src.update({"periode": r.get("periode"), "brouillard": r.get("brouillard")})
            if src.get("comptes_provisoires"):
                print("Comptes classés provisoirement (préfixes) : " + ", ".join(src["comptes_provisoires"]))
    try:
        residences = requete("GET", base + "/rest/v1/residences?select=id,dossier_pennylane,fictif", cle) or []
        commune, lignes, avert = lignes_a_publier(commun, par, residences)
        publier(base, cle, commune, lignes, envoyer=requete)
    except PublicationRefusee as e:
        print("ERREUR : " + str(e), file=sys.stderr)
        if demande is not None:
            maj_demande(base, cle, demande["id"], {"statut": "échec", "fin": _maintenant(), "message": str(e)[:300]})
        return 1
    for a in avert:
        print("avertissement : " + a)
    print(f"publié : données communes et {len(lignes)} résidence(s) : "
          + ", ".join(l["residence_id"] for l in lignes))
    if pennylane is not None and pennylane[2].get("_magasin_maj"):
        try:
            import time
            t2 = time.monotonic()
            ecrire_magasin(base, cle, source_pennylane.DOSSIER_TEST, pennylane[2]["_magasin_maj"], debut_lecture)
            print(f"Écritures conservées pour la prochaine synchronisation ({time.monotonic() - t2:.0f} s)")
        except PublicationRefusee as e:
            print("avertissement : écritures non conservées (" + str(e)[:200] + ") ; relecture complète la prochaine fois")
    if pennylane is not None and pennylane[2].get("_lettrage_a_memoriser"):
        try:
            ecrire_memo_lettrage(base, cle, source_pennylane.DOSSIER_TEST, pennylane[2]["_lettrage_a_memoriser"])
        except PublicationRefusee as e:
            print("avertissement : lettrage non mémorisé (" + str(e)[:200] + ")")
    if demande is not None:
        maj_demande(base, cle, demande["id"], {"statut": "terminée", "fin": _maintenant(),
                                               "resultat": _resultat_demande(demande, par, pennylane)})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
