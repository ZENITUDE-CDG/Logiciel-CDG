"""Ligne de commande du moteur de KPI (lot 6).

  python -m zenitude.kpi calcul <store> <dossier> <ecritures.csv> <exercices.csv> <mesures.csv> [--du AAAA-MM --au AAAA-MM] [--json]
  python -m zenitude.kpi groupe <store> <ecritures.csv> <mesures.csv> --du AAAA-MM --au AAAA-MM (--dossiers A,B | --activite Seniors) [--json]
"""
import json
import sys

from . import calculer_dossier, calculer_groupe, RefusCalcul
from zenitude.config.versions import Depot


def _option(args, nom):
    if nom in args:
        i = args.index(nom)
        return args[i + 1] if i + 1 < len(args) else None
    return None


def _texte(res):
    lignes = [f"Périmètre : {res['perimetre']}",
              f"Période   : {res['periode']['libelle']} ({res['periode']['nb_mois']} mois)",
              f"Config.   : {res['version_config']}  -  données {res['donnees']}", ""]
    largeur = max(len(k["nom"]) for k in res["kpi"]) if res["kpi"] else 10
    for k in res["kpi"]:
        ligne = f"{k['code']:<14} {k['nom']:<{largeur}}  {k['affichage']:>14}"
        if k["motif"]:
            ligne += f"   ({k['motif']})"
        lignes.append(ligne)
    return "\n".join(lignes)


def main(argv):
    if len(argv) < 2 or argv[0] not in ("calcul", "groupe"):
        print(__doc__, file=sys.stderr)
        return 2
    action, args = argv[0], argv[1:]
    try:
        depot = Depot(args[0])
        du, au = _option(args, "--du"), _option(args, "--au")
        if action == "calcul":
            res = calculer_dossier(depot, args[1], args[2], args[3], args[4], du, au)
        else:
            dossiers = _option(args, "--dossiers")
            res = calculer_groupe(depot, args[1], args[2], du, au,
                                  dossiers=dossiers.split(",") if dossiers else None,
                                  activite=_option(args, "--activite"))
    except (RefusCalcul, IndexError, ValueError) as e:
        print(f"REFUS : {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2) if "--json" in args else _texte(res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
