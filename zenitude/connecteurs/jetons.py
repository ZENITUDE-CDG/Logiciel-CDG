"""Jetons Pennylane chiffrés, un par dossier (lot 19, décision 0013).

Chaîne de confiance :
- la page génère une paire de clés RSA dans le navigateur d'un administrateur ; la clé PUBLIQUE est rangée dans
  la base (table cle_jetons), la clé PRIVÉE est copiée une seule fois dans le secret GitHub PENNYLANE_CLE_PRIVEE ;
- un jeton collé dans la page est chiffré dans le navigateur (RSA-OAEP SHA-256 + AES-GCM 256) avant tout envoi :
  la base, la page et les autres administrateurs ne voient jamais le jeton en clair ;
- seul GitHub Actions déchiffre, avec la clé privée, pour tester le jeton (GET /me) ou lire le dossier.

Format du jeton chiffré (texte) : « v1.<clé AES chiffrée>.<iv>.<données chiffrées + étiquette> », en base64.
Empreinte d'une clé : SHA-256 (hexadécimal) de la clé publique au format SPKI DER.

Le test d'un jeton ne lit que l'identité de la société (aucune donnée comptable) et vérifie :
- que le jeton est accepté par Pennylane ;
- que TOUS ses droits sont en lecture seule (sinon refusé et effacé) ;
- que la société est celle déjà rattachée à cette résidence, et qu'elle n'est rattachée à aucune autre
  (jeton collé au mauvais endroit : refusé et effacé).
Aucun jeton, en clair ou chiffré, n'est jamais affiché ni écrit dans un journal.
"""
import base64
import hashlib
from datetime import date, datetime, timezone

from . import pennylane as pl

VERSION = "v1"
ETATS = ("a_tester", "connectee", "refusee", "a_renouveler", "erreur")


class ErreurCle(Exception):
    """Clé privée absente, illisible ou différente de la clé publique du logiciel."""


def _b64(texte):
    return base64.b64decode(texte + "=" * (-len(texte) % 4))


def charger_cle_privee(pem):
    from cryptography.hazmat.primitives import serialization
    if not pem or "PRIVATE KEY" not in pem:
        raise ErreurCle("secret PENNYLANE_CLE_PRIVEE absent ou incomplet (il commence par -----BEGIN PRIVATE KEY-----)")
    try:
        return serialization.load_pem_private_key(pem.strip().encode(), password=None)
    except Exception:
        raise ErreurCle("secret PENNYLANE_CLE_PRIVEE illisible : recopiez la clé entière, lignes BEGIN et END comprises") from None


def empreinte_publique(cle_privee):
    from cryptography.hazmat.primitives import serialization
    der = cle_privee.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def empreinte_spki_b64(cle_publique_b64):
    return hashlib.sha256(_b64(cle_publique_b64)).hexdigest()


def chiffrer(jeton, cle_publique_b64):
    """Même chiffrement que la page (utilisé par les tests ; la page chiffre avec WebCrypto)."""
    import os
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pub = serialization.load_der_public_key(_b64(cle_publique_b64))
    k, iv = AESGCM.generate_key(bit_length=256), os.urandom(12)
    c = AESGCM(k).encrypt(iv, jeton.encode("utf-8"), None)
    w = pub.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return ".".join([VERSION] + [base64.b64encode(x).decode() for x in (w, iv, c)])


def dechiffrer(jeton_chiffre, cle_privee):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    parts = (jeton_chiffre or "").split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        raise ErreurCle("jeton chiffré illisible (format inconnu)")
    try:
        k = cle_privee.decrypt(_b64(parts[1]), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        return AESGCM(k).decrypt(_b64(parts[2]), _b64(parts[3]), None).decode("utf-8").strip()
    except Exception:
        raise ErreurCle("jeton impossible à déchiffrer avec la clé privée de GitHub") from None


def _scopes(me):
    """Droits du jeton tels que /me les renvoie (plusieurs emplacements possibles), ou None s'ils sont absents."""
    for porteur in (me, me.get("token") or {}, me.get("user") or {}, me.get("api_token") or {}):
        s = porteur.get("scopes") if isinstance(porteur, dict) else None
        if isinstance(s, str):
            s = s.replace(",", " ").split()
        if isinstance(s, list):
            return [str(x) for x in s]
    return None


def lecture_seule(scopes):
    return bool(scopes) and all(str(s).endswith(":readonly") for s in scopes)


def _maintenant():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def tester(connexion, cle_privee, autres, client_de=None, aujourdhui=None):
    """Teste un jeton. connexion : ligne de connexions_pennylane (avec jeton_chiffre) ; autres : {societe_attendue:
    dossier} des autres résidences. Renvoie les colonnes à écrire (état, motif, société, droits, date du test,
    et jeton_chiffre = None quand le jeton doit être effacé)."""
    client_de = client_de or (lambda jeton: pl.Client(jeton))
    aujourdhui = aujourdhui or date.today()
    out = {"teste_le": _maintenant()}

    def refus(motif, effacer=False, etat="refusee"):
        out.update({"etat": etat, "motif": motif[:300]})
        if effacer:
            out.update({"jeton_chiffre": None, "fin_jeton": None})
        return out

    if not connexion.get("jeton_chiffre"):
        return refus("aucun jeton enregistré", etat="erreur")
    if connexion.get("empreinte_cle") != empreinte_publique(cle_privee):
        return refus("jeton chiffré avec une autre clé que celle de GitHub : saisissez-le de nouveau")
    try:
        jeton = dechiffrer(connexion["jeton_chiffre"], cle_privee)
    except ErreurCle as e:
        return refus(str(e))
    try:
        me = client_de(jeton).get("/me")
    except pl.ErreurPennylane as e:
        if "401" in str(e):
            return refus("jeton refusé par Pennylane : expiré, supprimé ou mal copié")
        if "403" in str(e):
            return refus("accès refusé par Pennylane (403) : droits du jeton insuffisants")
        return refus("Pennylane injoignable ou réponse inattendue : réessayez plus tard", etat="erreur")
    finally:
        jeton = None
    societe = (me or {}).get("company") or {}
    sid = str(societe.get("id") or "").strip()
    nom = str(societe.get("name") or "").strip()[:200]
    if not sid:
        return refus("Pennylane n'a pas indiqué la société de ce jeton", etat="erreur")
    out.update({"societe_id": sid[:40], "societe_nom": nom})
    scopes = _scopes(me or {})
    if scopes is not None:
        out["droits"] = scopes[:40]
        if not lecture_seule(scopes):
            ecrits = [s for s in scopes if not s.endswith(":readonly")]
            return refus("jeton avec des droits d'écriture (" + ", ".join(ecrits[:5]) + ") : recréez-le en « Lecture seule » "
                         "dans Pennylane ; il a été effacé du logiciel", effacer=True)
    attendue = connexion.get("societe_attendue")
    if attendue and attendue != sid:
        return refus(f"ce jeton ouvre la société « {nom} » (n° {sid}), alors que cette résidence est rattachée à la société "
                     f"n° {attendue} : jeton effacé", effacer=True)
    if sid in autres and autres[sid] != connexion.get("dossier"):
        return refus(f"la société « {nom} » est déjà rattachée à la résidence {autres[sid]} : jeton effacé", effacer=True)
    out.update({"etat": "connectee", "societe_attendue": sid,
                "motif": None if scopes is not None else
                "Pennylane n'indique pas les droits du jeton : vérifiez dans Pennylane qu'il est en « Lecture seule »"})
    expire = connexion.get("expire_le")
    if expire and str(expire) < aujourdhui.isoformat():
        out.update({"etat": "a_renouveler", "motif": "date d'expiration dépassée : créez un nouveau jeton"})
    return out


def libelle_etat(etat):
    return {"a_tester": "à tester", "connectee": "connectée", "refusee": "refusée", "a_renouveler": "à renouveler",
            "erreur": "erreur"}.get(etat, etat)
