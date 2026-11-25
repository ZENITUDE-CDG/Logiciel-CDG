"""Lot 20 dans un vrai navigateur (données fictives, base simulée) : suivi KPI paramétrable.

1. Paramètres KPI : contrôles, modèles proposés d'après l'activité, création d'un indicateur, formule incohérente
   refusée, donnée utilisée non désactivable, ordre.
2. Indicateurs suivis : ratio de sommes, couverture partielle signalée, seuil, indicateur non suivi masqué, détail.
3. Modèle Excel : export (une feuille par modèle, codes, valeurs déjà importées), fichier lisible par Excel
   (relu par openpyxl), redépôt identique, valeur modifiée, donnée inconnue ou désactivée, résidence d'un autre
   modèle, catalogue modifié depuis l'export, import enregistré.
Ignorés si Playwright n'est pas installé.
"""
import base64
import copy
import io
import pathlib
import sys

import pytest

playwright = pytest.importorskip("playwright.sync_api")

RACINE = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tests"))
sys.path.insert(0, str(RACINE / "interface"))
import catalogue_kpi as ck  # noqa: E402
from test_lot18b_page import demarrer, site  # noqa: E402,F401

MESURES = [  # Les Terrasses du Port (DEMO-2001, Hôtellerie) et Le Belvédère (DEMO-2002, Hôtellerie), fictif
    {"dossier": "DEMO-2001", "mois": "2026-10", "mesure": "LN_VENDUES_HOT", "valeur": 1000},
    {"dossier": "DEMO-2001", "mois": "2026-10", "mesure": "LN_DISPO_HOT", "valeur": 1550},
    {"dossier": "DEMO-2002", "mois": "2026-10", "mesure": "LN_VENDUES_HOT", "valeur": 500},
    {"dossier": "DEMO-2002", "mois": "2026-10", "mesure": "LN_DISPO_HOT", "valeur": 1450},
    {"dossier": "DEMO-2001", "mois": "2026-09", "mesure": "LN_VENDUES_HOT", "valeur": 900},
    {"dossier": "DEMO-2001", "mois": "2026-09", "mesure": "LN_DISPO_HOT", "valeur": 1500},
    {"dossier": "DEMO-2002", "mois": "2026-09", "mesure": "LN_VENDUES_HOT", "valeur": 700},  # capacité absente
]


def tables(modeles=True, **autres):
    t = {"kpi_catalogue": copy.deepcopy(ck.CATALOGUE), "kpi_modeles": copy.deepcopy(ck.MODELES), "kpi_journal": [],
         "residence_modele": [{"dossier": "DEMO-2001", "modele": "TOURISME"}, {"dossier": "DEMO-2002", "modele": "TOURISME"},
                              {"dossier": "DEMO-2003", "modele": "SENIORS"}] if modeles else [],
         "mesures_importees": copy.deepcopy(MESURES), "kpi_mois": [], "depots_kpi": [],
         "residences": [{"id": "RES-00" + str(i), "dossier_pennylane": f"DEMO-200{i}", "code_mews": None} for i in range(1, 9)]}
    t.update(autres)
    return t


def page(pg, section, nom, perim):
    pg.evaluate(f"choisir('{perim}'); allerA('{section}', '{nom}')")
    pg.wait_for_selector("#contenu .titre-page")


def groupe(pg, *ds):
    """Périmètre de test : quelques résidences de démonstration."""
    pg.evaluate("(ds) => { D.perimetres.push({ id: 'GR-TEST', libelle: 'Groupe de test', type: 'groupe-cree', dossiers: ds }); }", list(ds))
    return "GR-TEST"


def test_modeles_proposes_et_controles(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables(modeles=False))
    page(pg, "import", "parametres", "GROUPE")
    texte = pg.inner_text("#contenu")
    assert "Contrôles du catalogue" in texte and "sans modèle de suivi" in texte
    assert "Configuration du moteur de calcul" in texte  # l'ancienne page reste en bas
    pg.click("#cat-proposer")
    pg.wait_for_function("tablesTest.residence_modele.length >= 8")
    attendu = {"DEMO-2001": "TOURISME", "DEMO-2002": "TOURISME", "DEMO-2003": "SENIORS", "DEMO-2004": "SENIORS"}
    obtenu = {x["dossier"]: x["modele"] for x in pg.evaluate("tablesTest.residence_modele")}
    assert {k: obtenu[k] for k in attendu} == attendu
    assert pg.query_selector("#cat-proposer") is None
    # Un modèle se change à la main
    pg.select_option("[data-res-modele='DEMO-2001']", "ETUDIANTS")
    pg.wait_for_function("tablesTest.residence_modele.find(x => x.dossier === 'DEMO-2001').modele === 'ETUDIANTS'")
    assert erreurs == []
    pg.close()


def test_creer_un_indicateur_et_refus(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    page(pg, "import", "parametres", "GROUPE")
    pg.click("#cat-nouv-ind")
    pg.fill("#cat-code", "to_essai")
    pg.fill("#cat-libelle", "TO essai (fictif)")
    pg.check("input[name='cat-modele'][value='TOURISME']")
    pg.check("input[name='cat-num'][value='NUITEES_SEN']")  # donnée suivie par Seniors seulement
    pg.check("input[name='cat-den'][value='LN_DISPO_HOT']")
    pg.click("#cat-ok")
    assert "non suivie par Tourisme" in pg.inner_text("#cat-erreur")
    pg.uncheck("input[name='cat-num'][value='NUITEES_SEN']")
    pg.check("input[name='cat-num'][value='LN_VENDUES_HOT']")
    pg.fill("#cat-seuil", "60")
    pg.click("#cat-ok")
    pg.wait_for_selector("#cat-form", state="detached")
    x = pg.evaluate("tablesTest.kpi_catalogue.find(x => x.code === 'TO_ESSAI')")
    assert x["numerateur"] == ["LN_VENDUES_HOT"] and x["denominateur"] == ["LN_DISPO_HOT"] and x["seuil"] == 0.6 and x["type"] == "indicateur"
    assert "TO essai (fictif)" in pg.inner_text("#cat-indicateur")
    # Désactiver une donnée utilisée : refusé
    pg.click("[data-cat-modif='LN_DISPO_HOT']")
    pg.uncheck("#cat-actif")
    pg.click("#cat-ok")
    assert "donnée utilisée par" in pg.inner_text("#cat-erreur")
    pg.click("#cat-annuler")
    # Ordre : le premier indicateur descend
    avant = pg.evaluate("CAT.filter(x => x.type === 'indicateur' && x.rubrique === 'Hébergement').map(x => x.code)")
    pg.click(f"[data-cat-bas='{avant[0]}']")
    pg.wait_for_function(f"CAT.filter(x => x.type === 'indicateur' && x.rubrique === 'Hébergement')[1].code === '{avant[0]}'")
    assert erreurs == []
    pg.close()


def test_indicateurs_suivis(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    pg.evaluate("tablesTest.kpi_catalogue.find(x => x.code === 'TO_HOT').seuil = 0.6")
    gid = groupe(pg, "DEMO-2001", "DEMO-2002")
    page(pg, "tableaux", "suivi", gid)
    pg.evaluate("catRecharger().then(() => { etat.lo = MOIS.indexOf('2026-09'); etat.hi = MOIS.indexOf('2026-10') + 1; majContenu(); })")
    pg.wait_for_function("document.querySelector('#suivi-ind') && document.querySelectorAll('#suivi-ind thead th').length === 7")
    r = pg.evaluate("valeurIndicateur(elementCat('TO_HOT'), ['DEMO-2001', 'DEMO-2002'], ['2026-10'])")
    assert r["v"] == pytest.approx(1500 / 3000) and r["retenus"] == 2 and r["attendus"] == 2      # ratio de sommes
    r = pg.evaluate("valeurIndicateur(elementCat('TO_HOT'), ['DEMO-2001', 'DEMO-2002'], ['2026-09', '2026-10'])")
    assert r["v"] == pytest.approx(2400 / 4500) and r["retenus"] == 3 and r["attendus"] == 4      # sept. du Belvédère incomplet
    texte = pg.inner_text("#suivi-ind")
    assert "50,0 %" in texte and "53,3 %*" in texte.replace(" *", "*")
    assert "Taux d'occupation seniors" not in texte          # non suivi par des résidences Tourisme
    assert pg.evaluate("document.querySelector('#suivi-ind td.seuil-ko') !== null")      # 50 % < 60 %
    d = pg.evaluate("EXPLIQUER.ind({ c: 'TO_HOT', d: ['DEMO-2001', 'DEMO-2002'], m: ['2026-09', '2026-10'] })")
    assert d["valeur"] == "53,3 %" and any("3 résidence-mois sur 4" in n for n in d["notes"])
    assert "Chambres vendues hôtelières" in pg.inner_text("#suivi-don")
    assert erreurs == []
    pg.close()


def lignes_js():
    return """(M) => { const tout = {}; M.feuilles.forEach(f => { tout[f.nom] = f.lignes.map(l => (l || []).map(c => c !== null && typeof c === 'object' ? c.v : c)); });
      const L = tout['Lisez-moi']; L.classeur = tout; return L; }"""


def test_modele_excel_aller_retour(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    gid = groupe(pg, "DEMO-2001", "DEMO-2002", "DEMO-2003")
    page(pg, "import", "externes", gid)
    M = pg.evaluate(f"(() => {{ const M = construireModeleExcel(perimetre('{gid}'), '2026-09', '2026-10'); return {{ noms: M.feuilles.map(f => f.nom), residences: M.residences, lignes: M.lignes }}; }})()")
    assert M == {"noms": ["Lisez-moi", "Tourisme (RT)", "Seniors"], "residences": 3, "lignes": 6}
    pg.evaluate(f"window.M = construireModeleExcel(perimetre('{gid}'), '2026-09', '2026-10'); true")
    tour = pg.evaluate("M.feuilles[1].lignes")
    codes = [c["v"] for c in tour[1][3:]]
    assert codes == [x["code"] for x in ck.CATALOGUE if x["type"] == "donnee" and "TOURISME" in x["modeles"]]
    assert "NUITEES_SEN" not in codes
    i = 3 + codes.index("LN_DISPO_HOT")
    oct_2001 = next(l for l in tour if l[0] == "DEMO-2001" and l[2] == "2026-10")
    assert oct_2001[i]["v"] == 1550                         # valeur déjà importée, reprise dans le modèle
    # Le fichier écrit s'ouvre dans Excel (relu par openpyxl)
    b64 = pg.evaluate("ecrireXlsx(M.feuilles).then(b => b.arrayBuffer()).then(a => { let s = ''; new Uint8Array(a).forEach(x => s += String.fromCharCode(x)); return btoa(s); })")
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(b64)))
    assert wb.sheetnames == ["Lisez-moi", "Tourisme (RT)", "Seniors"] and wb["Tourisme (RT)"]["A2"].value == "#codes"
    # Redépôt sans changement : rien de nouveau
    pg.evaluate(f"window.fab = {lignes_js()}; true")
    R = pg.evaluate("validerModeleKpi(fab(M), perimetre('GR-TEST'))")
    assert R["erreurs"] == [] and R["nouvelles"] == 0 and R["modifiees"] == 0 and R["identiques"] == 7
    # Une valeur modifiée, une ajoutée, une négative sur une quantité
    pg.evaluate("""(i) => { window.L = fab(M); const T = L.classeur['Tourisme (RT)'];
      T.find(l => l[0] === 'DEMO-2001' && l[2] === '2026-10')[i] = 1600;
      T.find(l => l[0] === 'DEMO-2002' && l[2] === '2026-09')[i] = 1400;
      T.find(l => l[0] === 'DEMO-2002' && l[2] === '2026-10')[3] = -3; }""", i)
    R = pg.evaluate("validerModeleKpi(L, perimetre('GR-TEST'))")
    assert R["erreurs"] == [] and R["modifiees"] == 1 and R["nouvelles"] == 1 and len(R["ecartees"]) == 1
    # Import enregistré par l'aperçu habituel
    pg.evaluate("etat.import = { nom: 'Zenitude_Modele_KPI.xlsx', feuille: 'toutes', lignes: L, R: validerModeleKpi(L, perimetre('GR-TEST')) }; majContenu(); true")
    assert "modèle Excel du catalogue" in pg.inner_text("#cons-resultat") and "Points d’attention" in pg.inner_text("#cons-resultat")
    pg.click("#cons-ok")
    pg.wait_for_function("!document.getElementById('cons-resultat')")
    T = pg.evaluate("tablesTest.mesures_importees")
    assert next(x for x in T if x["dossier"] == "DEMO-2001" and x["mois"] == "2026-10" and x["mesure"] == "LN_DISPO_HOT")["valeur"] == 1600
    assert pg.evaluate("tablesTest.depots_kpi.length") == 1
    assert erreurs == []
    pg.close()


def test_modele_excel_refus(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    gid = groupe(pg, "DEMO-2001", "DEMO-2002", "DEMO-2003")
    page(pg, "import", "externes", gid)
    pg.evaluate(f"window.M = construireModeleExcel(perimetre('{gid}'), '2026-10', '2026-10'); window.fab = {lignes_js()}; true")
    # Donnée inconnue du catalogue
    R = pg.evaluate("(() => { const L = fab(M); L.classeur['Tourisme (RT)'][1].push('DONNEE_INCONNUE'); return validerModeleKpi(L, perimetre('GR-TEST')); })()")
    assert any("DONNEE_INCONNUE inconnue du catalogue" in e["motif"] for e in R["erreurs"])
    # Résidence passée à un autre modèle depuis l'export
    pg.evaluate("RES_MODELES['DEMO-2002'] = 'SENIORS'; true")
    R = pg.evaluate("validerModeleKpi(fab(M), perimetre('GR-TEST'))")
    assert any("suit le modèle Seniors, pas Tourisme" in e["motif"] for e in R["erreurs"])
    pg.evaluate("RES_MODELES['DEMO-2002'] = 'TOURISME'; true")
    # Donnée désactivée depuis l'export
    pg.evaluate("elementCat('CA_MEWS_SPA').actif = false; true")
    R = pg.evaluate("validerModeleKpi(fab(M), perimetre('GR-TEST'))")
    assert any("CA spa HT" in e["motif"] and "désactivée" in e["motif"] for e in R["erreurs"])
    pg.evaluate("elementCat('CA_MEWS_SPA').actif = true; true")
    # Donnée ajoutée au modèle depuis l'export : avertissement, pas de blocage
    pg.evaluate("CAT.push({ code: 'NOUVELLE', type: 'donnee', libelle: 'Nouvelle donnée', rubrique: 'Test', unite: 'nombre', actif: true, modeles: ['TOURISME'], signe: 'positif', numerateur: [], denominateur: [], facteur: 1, ordre: 999 }); true")
    R = pg.evaluate("validerModeleKpi(fab(M), perimetre('GR-TEST'))")
    assert R["erreurs"] == [] and any("Nouvelle donnée" in a["motif"] and "réexportez" in a["motif"] for a in R["avertissements"])
    # Format inconnu
    R = pg.evaluate("(() => { const L = fab(M); L[4][1] = 'AUTRE'; return validerModeleKpi(L, perimetre('GR-TEST')); })()")
    assert "format du modèle inconnu" in R["erreurs"][0]["motif"]
    assert pg.evaluate("estModeleKpi(fab(M))") is True and pg.evaluate("estModeleKpi([['Résidence (nom Mews)']])") is False
    assert erreurs == []
    pg.close()


def test_export_bloque_sans_modele(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables(modeles=False))
    page(pg, "import", "externes", "GROUPE")
    assert pg.is_disabled("#mod-export") and "Export bloqué" in pg.inner_text("#mod-bloc")
    page(pg, "tableaux", "suivi", "GROUPE")
    assert "sans modèle de suivi" in pg.inner_text("#contenu")
    assert erreurs == []
    pg.close()


def test_migration_012_absente(site):
    pg, erreurs = demarrer(site, tables_en_plus=tables())
    pg.evaluate("D.lot20 = false; true")
    page(pg, "import", "parametres", "GROUPE")
    assert "Migration 012 non appliquée" in pg.inner_text("#contenu")
    page(pg, "tableaux", "suivi", "GROUPE")
    assert "Catalogue indisponible" in pg.inner_text("#contenu")
    assert erreurs == []
    pg.close()
