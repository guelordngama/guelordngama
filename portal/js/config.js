// Configuration du portail agents SafeCity.
(function () {
  var override = localStorage.getItem("safecity_api");
  var host = location.hostname;
  var isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  // En production : même origine (reverse proxy Nginx : /api et /socket.io).
  var def = isLocal ? "http://localhost:5000" : location.origin;
  window.SAFECITY_CONFIG = { API_BASE: override || def };
})();
