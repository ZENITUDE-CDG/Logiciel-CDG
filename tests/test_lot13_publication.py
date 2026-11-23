"""Lot 13 : publication des chiffres du moteur dans la base (décision 0007). Données fictives.

Vérifie le découpage (partie commune sans aucune donnée de résidence, une partie par résidence ne
contenant que la sienne), les garde-fous (résidence réelle refusée, dossier inconnu signalé), les
requêtes envoyées à Supabase (sans réseau : envoi simulé) et l'absence de clé secrète dans le dépôt.
"""
import json
import pathlib
import re
import subprocess
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "interface"))
sys.path.insert(0, str(RACINE / "scripts"))
import assembler_installation  # noqa: E402
import generer_demo  # noqa: E402
import publier_supabase as pub  # noqa: E402


@pytest.fixture(scope="module")
def decoupe(tmp_path_factory):
    demo = tmp_path_factory.mktemp("demo13")
    generer_demo.main(str(demo))
    return pub.calculer(str(demo))


def base_complete(par, fictif=True):
    return [{"id": c["residence"]["code"], "dossier_pennylane": d, "fictif": fictif} for d, c in par.items()]


def test_huit_residences_decoupees(decoupe):
    commun, par = decoupe
    assert sorted(par) == [f"DEMO-200{i}" for i in range(1, 9)]
    for cle in ("kpi", "lignes_ebitda", "lignes_sig", "cr_lignes", "calcul", "plan_comptes", "meta"):
        assert cle in commun


def test_partie_commune_sans_donnee_de_residence(decoupe):
    commun, par = decoupe
    texte = json.dumps(commun, ensure_ascii=False)
    assert "DEMO-" not in texte
    for c in par.values():
        assert c["residence"]["nom"] not in texte
    for cle in pub.PAR_RESIDENCE:
        assert cle not in commun
    assert not {"compta", "couverts", "exploitation"} & set(commun["calcul"])
    assert "dossiers" not in commun["tresorerie"]


def test_chaque_partie_ne_contient_que_sa_residence(decoupe):
    _, par = decoupe
    for d, c in par.items():
        texte = json.dumps(c, ensure_ascii=False)
        autres = {x for x in re.findall(r"DEMO-\d{4}", texte)} - {d}
        assert not autres, (d, autres)
        assert c["nb_ecritures"] > 0 and c["compta"] and c["finance"]["dossier"] == d


def test_lignes_et_empreintes(decoupe):
    commun, par = decoupe
    commune, lignes, avert = pub.lignes_a_publier(commun, par, base_complete(par))
    assert commune["id"] == "SITE" and commune["fictif"] is True and len(commune["empreinte"]) == 64
    assert [l["residence_id"] for l in lignes] == [f"RES-00{i}" for i in range(1, 9)]
    assert all(l["empreinte"] == pub.empreinte(l["contenu"]) for l in lignes)
    assert avert == []


def test_residence_reelle_refusee(decoupe):
    commun, par = decoupe
    base = base_complete(par)
    base[2]["fictif"] = False
    with pytest.raises(pub.PublicationRefusee, match="réelles"):
        pub.lignes_a_publier(commun, par, base)


def test_dossier_rattache_deux_fois_refuse(decoupe):
    commun, par = decoupe
    base = base_complete(par) + [{"id": "RES-099", "dossier_pennylane": "DEMO-2001", "fictif": True}]
    with pytest.raises(pub.PublicationRefusee, match="plusieurs"):
        pub.lignes_a_publier(commun, par, base)


def test_residences_manquantes_signalees(decoupe):
    commun, par = decoupe
    base = [r for r in base_complete(par) if r["dossier_pennylane"] != "DEMO-2008"]
    base.append({"id": "RES-901", "dossier_pennylane": "PENNY-9001", "fictif": True})
    _, lignes, avert = pub.lignes_a_publier(commun, par, base)
    assert len(lignes) == 7
    assert any("DEMO-2008" in a for a in avert) and any("RES-901" in a for a in avert)


def test_base_vide_refusee(decoupe):
    commun, par = decoupe
    with pytest.raises(pub.PublicationRefusee, match="installation_supabase"):
        pub.lignes_a_publier(commun, par, [])


def test_requetes_envoyees(decoupe):
    commun, par = decoupe
    commune, lignes, _ = pub.lignes_a_publier(commun, par, base_complete(par))
    appels = []
    pub.publier("https://exemple.supabase.co", "sb_secret_FICTIF", commune, lignes,
                envoyer=lambda m, u, c, corps, prefer: appels.append((m, u, corps, prefer)))
    assert len(appels) == 9
    assert appels[0][1].endswith("/rest/v1/donnees_communes?on_conflict=id")
    assert all(a[1].endswith("/rest/v1/donnees_residences?on_conflict=residence_id") for a in appels[1:])
    assert all(a[0] == "POST" and "merge-duplicates" in a[3] for a in appels)
    assert "sb_secret" not in json.dumps([a[2] for a in appels], ensure_ascii=False)


def test_entetes_selon_le_type_de_cle():
    assert pub.entetes("sb_secret_x") == {"apikey": "sb_secret_x", "Content-Type": "application/json"}
    h = pub.entetes("eyJhbGciOi.fictif")
    assert h["Authorization"] == "Bearer eyJhbGciOi.fictif"


def test_sans_secret_la_publication_s_arrete(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setattr(pub, "calculer", lambda: ({}, {}))
    assert pub.main([]) == 1
    assert "SUPABASE_SECRET_KEY" in capsys.readouterr().err
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_publishable_xxx")
    assert pub.main([]) == 1


def test_adresse_lue_dans_config():
    assert pub.url_supabase().startswith("https://") and pub.url_supabase().endswith(".supabase.co")


def test_installation_supabase_a_jour():
    actuel = (RACINE / "scripts" / "installation_supabase.sql").read_text(encoding="utf-8")
    assert actuel == assembler_installation.assembler(), \
        "Lancer python scripts/assembler_installation.py et committer scripts/installation_supabase.sql"


def test_aucune_cle_secrete_dans_le_depot():
    try:
        fichiers = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True, text=True,
                                  check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        fichiers = [str(p.relative_to(RACINE)) for p in RACINE.rglob("*") if p.is_file() and ".git" not in p.parts]
    motif = re.compile(r"sb_secret_[A-Za-z0-9_-]{12,}|service_role\"\s*:\s*\"eyJ")
    for f in fichiers:
        p = RACINE / f
        if p.suffix in (".png", ".xlsx", ".zip") or not p.exists():
            continue
        assert not motif.search(p.read_text(encoding="utf-8", errors="ignore")), f


def test_page_en_ligne_sans_donnees():
    texte = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "var D = null;" in texte
    assert "DEMO-200" not in texte


def test_index_html_a_jour(tmp_path):
    """La page publiée (index.html à la racine) doit être celle que produit le gabarit actuel : sinon le site
    affiche une ancienne version alors que le reste du dépôt est à jour (oubli de déposer index.html)."""
    import generer_site
    attendu = tmp_path / "index.html"
    generer_site.ecrire(str(attendu), None)
    assert (RACINE / "index.html").read_text(encoding="utf-8") == attendu.read_text(encoding="utf-8"), \
        "index.html n'est pas à jour : déposer le index.html livré avec interface/gabarit.html"
