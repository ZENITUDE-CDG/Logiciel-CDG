// Fonction serveur Supabase « lancer-synchro » (lot 18b, décision 0012 ; lot 19, décision 0013).
//
// Deux types de demande :
//   synchro (par défaut) : relire Pennylane, recalculer et publier (lot 18b) ;
//   test                 : tester les jetons Pennylane enregistrés dans le logiciel (lot 19) : identité de la
//                          société et droits, sans lire de comptabilité ni enregistrer de paramètres d'import.
//
// Appelée par la page Import comptable (bouton Synchroniser). Elle :
//   1. vérifie que la personne connectée est un administrateur actif (table profils) ;
//   2. contrôle la demande (dossiers connus, mois au format AAAA-MM, début <= fin) ;
//   3. refuse si une synchronisation est déjà en attente ou en cours (moins de 30 minutes) ;
//   4. enregistre les paramètres d'import de chaque résidence et la demande (table synchronisations) ;
//   5. lance immédiatement le workflow GitHub « Synchro Pennylane » avec le numéro de la demande.
//
// Secrets de la fonction (Supabase, Edge Functions, Secrets) - jamais dans le dépôt ni dans la page :
//   CLE_SECRETE_SUPABASE  clé secrète du projet (sb_secret_...), la même que le secret GitHub SUPABASE_SECRET_KEY
//   GITHUB_JETON_SYNCHRO  jeton GitHub à granularité fine : ce seul dépôt, droit « Actions : lecture et écriture »
// Variables facultatives :
//   GITHUB_DEPOT          par défaut ZENITUDE-CDG/Logiciel-CDG
//   ORIGINES_AUTORISEES   par défaut https://zenitude-cdg.github.io (séparer plusieurs adresses par des virgules)
// SUPABASE_URL est fourni par Supabase.
//
// Réglage dans Supabase : « Verify JWT with legacy secret » DÉSACTIVÉ (le projet utilise les nouvelles clés ;
// la fonction vérifie elle-même la session de la personne, étape 1).

import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const DEPOT = Deno.env.get("GITHUB_DEPOT") ?? "ZENITUDE-CDG/Logiciel-CDG";
const WORKFLOW = "synchro-pennylane-test.yml";
const ORIGINES = (Deno.env.get("ORIGINES_AUTORISEES") ?? "https://zenitude-cdg.github.io")
  .split(",").map((s) => s.trim()).filter(Boolean);
const MOIS = /^[0-9]{4}-(0[1-9]|1[0-2])$/;
const DOSSIER = /^[A-Z0-9_-]+$/;

function entetes(origine: string | null): Record<string, string> {
  const h: Record<string, string> = {
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Content-Type": "application/json",
    "Vary": "Origin",
  };
  if (origine && ORIGINES.includes(origine)) h["Access-Control-Allow-Origin"] = origine;
  return h;
}

function reponse(code: number, corps: unknown, origine: string | null): Response {
  return new Response(JSON.stringify(corps), { status: code, headers: entetes(origine) });
}

// Contrôle de la demande, sans accès réseau (testé à part).
export function controler(corps: any): { erreur?: string; demande?: any } {
  if (!corps || typeof corps !== "object") return { erreur: "demande illisible" };
  const dossiers = Array.isArray(corps.dossiers) ? [...new Set(corps.dossiers.map(String))] : [];
  if (!dossiers.length || dossiers.length > 500) return { erreur: "liste de résidences vide ou trop longue" };
  if (dossiers.some((d) => !DOSSIER.test(d as string))) return { erreur: "identifiant de dossier invalide" };
  const type = corps.type ?? "synchro";
  if (type !== "synchro" && type !== "test") return { erreur: "type de demande inconnu" };
  if (type === "test") return { demande: { type, dossiers, perimetre: String(corps.perimetre ?? "").slice(0, 120) } };
  const md = corps.mois_debut ?? null, mf = corps.mois_fin ?? null;
  if (md !== null && !MOIS.test(md)) return { erreur: "mois de début invalide (AAAA-MM)" };
  if (mf !== null && !MOIS.test(mf)) return { erreur: "mois de fin invalide (AAAA-MM)" };
  if (md && mf && md > mf) return { erreur: "le mois de début est après le mois de fin" };
  if (typeof corps.masquer_brouillard !== "boolean") return { erreur: "option brouillard manquante" };
  const perimetre = String(corps.perimetre ?? "").slice(0, 120);
  return { demande: { dossiers, mois_debut: md, mois_fin: mf, masquer_brouillard: corps.masquer_brouillard, perimetre } };
}

if (import.meta.main) Deno.serve(async (req) => {
  const origine = req.headers.get("Origin");
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: entetes(origine) });
  if (req.method !== "POST") return reponse(405, { erreur: "méthode non autorisée" }, origine);
  if (origine && !ORIGINES.includes(origine)) return reponse(403, { erreur: "origine non autorisée" }, origine);

  const cle = Deno.env.get("CLE_SECRETE_SUPABASE") ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const jetonGithub = Deno.env.get("GITHUB_JETON_SYNCHRO") ?? "";
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  if (!cle || !jetonGithub || !url) return reponse(500, { erreur: "fonction non configurée (secrets manquants)" }, origine);
  const base = createClient(url, cle, { auth: { persistSession: false, autoRefreshToken: false } });

  // 1. Personne connectée et administrateur actif
  const session = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!session) return reponse(401, { erreur: "connexion requise" }, origine);
  const { data: u, error: eu } = await base.auth.getUser(session);
  const email = u?.user?.email?.toLowerCase();
  if (eu || !email) return reponse(401, { erreur: "session invalide ou expirée : reconnectez-vous" }, origine);
  const { data: profil } = await base.from("profils").select("role, actif").eq("email", email).maybeSingle();
  if (!profil || !profil.actif || profil.role !== "administrateur") {
    return reponse(403, { erreur: "synchronisation réservée aux administrateurs" }, origine);
  }

  // 2. Demande
  let corps: unknown;
  try { corps = await req.json(); } catch { return reponse(400, { erreur: "demande illisible" }, origine); }
  const { erreur, demande } = controler(corps);
  if (erreur) return reponse(400, { erreur }, origine);
  const { data: connues, error: er } = await base.from("residences").select("dossier_pennylane").in("dossier_pennylane", demande.dossiers);
  if (er) return reponse(500, { erreur: "lecture des résidences impossible" }, origine);
  const trouves = new Set((connues ?? []).map((r: any) => r.dossier_pennylane));
  const inconnus = demande.dossiers.filter((d: string) => !trouves.has(d));
  if (inconnus.length) return reponse(400, { erreur: "dossiers inconnus : " + inconnus.join(", ") }, origine);

  // 3. Une seule synchronisation à la fois
  const depuis = new Date(Date.now() - 30 * 60 * 1000).toISOString();
  const { data: actives } = await base.from("synchronisations").select("id")
    .in("statut", ["demandée", "en cours"]).gte("demandee_le", depuis).limit(1);
  if (actives && actives.length) {
    return reponse(409, { erreur: `une synchronisation est déjà en cours (n° ${actives[0].id}) : attendez qu'elle se termine` }, origine);
  }

  // 4. Paramètres (synchronisation seulement) et demande
  if (demande.type === "test") {
    const { data: lt, error: et } = await base.from("synchronisations")
      .insert({ ...demande, demandee_par: email, statut: "demandée" }).select("id").single();
    if (et || !lt) return reponse(500, { erreur: "enregistrement de la demande impossible (migration 011 appliquée ?)" }, origine);
    return await lancer(base, jetonGithub, lt.id, origine);
  }
  const params = demande.dossiers.map((d: string) => ({ dossier: d, mois_debut: demande.mois_debut, mois_fin: demande.mois_fin,
    masquer_brouillard: demande.masquer_brouillard, modifie_par: email }));
  const { error: ep } = await base.from("parametres_import").upsert(params, { onConflict: "dossier" });
  if (ep) return reponse(500, { erreur: "enregistrement des paramètres impossible" }, origine);
  const { data: ligne, error: ei } = await base.from("synchronisations")
    .insert({ ...demande, demandee_par: email, statut: "demandée" }).select("id").single();
  if (ei || !ligne) return reponse(500, { erreur: "enregistrement de la demande impossible" }, origine);

  return await lancer(base, jetonGithub, ligne.id, origine);
});

// 5. Lancement immédiat du workflow GitHub
async function lancer(base: any, jetonGithub: string, id: number, origine: string | null): Promise<Response> {
  const gh = await fetch(`https://api.github.com/repos/${DEPOT}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${jetonGithub}`, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "zenitude-lancer-synchro" },
    body: JSON.stringify({ ref: "main", inputs: { demande: String(id) } }),
  });
  if (gh.status !== 204) {
    const motif = gh.status === 401 || gh.status === 403 ? "jeton GitHub refusé (expiré ou droits insuffisants)"
      : gh.status === 404 ? "workflow ou dépôt introuvable (nom du dépôt ou du fichier)" : `GitHub a répondu ${gh.status}`;
    await base.from("synchronisations").update({ statut: "échec", fin: new Date().toISOString(), message: "lancement refusé : " + motif }).eq("id", id);
    return reponse(502, { erreur: "lancement refusé : " + motif, id }, origine);
  }
  return reponse(200, { id, statut: "demandée" }, origine);
}
