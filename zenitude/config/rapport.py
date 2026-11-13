"""Rapport de chargement exportable (JSON et Markdown) - lot 2."""
import json


def vers_dict(rapport):
    return {
        "fichier": rapport.chemin,
        "empreinte_sha256": rapport.empreinte,
        "verdict": "refusé" if rapport.erreurs else "valide",
        "lignes_lues": rapport.lignes_lues,
        "erreurs": [c.__dict__ for c in rapport.erreurs],
        "avertissements": [c.__dict__ for c in rapport.avertissements],
    }


def vers_json(rapport):
    return json.dumps(vers_dict(rapport), ensure_ascii=False, indent=2)


def vers_markdown(rapport):
    d = vers_dict(rapport)
    lignes = [
        f"# Rapport de chargement",
        "",
        f"- Fichier : `{d['fichier']}`",
        f"- Empreinte SHA-256 : `{d['empreinte_sha256']}`",
        f"- Verdict : **{d['verdict']}** "
        f"({len(d['erreurs'])} erreur(s), {len(d['avertissements'])} avertissement(s))",
        "",
        "## Lignes lues par onglet",
        "",
        "| Onglet | Lignes |",
        "| --- | --- |",
    ]
    lignes += [f"| {k} | {v} |" for k, v in d["lignes_lues"].items()]
    for titre, liste in (("Erreurs", d["erreurs"]), ("Avertissements", d["avertissements"])):
        lignes += ["", f"## {titre}", ""]
        if not liste:
            lignes.append("Aucun.")
        else:
            lignes += ["| Code | Onglet | Ligne | Motif |", "| --- | --- | --- | --- |"]
            for c in liste:
                lignes.append(f"| {c['code']} | {c['onglet']} | {c['ligne'] or '-'} | {c['message']} |")
    return "\n".join(lignes) + "\n"
