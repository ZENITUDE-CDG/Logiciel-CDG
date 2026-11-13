"""Génère la maquette HTML du logiciel avec des données fictives issues du moteur réel.

Aucune fonction réelle : la page affiche des résultats calculés par le lot 1 à 5 et des écrans
non réalisés, marqués comme tels. Usage : python maquette/generer_maquette.py <sortie.html>
"""
import html
import os
import sys
import tempfile
from datetime import date

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from zenitude.config import controles, impact, publication  # noqa: E402
from zenitude.config.versions import Depot  # noqa: E402

FIX = os.path.join(RACINE, "tests", "fixtures")
ECR = os.path.join(FIX, "ecritures_synthetiques.csv")
EXE = os.path.join(FIX, "exercices.csv")
MODELE = os.path.join(RACINE, "config_modele", "Zenitude_Configuration_modele.xlsx")
V1 = os.path.join(FIX, "config_complete_v1.xlsx")
V2 = os.path.join(FIX, "config_complete_v2.xlsx")
E = html.escape


def euro(v):
    return f"{float(v):,.2f} €".replace(",", " ").replace(".", ",")


def construire_donnees():
    store = os.path.join(tempfile.mkdtemp(), "store")
    d = Depot(store)
    vid1 = d.deposer(V1, "alice")
    d.approuver(vid1, "bob")
    d.appliquer(vid1, "bob")
    pubs = {}
    for dossier in ("PENNY-1001", "PENNY-1002", "PENNY-1003"):
        pid, inst = publication.publier(d, ECR, EXE, dossier, "carol")
        pubs[dossier] = inst
    vid2 = d.deposer(V2, "alice")
    apercu = impact.comparer(V1, V2)
    return {
        "pubs": pubs,
        "versions": d.statut()["versions"],
        "journal": d.statut()["journal"],
        "courante": d.statut()["courante"],
        "rapport_modele": controles.verifier(MODELE),
        "apercu": apercu,
        "v2": vid2,
        "ecritures": len(open(ECR, encoding="utf-8").read().splitlines()) - 1,
        "exercices": {l.split(";")[0]: l.split(";")[1:] for l in open(EXE, encoding="utf-8").read().splitlines()[1:]},
    }


def page(donnees):
    p = donnees["pubs"]
    nav = [
        ("accueil", "Accueil", "Vue personnelle"),
        ("pilotage", "Pilotage", "Vue groupe"),
        ("finance", "Finance", "Compte de résultat"),
        ("budgets", "Budgets", "Non réalisé"),
        ("rapports", "Rapports", "Non réalisé"),
        ("donnees", "Données", "Imports et connexions"),
    ]
    cfg = ("configuration", "Configuration", "Versions et contrôles")

    def bandeau():
        return f"""<div class="contexte">
<span><b>Périmètre</b> Groupe test (3 dossiers)</span>
<span><b>Exercice</b> voir chaque dossier</span>
<span><b>Scénario</b> Référence</span>
<span><b>Version de configuration</b> {E(donnees['courante'])}</span>
<span class="fictif">Données fictives</span></div>"""

    # Accueil
    attente = [v for v in donnees["versions"] if v["statut"] == "déposée"]
    accueil = f"""<h2>Accueil</h2>
<div class="cartes">
<div class="carte"><h3>Travaux à traiter</h3>
<ul><li>{len(attente)} version(s) de configuration en attente d'approbation ({', '.join(E(v['id']) for v in attente) or 'aucune'})</li>
</ul></div>
<div class="carte"><h3>Raccourcis</h3>
<ul><li><a href="#finance">Compte de résultat par dossier</a></li>
<li><a href="#configuration">Versions et contrôles</a></li></ul></div>
<div class="carte"><h3>Ce qui est réel</h3>
<p>Calcul du compte de résultat, contrôle des comptes non classés, dépôt et approbation des versions, retour arrière.</p>
<p class="muted">Tout le reste de cette maquette est à titre indicatif.</p></div></div>"""

    # Finance : compte de résultat
    lignes = ""
    for dossier, inst in p.items():
        r = inst["resultat"]
        ex = inst["exercice"]
        note = " (exercice court : non comparable directement à 12 mois)" if ex["duree_mois"] != 12 else ""
        lignes += f"""<tr><td>{E(dossier)}</td><td>{E(ex['debut'])} → {E(ex['fin'])}</td>
<td class="num">{ex['duree_mois']} mois{E(note)}</td>
<td class="num">{euro(r['CA_HEBERGEMENT'])}</td><td class="num">{euro(r['CA_SERVICES'])}</td>
<td class="num">{euro(r['PL_CHARGES'])}</td><td class="num"><b>{euro(r['RESULTAT'])}</b></td>
<td><span class="badge ok">publié</span></td></tr>"""
    finance = f"""<h2>Finance / Compte de résultat</h2>
<p>Un compte de résultat par dossier et exercice. Les charges sont par nature, sans marge par activité.</p>
<table><thead><tr><th>Dossier</th><th>Exercice</th><th>Durée</th><th>CA hébergement</th><th>CA services</th>
<th>Charges</th><th>Résultat</th><th>État</th></tr></thead><tbody>{lignes}</tbody></table>
<h3>Clôture de gestion</h3>
<p class="muted">Étalements, provisions et ajustements : non réalisés dans cette version.</p>"""

    # Pilotage
    total = sum(float(i["resultat"]["RESULTAT"]) for i in p.values())
    pilotage = f"""<h2>Pilotage / Vue groupe</h2>
<div class="cartes"><div class="carte"><h3>Résultat cumulé</h3><p class="gros">{euro(total)}</p>
<p class="muted">Somme des 3 dossiers, chacun sur son propre exercice. Pas de comparaison à périmètre constant.</p></div>
<div class="carte"><h3>Couverture</h3><p class="gros">3 / 3</p><p class="muted">dossiers publiés</p></div></div>
<p class="muted">Groupes, lots de pilotage et comparatifs : non réalisés.</p>"""

    # Budgets
    budgets = """<h2>Budgets</h2>
<p>Campagnes budgétaires, scénarios Référence, Optimiste et Défavorable, atterrissage.</p>
<div class="cartes">
<div class="carte"><h3>Référence</h3><p class="muted">Calculée par le contrôle de gestion</p></div>
<div class="carte"><h3>Optimiste</h3><p class="muted">Copie de la référence, hypothèses favorables</p></div>
<div class="carte"><h3>Défavorable</h3><p class="muted">Copie de la référence, hypothèses prudentes</p></div></div>
<p class="badge attente">Non réalisé</p>"""

    # Rapports
    rapports = """<h2>Rapports</h2>
<table><thead><tr><th>Modèle</th><th>Format</th><th>État</th></tr></thead><tbody>
<tr><td>Compte de résultat résidence</td><td>PDF</td><td><span class="badge attente">à venir</span></td></tr>
<tr><td>Budget</td><td>PowerPoint</td><td><span class="badge attente">à venir</span></td></tr>
<tr><td>Synthèse régionale</td><td>PDF</td><td><span class="badge attente">à venir</span></td></tr>
<tr><td>Envoi programmé par mail</td><td>-</td><td><span class="badge attente">non prévu en phase test</span></td></tr>
</tbody></table>"""

    # Données
    donnees_html = f"""<h2>Données</h2>
<div class="cartes">
<div class="carte"><h3>Écritures importées</h3><p class="gros">{donnees['ecritures']}</p><p class="muted">Données fictives, plan comptable général</p></div>
<div class="carte"><h3>Connexion Pennylane</h3><p class="badge attente">non connectée</p><p class="muted">Phase test : aucune connexion réelle</p></div>
<div class="carte"><h3>Exercices</h3><p class="muted">Un exercice décalé (avril à mars), un exercice de neuf mois.</p></div></div>"""

    # Configuration
    lignes_v = ""
    for v in donnees["versions"]:
        approb = ", ".join(E(a) for a in v["approbations"]) or "-"
        etat = {"appliquée": "ok", "déposée": "attente"}.get(v["statut"], "")
        lignes_v += f"""<tr><td>{E(v['id'])}</td><td><span class="badge {etat}">{E(v['statut'])}</span></td>
<td>{E(v['auteur_depot'])}</td><td>{approb}</td><td>{E(v['date_depot'])}</td></tr>"""
    rm = donnees["rapport_modele"]
    lignes_rm = "".join(f"<tr><td>{E(c.code)}</td><td>{E(c.onglet)}</td><td>{c.ligne or '-'}</td><td>{E(c.message)}</td></tr>"
                        for c in rm.constats) or "<tr><td colspan=4>Aucun constat</td></tr>"
    ap = donnees["apercu"]
    lignes_ap = "".join(f"<li>{E(c['onglet'])} : {E(c['type'])} ({E(', '.join(str(v) for v in c['cle'].values() if v))})"
                        f"{' - archivage' if c['archivage'] else ''}</li>" for c in ap["changements"]) or "<li>Aucun changement</li>"
    configuration = f"""<h2>Configuration / Versions et contrôles</h2>
<h3>Versions</h3>
<table><thead><tr><th>Version</th><th>État</th><th>Déposée par</th><th>Approuvée par</th><th>Date</th></tr></thead>
<tbody>{lignes_v}</tbody></table>
<p class="muted">Une version ne peut être appliquée qu'après approbation par une autre personne que son auteur. Un retour arrière ne modifie aucune donnée.</p>
<h3>Aperçu des impacts : {E(donnees['courante'])} vers {E(donnees['v2'])}</h3>
<p>Nouvelle version : <span class="badge {'ok' if ap['nouvelle_version_valide'] else 'erreur'}">{'valide' if ap['nouvelle_version_valide'] else 'refusée'}</span></p>
<ul>{lignes_ap}</ul>
<h3>Rapport de chargement : modèle de configuration</h3>
<p>Verdict : <span class="badge {'erreur' if rm.erreurs else 'ok'}">{'refusé' if rm.erreurs else 'valide'}</span>
 <span class="muted">Empreinte {E(rm.empreinte[:16])}…</span></p>
<table><thead><tr><th>Code</th><th>Onglet</th><th>Ligne</th><th>Motif</th></tr></thead><tbody>{lignes_rm}</tbody></table>
<h3>Journal</h3>
<ul>{''.join(f"<li>{E(j['date'])} : {E(j['action'])} par {E(j['auteur'])} ({E(j['detail'])})</li>" for j in donnees['journal'])}</ul>"""

    sections = {"accueil": accueil, "pilotage": pilotage, "finance": finance, "budgets": budgets,
                "rapports": rapports, "donnees": donnees_html, "configuration": configuration}
    menu = "".join(f'<a href="#{k}" data-s="{k}"><b>{E(t)}</b><small>{E(s)}</small></a>' for k, t, s in nav)
    menu_bas = f'<a href="#{cfg[0]}" data-s="{cfg[0]}"><b>{E(cfg[1])}</b><small>{E(cfg[2])}</small></a>'
    corps = "".join(f'<section id="s-{k}" class="vue">{v}</section>' for k, v in sections.items())
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zenitude - Pilotage (maquette)</title>
<style>
:root {{ --acc:#1F3A5F; --fond:#F5F6F8; --txt:#1d2530; --mut:#5c6675; --bord:#d9dde3; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family: Arial, Helvetica, sans-serif; color:var(--txt); background:var(--fond); }}
.haut {{ background:#fff3c4; border-bottom:1px solid #e0c96a; padding:8px 16px; font-size:14px; }}
.app {{ display:flex; min-height:calc(100vh - 36px); }}
aside {{ width:230px; background:#fff; border-right:1px solid var(--bord); display:flex; flex-direction:column; }}
aside .logo {{ padding:18px 16px; font-weight:bold; color:var(--acc); border-bottom:1px solid var(--bord); }}
aside nav {{ flex:1; }}
aside a {{ display:block; padding:10px 16px; color:var(--txt); text-decoration:none; border-left:3px solid transparent; }}
aside a small {{ display:block; color:var(--mut); font-size:12px; }}
aside a.actif {{ background:#e9eef6; border-left-color:var(--acc); }}
aside .bas {{ border-top:1px solid var(--bord); }}
main {{ flex:1; padding:0; }}
.contexte {{ background:#fff; border-bottom:1px solid var(--bord); padding:10px 24px; display:flex; flex-wrap:wrap; gap:18px; font-size:13px; }}
.fictif {{ color:#7a4b00; font-weight:bold; }}
.contenu {{ padding:20px 24px; }}
h2 {{ color:var(--acc); margin-top:4px; }}
h3 {{ font-size:16px; margin:18px 0 8px; }}
table {{ width:100%; border-collapse:collapse; background:#fff; font-size:14px; }}
th,td {{ border:1px solid var(--bord); padding:7px 9px; text-align:left; vertical-align:top; }}
th {{ background:#eef1f5; }}
td.num {{ text-align:right; white-space:nowrap; }}
.cartes {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin:12px 0; }}
.carte {{ background:#fff; border:1px solid var(--bord); border-radius:6px; padding:14px; }}
.carte h3 {{ margin-top:0; }}
.gros {{ font-size:22px; font-weight:bold; margin:6px 0; }}
.muted {{ color:var(--mut); font-size:13px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid #888; }}
.badge.ok {{ border-color:#2e7d32; color:#1b5e20; }}
.badge.attente {{ border-color:#8a6d00; color:#6b5200; }}
.badge.erreur {{ border-color:#b00020; color:#8a0019; }}
.vue {{ display:none; }}
.vue.actif {{ display:block; }}
a {{ color:var(--acc); }}
</style></head><body>
<div class="haut"><b>MAQUETTE</b> : aucune fonction réelle hors calculs et contrôles décrits. Données fictives. Mise en page à valider.</div>
<div class="app">
<aside><div class="logo">Zenitude · Pilotage</div><nav>{menu}</nav><div class="bas">{menu_bas}</div></aside>
<main>{bandeau()}<div class="contenu">{corps}</div></main>
</div>
<script>
function afficher() {{
  var k = (location.hash || '#accueil').slice(1);
  if (!document.getElementById('s-' + k)) k = 'accueil';
  document.querySelectorAll('.vue').forEach(function(s) {{ s.classList.toggle('actif', s.id === 's-' + k); }});
  document.querySelectorAll('aside a').forEach(function(a) {{ a.classList.toggle('actif', a.dataset.s === k); }});
}}
window.addEventListener('hashchange', afficher); afficher();
</script></body></html>"""


def main(sortie):
    donnees = construire_donnees()
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(page(donnees))
    print("maquette écrite :", sortie)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "maquette", "index.html"))
