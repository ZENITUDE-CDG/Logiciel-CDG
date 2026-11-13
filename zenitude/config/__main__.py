"""Interface en ligne de commande : python -m zenitude.config check <fichier.xlsx>"""
import sys

from . import verifier
from . import impact, rapport as rapport_export


USAGE = """usage :
  python -m zenitude.config check <fichier.xlsx> [--json | --md]
  python -m zenitude.config impact <ancien.xlsx> <nouveau.xlsx> [--json]"""


def main_versions(argv):
    from .versions import Depot, RefusAction, RefusDepot
    import json
    if len(argv) < 2:
        print("usage : versions <dossier> statut|deposer <f> <auteur>|approuver <vid> <par>|appliquer <vid> <auteur>|revenir <vid> <auteur>|publier <dossier> <ecritures.csv> <exercices.csv> <auteur>", file=sys.stderr)
        return 2
    depot = Depot(argv[1])
    action, args = argv[2], argv[3:]
    try:
        if action == "statut":
            print(json.dumps(depot.statut(), ensure_ascii=False, indent=2))
        elif action == "deposer":
            print(depot.deposer(args[0], args[1]))
        elif action == "approuver":
            depot.approuver(args[0], args[1])
        elif action == "appliquer":
            depot.appliquer(args[0], args[1])
        elif action == "revenir":
            depot.revenir(args[0], args[1])
        elif action == "publier":
            from . import publication
            pid, _ = publication.publier(depot, args[1], args[2], args[0], args[3])
            print(pid)
        else:
            print("action inconnue", file=sys.stderr)
            return 2
    except (RefusDepot, RefusAction) as e:
        print(f"REFUS : {e}", file=sys.stderr)
        return 1
    except publication.PublicationBloquee as e:
        print(f"REFUS : {e}", file=sys.stderr)
        return 1
    return 0


def main(argv):
    if argv and argv[0] == "versions":
        return main_versions(argv)
    if argv and argv[0] == "impact" and len(argv) in (3, 4):
        res = impact.comparer(argv[1], argv[2])
        if "--json" in argv:
            import json
            print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
        else:
            print(impact.vers_markdown(res))
        return 0 if res["nouvelle_version_valide"] else 1
    if not argv or argv[0] != "check" or len(argv) not in (2, 3):
        print(USAGE, file=sys.stderr)
        return 2
    rapport = verifier(argv[1])
    if "--json" in argv:
        print(rapport_export.vers_json(rapport))
        return 1 if rapport.erreurs else 0
    if "--md" in argv:
        print(rapport_export.vers_markdown(rapport))
        return 1 if rapport.erreurs else 0
    print(f"Fichier : {rapport.chemin}")
    print(f"Empreinte SHA-256 : {rapport.empreinte}")
    print("Lignes lues par onglet : " + ", ".join(f"{k}={v}" for k, v in rapport.lignes_lues.items()))
    for c in rapport.constats:
        print(c)
    print(f"Résultat : {'REFUSÉ' if rapport.erreurs else 'VALIDE'} "
          f"({len(rapport.erreurs)} erreur(s), {len(rapport.avertissements)} avertissement(s))")
    return 1 if rapport.erreurs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
