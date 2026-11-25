// Tests de la fonction « lancer-synchro » (contrôle de la demande). Lancement : deno test --allow-env (hors GitHub Actions).
function assertEquals(a: unknown, b: unknown) {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`attendu ${JSON.stringify(b)}, obtenu ${JSON.stringify(a)}`);
}
import { controler } from "./index.ts";

const ok = { dossiers: ["PENNY-TEST", "PENNY-TEST"], mois_debut: "2026-01", mois_fin: "2026-10", masquer_brouillard: true, perimetre: "Groupe" };

Deno.test("demande correcte, doublons retirés", () => {
  assertEquals(controler(ok).demande, { dossiers: ["PENNY-TEST"], mois_debut: "2026-01", mois_fin: "2026-10", masquer_brouillard: true, perimetre: "Groupe" });
});
Deno.test("mois sans borne accepté", () => {
  assertEquals(controler({ ...ok, mois_debut: null, mois_fin: undefined }).demande?.mois_fin, null);
});
Deno.test("refus", () => {
  for (const [corps, motif] of [
    [null, "demande illisible"],
    [{ ...ok, dossiers: [] }, "liste de résidences vide ou trop longue"],
    [{ ...ok, dossiers: ["penny test"] }, "identifiant de dossier invalide"],
    [{ ...ok, mois_debut: "2026-13" }, "mois de début invalide (AAAA-MM)"],
    [{ ...ok, mois_fin: "26-10" }, "mois de fin invalide (AAAA-MM)"],
    [{ ...ok, mois_debut: "2026-11", mois_fin: "2026-10" }, "le mois de début est après le mois de fin"],
    [{ ...ok, masquer_brouillard: "oui" }, "option brouillard manquante"],
  ] as const) assertEquals(controler(corps).erreur, motif);
});
Deno.test("périmètre tronqué à 120 caractères", () => {
  assertEquals(controler({ ...ok, perimetre: "x".repeat(300) }).demande?.perimetre.length, 120);
});
Deno.test("décision 0017 : plus de demande de test des jetons", () => {
  assertEquals(controler({ ...ok, type: "test" }).erreur, "type de demande inconnu");
  assertEquals(controler({ ...ok, type: "inconnu" }).erreur, "type de demande inconnu");
  assertEquals(controler({ ...ok, type: "synchro" }).demande?.masquer_brouillard, true);
});
