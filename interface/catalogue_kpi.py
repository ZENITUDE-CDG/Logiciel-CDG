"""Catalogue de départ du suivi KPI paramétrable (lot 20, décision 0014).

Source unique des valeurs de départ :
- la migration 012 les insère dans la base (une seule fois : ON CONFLICT DO NOTHING) ; un test vérifie que le bloc
  SQL de la migration est exactement celui que produit `sql_amorce()` ;
- la page de démonstration locale (sans base) les reçoit par `generer_site.construire`.

Deux sortes d'éléments :
- donnée : valeur mensuelle saisie ou importée par résidence (code stable, jamais un ratio) ;
- indicateur : calculé, jamais importé = facteur x somme(numérateur) / somme(dénominateur), sommes faites sur les
  résidences et les mois retenus (ratio de sommes, invariant 4). Sans dénominateur : facteur x somme(numérateur).
Un modèle de suivi (Tourisme, Seniors, Étudiants) dit quelles données et quels indicateurs suit une résidence.
Exemple de départ repris du consolidé KPI (lot 19), à ajuster dans la page Paramètres KPI.
"""

MODELES = [
    {"id": "TOURISME", "libelle": "Tourisme (RT)", "ordre": 1},
    {"id": "SENIORS", "libelle": "Seniors", "ordre": 2},
    {"id": "ETUDIANTS", "libelle": "Étudiants", "ordre": 3},
]
# Modèle proposé d'après l'activité de la résidence (référentiel) ; toujours modifiable.
MODELE_PAR_ACTIVITE = {"Hôtellerie": "TOURISME", "Seniors": "SENIORS", "Mixte": "SENIORS", "Étudiants": "ETUDIANTS"}

T, S, E = "TOURISME", "SENIORS", "ETUDIANTS"
TOUS = [T, S, E]


def _d(code, libelle, rubrique, unite, modeles, colonne, signe="positif"):
    return {"code": code, "type": "donnee", "libelle": libelle, "rubrique": rubrique, "unite": unite, "modeles": modeles,
            "colonne_consolide": colonne, "signe": signe, "numerateur": [], "denominateur": [], "facteur": 1,
            "sens": None, "seuil": None}


def _i(code, libelle, rubrique, unite, modeles, num, den, colonne=None, sens="haut", facteur=1):
    return {"code": code, "type": "indicateur", "libelle": libelle, "rubrique": rubrique, "unite": unite, "modeles": modeles,
            "colonne_consolide": colonne, "signe": "positif", "numerateur": num, "denominateur": den, "facteur": facteur,
            "sens": sens, "seuil": None}


CATALOGUE = [
    # Indicateurs (en tête de chaque rubrique)
    _i("TO_RES", "Taux d'occupation de la résidence", "Hébergement", "pourcent", TOUS, ["LN_VENDUES"], ["LN_DISPONIBLES"], "TO résidence"),
    _i("TO_HOT", "Taux d'occupation hôtelier", "Hébergement", "pourcent", TOUS, ["LN_VENDUES_HOT"], ["LN_DISPO_HOT"], "TO hôtelier"),
    _i("PM", "Prix moyen chambre", "Hébergement", "euro", TOUS, ["CA_MEWS_HEB_HOT"], ["LN_VENDUES_HOT"], "PM"),
    _i("REVPAR", "RevPar", "Hébergement", "euro", TOUS, ["CA_MEWS_HEB_HOT"], ["LN_DISPO_HOT"], "RevPar"),
    _i("REVPAC", "RevPac", "Hébergement", "euro", TOUS, ["CA_MEWS_HOTELIER"], ["NUITEES_CLIENTS"], "RevPac"),
    _i("DMS", "Durée moyenne de séjour", "Hébergement", "jours", TOUS, ["LN_VENDUES_HOT"], ["NB_SEJOURS"], "DMS"),
    _i("TO_SEN", "Taux d'occupation seniors", "Seniors", "pourcent", [S], ["NUITEES_SEN"], ["LN_DISPO_SEN"], "TO seniors"),
    _i("CAPTAGE_PDJ", "Taux de captage petit-déjeuner", "Restauration", "pourcent", [T, S], ["COUVERTS_PDJ"], ["NUITEES_CLIENTS"], "Captage PDJ"),
    _i("CA_TOTAL", "CA total de la résidence", "Chiffre d'affaires", "euro", TOUS, ["CA_MEWS_TOTAL"], []),
    # Données
    _d("LN_VENDUES", "Nuitées totales", "Hébergement", "nombre", TOUS, "Nuitées totales"),
    _d("LN_DISPONIBLES", "Capacité totale (lots × jours)", "Hébergement", "nombre", TOUS, "Capacité totale"),
    _d("LOTS_HOT", "Lots hôteliers", "Hébergement", "nombre", TOUS, "Lots hôtelier"),
    _d("LN_VENDUES_HOT", "Chambres vendues hôtelières", "Hébergement", "nombre", TOUS, "Chambres vendues hôtelières"),
    _d("LN_DISPO_HOT", "Capacité hôtelière (lots × jours)", "Hébergement", "nombre", TOUS, "Capacité hôtelière (lots × jours)"),
    _d("NB_SEJOURS", "Nombre de réservations", "Hébergement", "nombre", TOUS, "Nb de réservations"),
    _d("NUITEES_CLIENTS", "Clients présents", "Hébergement", "nombre", TOUS, "Clients présents"),
    _d("LOTS_SEN", "Lots seniors", "Seniors", "nombre", [S], "Lots seniors"),
    _d("LOTS_SEN_OCC", "Lots seniors occupés", "Seniors", "nombre", [S], "Lots seniors occupés"),
    _d("NUITEES_SEN", "Nuitées seniors", "Seniors", "nombre", [S], "Nuitées seniors"),
    _d("LN_DISPO_SEN", "Capacité seniors", "Seniors", "nombre", [S], "Capacité seniors"),
    _d("CA_MEWS_HEB_SEN", "CA hébergement seniors HT", "Seniors", "euro", [S], "CA hébergement seniors HT", "signe"),
    _d("CA_SAP", "CA SAP HT", "Seniors", "euro", [S], "CA SAP", "signe"),
    _d("CA_RESTO_SEN", "CA restauration seniors HT", "Seniors", "euro", [S], "CA Restauration seniors", "signe"),
    _d("COUVERTS_PDJ", "Petits-déjeuners servis", "Restauration", "nombre", [T, S], "Nb PDJ"),
    _d("CA_MEWS_PDJ", "CA petit-déjeuner HT", "Restauration", "euro", [T, S], "CA HT PDJ", "signe"),
    _d("CA_MEWS_RESTO", "CA restaurant HT", "Restauration", "euro", [T, S], "CA HT RESTO", "signe"),
    _d("CA_MEWS_TOTAL", "CA total résidence HT", "Chiffre d'affaires", "euro", TOUS, "CA total résidence HT", "signe"),
    _d("CA_MEWS_HOTELIER", "CA total hôtelier HT", "Chiffre d'affaires", "euro", TOUS, "CA total hôtelier HT", "signe"),
    _d("CA_MEWS_HEB_HOT", "CA hébergement hôtelier HT", "Chiffre d'affaires", "euro", TOUS, "CA hébergement hôtelier HT", "signe"),
    _d("CA_MEWS_SPA", "CA spa HT", "Chiffre d'affaires", "euro", [T], "CA HT SPA", "signe"),
]
for _n, _x in enumerate(CATALOGUE):
    _x["ordre"] = (_n + 1) * 10
    _x["actif"] = True


def _sql(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "ARRAY[" + ", ".join(_sql(x) for x in v) + "]::text[]" if v else "'{}'::text[]"
    return "'" + str(v).replace("'", "''") + "'"


COLONNES = ["code", "type", "libelle", "rubrique", "ordre", "unite", "actif", "modeles", "colonne_consolide", "signe",
            "numerateur", "denominateur", "facteur", "sens", "seuil"]


def sql_amorce():
    """Bloc SQL d'amorçage (inclus tel quel dans migrations/012_suivi_kpi_parametrable.sql)."""
    out = ["-- >>> amorce générée par interface/catalogue_kpi.py (ne pas modifier à la main)",
           "INSERT INTO kpi_modeles (id, libelle, ordre) VALUES"]
    out.append(",\n".join(f"  ({_sql(m['id'])}, {_sql(m['libelle'])}, {m['ordre']})" for m in MODELES) + "\nON CONFLICT (id) DO NOTHING;")
    out.append("INSERT INTO kpi_catalogue (" + ", ".join(COLONNES) + ") VALUES")
    # Données d'abord : la base vérifie que la formule d'un indicateur n'utilise que des données existantes.
    rangees = sorted(CATALOGUE, key=lambda x: x["type"] != "donnee")
    out.append(",\n".join("  (" + ", ".join(_sql(x[c]) for c in COLONNES) + ")" for x in rangees) + "\nON CONFLICT (code) DO NOTHING;")
    out.append("-- <<< fin de l'amorce")
    return "\n".join(out)


if __name__ == "__main__":
    print(sql_amorce())
