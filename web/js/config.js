// Configuration de l'application citoyenne SafeCity.
// Modifiez API_BASE pour pointer vers votre serveur backend.
window.SAFECITY_CONFIG = {
  // URL du backend Flask (sans slash final).
  API_BASE: (localStorage.getItem("safecity_api") || "http://localhost:5000"),
};
