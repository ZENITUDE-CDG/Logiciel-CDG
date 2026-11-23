// Fonctions communes aux écrans de connexion, d'espace et d'administration (lot 12).
// Aucune règle de droits ici : la base décide ce que chacun voit et modifie.
(function () {
  "use strict";

  var cfg = window.ZENITUDE_CONFIG || {};
  var configOk = cfg.supabaseUrl && cfg.supabaseCle && cfg.supabaseCle.indexOf("COLLER_") !== 0;

  var ROLES = { administrateur: "Administrateur", collaborateur: "Collaborateur", lecture: "Lecture seule" };

  function el(tag, attrs, enfants) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "texte") n.textContent = attrs[k];
      else if (k.indexOf("on") === 0) n.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) n.setAttribute(k, attrs[k]);
    });
    (enfants || []).forEach(function (e) { if (e) n.appendChild(typeof e === "string" ? document.createTextNode(e) : e); });
    return n;
  }

  function message(zone, texte, type) {
    zone.textContent = texte || "";
    zone.className = "message" + (texte ? " " + (type || "erreur") : "");
  }

  // Messages d'erreur compréhensibles, sans jargon technique.
  function traduire(err) {
    var m = (err && (err.message || err.error_description)) || String(err || "");
    if (/Invalid login credentials/i.test(m)) return "Adresse ou mot de passe incorrect.";
    if (/Email not confirmed/i.test(m)) return "Ce compte n’est pas encore confirmé dans Supabase.";
    if (/row-level security|permission denied/i.test(m)) return "Action refusée : vos droits ne le permettent pas.";
    if (/duplicate key|already exists/i.test(m)) return "Cet élément existe déjà.";
    if (/violates check constraint/i.test(m)) return "Valeur refusée : les codes s’écrivent en majuscules, chiffres, tirets (exemple : RES-001).";
    if (/violates foreign key/i.test(m)) return "Élément introuvable : rechargez la page.";
    if (/Password should be at least/i.test(m)) return "Le mot de passe est trop court.";
    if (/Failed to fetch|NetworkError/i.test(m)) return "Connexion à la base impossible. Vérifiez votre réseau.";
    return "Erreur : " + m;
  }

  function erreurConfig() {
    document.addEventListener("DOMContentLoaded", function () {
      document.body.innerHTML = "";
      document.body.appendChild(el("main", {}, [el("section", { class: "bloc" }, [
        el("h1", { texte: "Configuration incomplète" }),
        el("p", { texte: "La clé publique Supabase n’est pas renseignée dans le fichier app/config.js du dépôt." })
      ])]));
    });
  }

  if (!configOk || !window.supabase) {
    window.Zen = { pret: false };
    erreurConfig();
    return;
  }

  // Nom de session fixe : la garde du tableau de bord (app/garde.js) le lit, quel que soit le serveur.
  var client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseCle,
    { auth: { storageKey: "zenitude-session", persistSession: true, autoRefreshToken: true } });

  async function session() {
    var r = await client.auth.getSession();
    return r.data && r.data.session;
  }

  // Exige une personne connectée et un profil actif. Renvoie { session, profil }.
  async function exigerConnexion() {
    var s = await session();
    if (!s) { location.replace("connexion.html"); return null; }
    var email = (s.user.email || "").toLowerCase();
    var r = await client.from("profils").select("email, nom, role, actif").eq("email", email).maybeSingle();
    return { session: s, email: email, profil: r.error ? null : r.data };
  }

  async function deconnexion() {
    await client.auth.signOut();
    location.replace("connexion.html");
  }

  // Barre du haut commune aux pages connectées.
  function barre(page, profil) {
    var liens = [el("a", { href: "index.html", texte: "Tableau de bord" }),
                 el("a", { href: "espace.html", texte: "Mon espace", "aria-current": page === "espace" ? "page" : null })];
    if (profil && profil.role === "administrateur") {
      liens.push(el("a", { href: "administration.html", texte: "Administration",
                           "aria-current": page === "administration" ? "page" : null }));
    }
    liens.push(el("button", { type: "button", texte: "Se déconnecter", onclick: deconnexion }));
    var logo = el("img", { src: "interface/logo_zenitude.png", alt: "Zenitude" });
    logo.addEventListener("error", function () { logo.remove(); });
    return el("header", { class: "barre" }, [logo, el("span", { class: "nom-app", texte: "Pilotage" }),
                                             el("nav", { "aria-label": "Navigation" }, liens)]);
  }

  window.Zen = { pret: true, client: client, ROLES: ROLES, el: el, message: message, traduire: traduire,
                 session: session, exigerConnexion: exigerConnexion, deconnexion: deconnexion, barre: barre };
})();
