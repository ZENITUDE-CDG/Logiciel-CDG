// Garde du tableau de bord (lot 12) : renvoie vers l'écran de connexion si personne n'est connecté.
// Ce n'est qu'un confort d'affichage : la vraie protection des données est dans la base.
// Les tests du site ouvrent la page en local (file://) : la garde ne s'applique pas dans ce cas.
(function () {
  if (location.protocol === "file:") return;
  var connecte = false;
  try {
    var s = JSON.parse(localStorage.getItem("zenitude-session") || "null");
    connecte = !!(s && s.access_token && (s.refresh_token || s.expires_at * 1000 > Date.now()));
  } catch (e) { connecte = false; }
  if (!connecte) { location.replace("connexion.html"); return; }
  document.addEventListener("DOMContentLoaded", function () {
    var a = document.createElement("a");
    a.href = "espace.html";
    a.textContent = "Mon espace";
    a.setAttribute("style", "position:fixed;right:16px;bottom:16px;z-index:9999;background:#0F506C;color:#fff;" +
      "font:600 13px Montserrat,Arial,sans-serif;padding:9px 14px;border-radius:6px;text-decoration:none;" +
      "box-shadow:0 2px 8px rgba(15,80,108,.35)");
    document.body.appendChild(a);
  });
})();
