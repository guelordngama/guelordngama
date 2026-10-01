/* SafeCity — coquille du portail agents (barre latérale / onglets mobiles).
 * N'altère pas la logique de app.js : fait défiler vers les cartes (missions,
 * carte, messagerie), relaie « Historique » et affiche les initiales de l'agent.
 */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const links = () => document.querySelectorAll(".side-link[data-go], .side-link[data-proxy]");

  function highlight(target) {
    links().forEach((b) => b.classList.toggle("active", b.dataset.go === target));
  }

  document.addEventListener("click", (e) => {
    const proxy = e.target.closest(".side-link[data-proxy]");
    if (proxy) { const t = $(proxy.dataset.proxy); if (t) t.click(); return; }
    const link = e.target.closest(".side-link[data-go]");
    if (!link) return;
    const card = $(link.dataset.go);
    if (!card) return;
    highlight(link.dataset.go);
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash");
  });

  // Initiales/photo de l'agent (#agent-initials) : rendues directement par
  // app.js (renderProfile), qui sait aussi afficher la photo de profil —
  // plus besoin d'observer #agent-name ici (ça écrasait la photo par du texte).

  // La carte Leaflet doit recalculer sa taille quand l'app s'affiche / se redimensionne.
  function fixMap() {
    const m = document.querySelector("#map.leaflet-container");
    if (m && window.dispatchEvent) window.dispatchEvent(new Event("resize"));
  }
  const app = $("app");
  if (app) new MutationObserver(() => setTimeout(fixMap, 150))
    .observe(app, { attributes: true, attributeFilter: ["class"] });
})();
