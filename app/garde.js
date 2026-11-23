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
  // Lot 14 : plus de bouton flottant « Mon espace » ; le compte s'ouvre en cliquant sur l'adresse e-mail,
  // en bas à gauche du menu.
})();
