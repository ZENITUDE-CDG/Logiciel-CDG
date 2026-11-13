"""Dépôt, approbation, application et retour arrière des versions de configuration (lot 4).

Règles (docs/configuration.md §7) :
- seule une version valide peut être déposée ;
- le déposant ne peut pas approuver sa propre version ;
- une version doit être approuvée avant application ;
- l'application ne modifie aucune donnée : elle change seulement la version courante ;
- un retour arrière remet une version antérieure courante, sans toucher aux données ;
- les publications conservent la version de configuration utilisée à leur création.

Stockage : un dossier contenant state.json (écrit de façon atomique) et des copies des classeurs
nommées par empreinte. Un seul rédacteur à la fois : aucun verrou inter-processus n'est implémenté.
"""
import hashlib
import json
import os
import shutil
from datetime import datetime

from . import controles, impact


class RefusDepot(Exception):
    pass


class RefusAction(Exception):
    pass


def _maintenant():
    return datetime.now().replace(microsecond=0).isoformat()


class Depot:
    def __init__(self, dossier):
        self.dossier = dossier
        self.fichiers = os.path.join(dossier, "fichiers")
        self.etat_path = os.path.join(dossier, "state.json")
        os.makedirs(self.fichiers, exist_ok=True)
        if not os.path.exists(self.etat_path):
            self._ecrire({"versions": [], "courante": None, "journal": [], "publications": []})

    # --- état -----------------------------------------------------------------
    def _lire(self):
        with open(self.etat_path, encoding="utf-8") as f:
            return json.load(f)

    def _ecrire(self, etat):
        tmp = self.etat_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.etat_path)

    def _journal(self, etat, action, auteur, detail):
        etat["journal"].append({"date": _maintenant(), "action": action, "auteur": auteur, "detail": detail})

    def _version(self, etat, vid):
        for v in etat["versions"]:
            if v["id"] == vid:
                return v
        raise RefusAction(f"version inconnue : {vid}")

    # --- lecture --------------------------------------------------------------
    def statut(self):
        etat = self._lire()
        return {
            "courante": etat["courante"],
            "versions": [{k: v[k] for k in ("id", "statut", "auteur_depot", "date_depot", "empreinte")}
                         | {"approbations": [a["par"] for a in v["approbations"]]} for v in etat["versions"]],
            "publications": etat["publications"],
            "journal": etat["journal"],
        }

    # --- dépôt ----------------------------------------------------------------
    def deposer(self, classeur, auteur):
        rapport = controles.verifier(classeur)
        if rapport.erreurs:
            raise RefusDepot("classeur refusé : " + "; ".join(str(e) for e in rapport.erreurs))
        empreinte = rapport.empreinte
        etat = self._lire()
        for v in etat["versions"]:
            if v["empreinte"] == empreinte:
                raise RefusDepot(f"ce classeur est déjà déposé sous {v['id']}")
        destination = os.path.join(self.fichiers, empreinte + ".xlsx")
        if not os.path.exists(destination):
            shutil.copyfile(classeur, destination)
        apercu = None
        if etat["courante"]:
            courante = self._version(etat, etat["courante"])
            apercu = impact.comparer(os.path.join(self.fichiers, courante["empreinte"] + ".xlsx"), destination)
        vid = f"v{len(etat['versions']) + 1}"
        etat["versions"].append({
            "id": vid, "empreinte": empreinte, "statut": "déposée",
            "auteur_depot": auteur, "date_depot": _maintenant(),
            "approbations": [], "parent": etat["courante"],
            "apercu": apercu["resume"] if apercu else None,
        })
        self._journal(etat, "dépôt", auteur, vid)
        self._ecrire(etat)
        return vid

    # --- approbation ----------------------------------------------------------
    def approuver(self, vid, approbateur):
        etat = self._lire()
        v = self._version(etat, vid)
        if v["statut"] != "déposée":
            raise RefusAction(f"{vid} n'est pas en attente d'approbation (statut : {v['statut']})")
        if approbateur == v["auteur_depot"]:
            raise RefusAction("le déposant ne peut pas approuver sa propre version")
        if any(a["par"] == approbateur for a in v["approbations"]):
            raise RefusAction(f"{approbateur} a déjà approuvé {vid}")
        v["approbations"].append({"par": approbateur, "date": _maintenant()})
        v["statut"] = "approuvée"
        self._journal(etat, "approbation", approbateur, vid)
        self._ecrire(etat)

    # --- application ----------------------------------------------------------
    def appliquer(self, vid, auteur):
        etat = self._lire()
        v = self._version(etat, vid)
        if v["statut"] == "appliquée":
            raise RefusAction(f"{vid} est déjà appliquée")
        if v["statut"] != "approuvée":
            raise RefusAction(f"{vid} doit être approuvée avant application")
        chemin = os.path.join(self.fichiers, v["empreinte"] + ".xlsx")
        if _empreinte(chemin) != v["empreinte"]:
            raise RefusAction(f"fichier de {vid} modifié depuis le dépôt : application refusée")
        if controles.verifier(chemin).erreurs:
            raise RefusAction(f"{vid} n'est plus valide : application refusée")
        if etat["courante"]:
            self._version(etat, etat["courante"])["statut"] = "remplacée"
        v["statut"] = "appliquée"
        etat["courante"] = vid
        self._journal(etat, "application", auteur, vid)
        self._ecrire(etat)

    # --- retour arrière -------------------------------------------------------
    def revenir(self, vid, auteur):
        etat = self._lire()
        cible = self._version(etat, vid)
        if cible["statut"] != "remplacée":
            raise RefusAction(f"retour impossible vers {vid} (statut : {cible['statut']})")
        if etat["courante"]:
            self._version(etat, etat["courante"])["statut"] = "remplacée"
        cible["statut"] = "appliquée"
        etat["courante"] = vid
        self._journal(etat, "retour arrière", auteur, vid)
        self._ecrire(etat)

    def _journal_refus(self, etat, action, auteur, dossier, non_classes):
        self._journal(etat, action, auteur, f"{dossier} : comptes non classés {', '.join(non_classes)}")


def _empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()
