"""Lot 26 - DSN mensuelles FICTIVES (norme NEODeS, rubriques utilisées par zenitude/social/dsn.py).

Un fichier par mois, chacun contenant une déclaration par résidence de démonstration (envoi multiple),
de octobre 2025 au dernier mois importé de la démonstration. Le brut déclaré est égal au compte 641 de la
démonstration (interface/demo/ecritures.csv), sauf des anomalies volontaires pour le rapprochement :
  - DEMO-2003, juin 2026 : brut DSN inférieur de 1 234,56 € au compte 641 ;
  - DEMO-2005, février 2026 : pas de DSN (mois manquant) ;
  - DEMO-2008, mai 2026 : déclaration « annule et remplace » (type 03).
Arrêts de travail : déclarés le mois du début et le mois de la reprise (avec la date de reprise), un arrêt
en cours sans date de reprise, un salarié sans quotité lisible (ETP non calculable) dans DEMO-2007 en
mars 2026. Noms, NIR et SIRET inventés (« FICTIF »), aucune donnée réelle.

Usage : python tests/generer_dsn.py [dossier_sortie]   (défaut : interface/demo/dsn)
"""
from __future__ import annotations

import calendar
import csv
import datetime as dt
import pathlib
import random
import sys
from decimal import Decimal

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOIS = [f"{a}-{m:02d}" for a, m in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]]
ECART = ("DEMO-2003", "2026-06", Decimal("1234.56"))
MANQUANT = ("DEMO-2005", "2026-02")
REMPLACE = ("DEMO-2008", "2026-05")
SANS_QUOTITE = ("DEMO-2007", "2026-03")
MOTIFS_FIN = ["059", "031", "043", "034", "020", "039"]


def siret(dossier):
    return "999" + "00" + dossier[-4:] + "00011"


def jjmmaaaa(d):
    return d.strftime("%d%m%Y")


def fin_mois(m):
    a, mo = int(m[:4]), int(m[5:])
    return dt.date(a, mo, calendar.monthrange(a, mo)[1])


def debut_mois(m):
    return dt.date(int(m[:4]), int(m[5:]), 1)


def bruts_641():
    out = {}
    with open(RACINE / "interface" / "demo" / "ecritures.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["compte"].startswith("641"):
                cle = (r["dossier"], r["date"][:7])
                out[cle] = out.get(cle, Decimal(0)) + Decimal(r["debit"] or "0") - Decimal(r["credit"] or "0")
    return out


class Salarie:
    def __init__(self, rng, dossier, n, debut):
        self.n = n
        self.sexe = rng.choice(["01", "02", "02"])
        self.naissance = dt.date(rng.randint(1962, 2004), rng.randint(1, 12), rng.randint(1, 28))
        self.nir = ("1" if self.sexe == "01" else "2") + f"{self.naissance.year % 100:02d}{self.naissance.month:02d}99{n:06d}"
        self.debut = debut
        alea = rng.random()
        self.nature, self.dispositif = ("02", "99") if alea < 0.2 else ("01", "64") if alea < 0.27 else ("01", "99")
        self.cadre = "01" if n % 9 == 1 else "04"
        self.quotite = "151.67" if rng.random() < 0.75 else rng.choice(["104.00", "121.33", "86.67"])
        self.fin, self.motif_fin = None, None
        self.arrets = []  # (dernier jour travaillé, motif, fin prévue, reprise)
        self.dossier = dossier


def roster(rng, dossier, brut_moyen):
    n = max(6, int(brut_moyen / Decimal("2300")))
    sal = [Salarie(rng, dossier, i + 1, dt.date(rng.randint(2008, 2025), rng.randint(1, 12), rng.randint(1, 28)))
           for i in range(n)]
    for s in sal:
        if s.debut > dt.date(2025, 9, 1):
            s.debut = dt.date(2025, 9, 1)
    suivant = n + 1
    # mouvements : quelques sorties et entrées sur la période
    for k, m in enumerate(MOIS[1:], start=1):
        if rng.random() < 0.45:
            actifs = [s for s in sal if s.fin is None and s.debut < debut_mois(m)]
            if len(actifs) > 4:
                s = rng.choice(actifs)
                s.fin = debut_mois(m) + dt.timedelta(days=rng.randint(0, 27))
                s.motif_fin = "031" if s.nature == "02" else MOTIFS_FIN[k % len(MOTIFS_FIN)]
        if rng.random() < 0.5:
            s = Salarie(rng, dossier, suivant, debut_mois(m) + dt.timedelta(days=rng.randint(0, 20)))
            suivant += 1
            sal.append(s)
    # arrêts de travail
    for k, m in enumerate(MOIS):
        if rng.random() < 0.55:
            actifs = [s for s in sal if s.debut < debut_mois(m) and (s.fin is None or s.fin > fin_mois(m))]
            if actifs:
                s = rng.choice(actifs)
                dernier = debut_mois(m) + dt.timedelta(days=rng.randint(0, 25))
                duree = rng.choice([3, 8, 15, 30, 45, 70])
                motif = rng.choice(["01", "01", "01", "06", "02"])
                reprise = dernier + dt.timedelta(days=duree + 1)
                if k >= len(MOIS) - 2 and duree >= 30:
                    reprise = None  # arrêt en cours, sans date de reprise
                s.arrets.append((dernier, motif, dernier + dt.timedelta(days=duree), reprise))
    return sal


def lignes_declaration(rng, dossier, m, s641, sal, type_decl):
    L, F = fin_mois(m), debut_mois(m)
    concernes = [s for s in sal if s.debut <= L and (s.fin is None or s.fin >= F)]
    payes = concernes
    poids = [Decimal(s.quotite) for s in payes]
    tot = sum(poids)
    brut = s641 - (ECART[2] if (dossier, m) == ECART[:2] else Decimal(0))
    parts, reste = [], brut
    for i, p in enumerate(poids):
        v = (brut * p / tot).quantize(Decimal("0.01")) if i < len(poids) - 1 else reste
        reste -= v
        parts.append(v)
    L_ = [("S20.G00.05.001", "01"), ("S20.G00.05.002", type_decl), ("S20.G00.05.003", "11"),
          ("S20.G00.05.004", f"{dossier}-{m}"), ("S20.G00.05.005", "01" + F.strftime("%m%Y")), ("S20.G00.05.007", jjmmaaaa(L)),
          ("S20.G00.05.010", "01")]
    sir = siret(dossier)
    L_ += [("S21.G00.06.001", sir[:9]), ("S21.G00.06.002", sir[9:]), ("S21.G00.06.003", "5510Z"),
           ("S21.G00.06.004", "1 RUE FICTIVE"), ("S21.G00.06.005", "75001"), ("S21.G00.06.006", "PARIS")]
    presents = [s for s in concernes if s.fin is None or s.fin >= L]
    L_ += [("S21.G00.11.001", sir[9:]), ("S21.G00.11.002", "5510Z"), ("S21.G00.11.003", "1 RUE FICTIVE"),
           ("S21.G00.11.004", "75001"), ("S21.G00.11.005", "PARIS"), ("S21.G00.11.008", str(len(presents)))]
    cotis = (brut * Decimal("0.62")).quantize(Decimal("0.01"))
    L_ += [("S21.G00.20.001", "78861779300013"), ("S21.G00.20.005", f"{cotis * Decimal('0.7'):.2f}"),
           ("S21.G00.20.010", "05"),
           ("S21.G00.20.001", "P0942"), ("S21.G00.20.005", f"{cotis - (cotis * Decimal('0.7')).quantize(Decimal('0.01')):.2f}"),
           ("S21.G00.20.010", "05")]
    for s, b in zip(payes, parts):
        L_ += [("S21.G00.30.001", s.nir), ("S21.G00.30.002", "FICTIF"), ("S21.G00.30.004", f"SALARIE {s.n:03d}"),
               ("S21.G00.30.005", s.sexe), ("S21.G00.30.006", jjmmaaaa(s.naissance)), ("S21.G00.30.019", f"M{s.n:04d}")]
        q = s.quotite
        L_ += [("S21.G00.40.001", jjmmaaaa(s.debut)), ("S21.G00.40.002", "90"), ("S21.G00.40.003", s.cadre),
               ("S21.G00.40.004", "463a"), ("S21.G00.40.006", "EMPLOI FICTIF"), ("S21.G00.40.007", s.nature),
               ("S21.G00.40.008", s.dispositif), ("S21.G00.40.009", f"C{s.n:04d}"), ("S21.G00.40.011", "10"),
               ("S21.G00.40.012", "151.67")]
        if not ((dossier, m) == SANS_QUOTITE[:2] and s.n == 2):
            L_.append(("S21.G00.40.013", q))
        L_.append(("S21.G00.40.014", "10" if q == "151.67" else "20"))
        for dernier, motif, prevue, reprise in s.arrets:
            debut_abs = dernier + dt.timedelta(days=1)
            mois_debut = f"{debut_abs.year}-{debut_abs.month:02d}"
            mois_reprise = f"{reprise.year}-{reprise.month:02d}" if reprise else None
            if m == mois_debut or m == mois_reprise:
                L_ += [("S21.G00.60.001", motif), ("S21.G00.60.002", jjmmaaaa(dernier)), ("S21.G00.60.003", jjmmaaaa(prevue))]
                if reprise and m == mois_reprise:
                    L_ += [("S21.G00.60.010", jjmmaaaa(reprise)), ("S21.G00.60.011", "01")]
        if s.fin and F <= s.fin <= L:
            L_ += [("S21.G00.62.001", jjmmaaaa(s.fin)), ("S21.G00.62.002", s.motif_fin)]
        net = (b * Decimal("0.78")).quantize(Decimal("0.01"))
        pas = (net * Decimal("0.03")).quantize(Decimal("0.01"))
        L_ += [("S21.G00.50.001", jjmmaaaa(L)), ("S21.G00.50.002", f"{net:.2f}"), ("S21.G00.50.004", f"{net - pas:.2f}"),
               ("S21.G00.50.006", "3.00"), ("S21.G00.50.009", f"{pas:.2f}")]
        heures = Decimal(q) if s.fin is None or s.fin >= L else Decimal("70.00")
        L_ += [("S21.G00.51.001", jjmmaaaa(F)), ("S21.G00.51.002", jjmmaaaa(L)), ("S21.G00.51.010", f"C{s.n:04d}"),
               ("S21.G00.51.011", "001"), ("S21.G00.51.013", f"{b:.2f}")]
        L_ += [("S21.G00.51.001", jjmmaaaa(F)), ("S21.G00.51.002", jjmmaaaa(L)), ("S21.G00.51.010", f"C{s.n:04d}"),
               ("S21.G00.51.011", "002"), ("S21.G00.51.012", f"{heures:.2f}"), ("S21.G00.51.013", f"{b:.2f}")]
        if rng.random() < 0.25:
            hs = Decimal(rng.choice(["4.00", "7.50", "12.25"]))
            L_ += [("S21.G00.51.001", jjmmaaaa(F)), ("S21.G00.51.002", jjmmaaaa(L)), ("S21.G00.51.010", f"C{s.n:04d}"),
                   ("S21.G00.51.011", "017"), ("S21.G00.51.012", f"{hs:.2f}"), ("S21.G00.51.013", f"{hs * Decimal('14.10'):.2f}")]
        if rng.random() < 0.2:
            L_ += [("S21.G00.52.001", "026"), ("S21.G00.52.002", f"{Decimal(rng.choice(['50', '120', '300'])):.2f}")]
        L_ += [("S21.G00.78.001", "03"), ("S21.G00.78.002", jjmmaaaa(F)), ("S21.G00.78.003", jjmmaaaa(L)),
               ("S21.G00.78.004", f"{b:.2f}")]
    return L_


def generer(sortie):
    sortie = pathlib.Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    bruts = bruts_641()
    dossiers = sorted({d for d, _ in bruts})
    rng = random.Random(26)
    rosters = {d: roster(rng, d, sum(v for (dd, _), v in bruts.items() if dd == d) / 15) for d in dossiers}
    fichiers = []
    for m in MOIS:
        corps = []
        for d in dossiers:
            if (d, m) == MANQUANT:
                continue
            corps += lignes_declaration(rng, d, m, bruts[(d, m)], rosters[d], "03" if (d, m) == REMPLACE else "01")
        tete = [("S10.G00.00.001", "LOGICIEL PAIE FICTIF"), ("S10.G00.00.002", "EDITEUR FICTIF"), ("S10.G00.00.003", "1.0"),
                ("S10.G00.00.005", "02"), ("S10.G00.00.006", "P26V01"), ("S10.G00.00.008", "01"),
                ("S10.G00.01.001", "999000001"), ("S10.G00.01.002", "00011"), ("S10.G00.01.003", "ZENITUDE FICTIF")]
        n_decl = len(dossiers) - (1 if m == MANQUANT[1] else 0)
        toutes = tete + corps
        toutes += [("S90.G00.90.001", str(len(toutes) + 2)), ("S90.G00.90.002", str(n_decl))]
        texte = "\r\n".join(f"{k},'{v}'" for k, v in toutes) + "\r\n"
        f = sortie / f"DSN_FICTIVE_{m.replace('-', '')}.dsn"
        f.write_bytes(texte.encode("latin-1"))
        fichiers.append(f)
    return fichiers


if __name__ == "__main__":
    fs = generer(sys.argv[1] if len(sys.argv) > 1 else RACINE / "interface" / "demo" / "dsn")
    print(f"{len(fs)} fichiers DSN fictifs écrits dans {fs[0].parent}")
