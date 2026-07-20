// Configuration de l'application citoyenne SafeCity.
(function () {
  var override = localStorage.getItem("safecity_api");
  var host = location.hostname;
  var isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  // En développement : backend sur le port 5000.
  // En production : même origine (le reverse proxy Nginx route /api et /socket.io).
  var def = isLocal ? "http://localhost:5000" : location.origin;
  window.SAFECITY_CONFIG = { API_BASE: override || def };
})();
