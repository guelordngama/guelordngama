/* SafeCity — coquille du tableau de bord citoyen.
 * Gère la barre latérale, le basculement connexion/tableau de bord, le titre de
 * page, la fiche utilisateur, « Mes alertes » et les réglages — SANS modifier la
 * logique métier de app.js (auth, GPS, envoi, suivi). On se greffe uniquement sur
 * les classes .active que app.js pose déjà sur les écrans.
 */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const tr = (k, fb) => (window.t ? window.t(k) : null) || fb;

  // view (barre latérale) -> id de section + titre/sous-titre
  const VIEWS = {
    alert:    { id: "screen-alert",    title: () => tr("nav.home", "Accueil"),       sub: () => tr("app.tagline", "Alerte d'urgence citoyenne") },
    details:  { id: "screen-details",  title: () => tr("details.title", "Détails de l'incident"), sub: () => "", nav: "alert" },
    confirm:  { id: "screen-confirm",  title: () => tr("confirm.title", "Alerte envoyée"),        sub: () => "", nav: "alert" },
    mine:     { id: "screen-mine",     title: () => tr("nav.myAlerts", "Mes alertes"), sub: () => tr("mine.sub", "Vos signalements") },
    track:    { id: "screen-track",    title: () => tr("track.title", "Suivre une alerte"),        sub: () => "" },
    about:    { id: "screen-about",    title: () => tr("nav.about", "À propos"),       sub: () => "" },
    settings: { id: "screen-settings", title: () => tr("nav.settings", "Paramètres"),  sub: () => "" },
  };

  const navLinks = () => document.querySelectorAll(".side-link[data-view]");

  function setTitle(view) {
    const v = VIEWS[view];
    if (!v) return;
    $("page-title").textContent = v.title();
    const sub = $("page-sub");
    sub.textContent = v.sub();
    sub.style.display = v.sub() ? "" : "none";
  }

  function highlight(navName) {
    navLinks().forEach((b) => b.classList.toggle("active", b.dataset.view === navName));
  }

  // Active un écran (barre latérale) : désactive TOUTES les sections .screen du
  // contenu, active la cible, met à jour titre + surbrillance.
  function goView(view) {
    const v = VIEWS[view];
    if (!v) return;
    document.querySelectorAll(".content .screen").forEach((s) => s.classList.remove("active"));
    const el = document.getElementById(v.id);
    if (el) el.classList.add("active");
    highlight(v.nav || view);
    setTitle(view);
    if (view === "mine") renderMine();
    if (view === "settings") syncSettings();
    window.scrollTo(0, 0);
  }

  // Clics de navigation (barre latérale + barre mobile).
  document.addEventListener("click", (e) => {
    const link = e.target.closest(".side-link[data-view]");
    if (!link) return;
    e.preventDefault();
    goView(link.dataset.view);
  });

  // --------------------------------------------------------------------- //
  // Basculement connexion <-> tableau de bord (observe l'écran d'auth).
  // On surveille les classes que app.js pose sur ses écrans.
  // --------------------------------------------------------------------- //
  const APP_SCREENS = ["screen-auth", "screen-alert", "screen-details", "screen-confirm", "screen-track"];
  function syncFromAppScreens() {
    const authed = !$("screen-auth").classList.contains("active");
    document.body.classList.toggle("authed", authed);
    if (!authed) return;
    // Reflète la surbrillance de la barre selon l'écran interne actif.
    if ($("screen-details").classList.contains("active") ||
        $("screen-confirm").classList.contains("active") ||
        $("screen-alert").classList.contains("active")) {
      // Ne pas écraser une vue personnalisée (mine/about/settings) déjà active.
      const custom = $("screen-mine").classList.contains("active") ||
                     $("screen-about").classList.contains("active") ||
                     $("screen-settings").classList.contains("active");
      if (!custom) {
        highlight("alert");
        if ($("screen-details").classList.contains("active")) setTitle("details");
        else if ($("screen-confirm").classList.contains("active")) setTitle("confirm");
        else setTitle("alert");
      }
    }
    refreshUser();
  }
  const obs = new MutationObserver(syncFromAppScreens);
  APP_SCREENS.forEach((id) => {
    const el = $(id);
    if (el) obs.observe(el, { attributes: true, attributeFilter: ["class"] });
  });
  // Capture la confirmation d'une alerte envoyée (pour « Mes alertes »).
  const confirmObs = new MutationObserver(() => {
    if ($("screen-confirm").classList.contains("active")) captureSentAlert();
  });
  confirmObs.observe($("screen-confirm"), { attributes: true, attributeFilter: ["class"] });

  // --------------------------------------------------------------------- //
  // Fiche utilisateur (initiales avatar + profil)
  // --------------------------------------------------------------------- //
  function getAuth() {
    try { return JSON.parse(localStorage.getItem("safecity_auth")) || null; } catch (e) { return null; }
  }
  function initials(name) {
    if (!name) return "?";
    const letters = name.replace(/[^A-Za-zÀ-ÿ ]/g, "").trim().split(/\s+/).filter(Boolean);
    if (!letters.length) return "👤";
    const a = letters[0][0] || "";
    const b = letters[1] ? letters[1][0] : "";
    return (a + b).toUpperCase() || "👤";
  }
  function refreshUser() {
    const a = getAuth();
    const name = (a && a.user && (a.user.name || a.user.phone)) || "";
    const ini = initials(name);
    if ($("user-initials")) $("user-initials").textContent = ini || "?";
    if ($("profile-initials")) $("profile-initials").textContent = ini || "?";
    if ($("profile-name")) $("profile-name").textContent = (a && a.user && a.user.name) || "Citoyen";
    if ($("profile-phone")) $("profile-phone").textContent = (a && a.user && a.user.phone) || "—";
  }

  // --------------------------------------------------------------------- //
  // « Mes alertes » (mémorisées localement sur cet appareil)
  // --------------------------------------------------------------------- //
  const MY_KEY = "safecity_myalerts";
  function getMine() {
    try { return JSON.parse(localStorage.getItem(MY_KEY)) || []; } catch (e) { return []; }
  }
  function setMine(a) { try { localStorage.setItem(MY_KEY, JSON.stringify(a.slice(0, 30))); } catch (e) {} }

  function captureSentAlert() {
    const box = $("cf-ref-box");
    if (!box || box.hidden) return;                 // pas de référence (hors-ligne)
    const ref = ($("cf-ref").textContent || "").trim();
    if (!ref || ref === "—") return;
    const list = getMine();
    if (list.some((x) => x.ref === ref)) return;    // déjà enregistrée
    list.unshift({
      ref: ref,
      type: ($("cf-type").textContent || "").trim(),
      neighborhood: ($("cf-neighborhood").textContent || "").trim(),
      at: Date.now(),
    });
    setMine(list);
    renderLastAlert();
  }

  function alertCardHTML(a) {
    const when = new Date(a.at).toLocaleString("fr-FR",
      { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    return '<div class="card"><div class="la-row">' +
      '<span class="la-ref">#' + esc(a.ref) + '</span>' +
      '<span class="pill blue">' + esc(a.type || "Alerte") + '</span></div>' +
      '<div class="la-line"><span class="ic">📍</span>' + esc(a.neighborhood || "—") + '</div>' +
      '<div class="la-line"><span class="ic">🕒</span>' + when + '</div>' +
      '<button class="link-btn" data-track="' + esc(a.ref) + '">' +
        tr("home.seeDetail", "Voir le détail") + ' →</button></div>';
  }
  function esc(s) { return (s || "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  function renderMine() {
    const host = $("mine-list");
    const list = getMine();
    if (!list.length) {
      host.innerHTML = '<div class="card"><p class="la-empty">' +
        tr("mine.empty", "Vous n'avez pas encore envoyé d'alerte depuis cet appareil.") + '</p></div>';
      return;
    }
    host.innerHTML = list.map(alertCardHTML).join("");
  }
  function renderLastAlert() {
    const host = $("last-alert-body");
    if (!host) return;
    const list = getMine();
    if (!list.length) {
      host.innerHTML = '<p class="la-empty">' + tr("home.noAlert", "Aucune alerte envoyée pour l'instant.") + '</p>';
      return;
    }
    host.innerHTML = alertCardHTML(list[0]).replace('<div class="card">', '<div>').replace(/<\/div>$/, "</div>");
  }

  // Clic sur « Voir le détail » -> ouvre le suivi et lance la recherche.
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-track]");
    if (!b) return;
    e.preventDefault();
    goView("track");
    const inp = $("track-input");
    if (inp) { inp.value = b.dataset.track; $("btn-track-go").click(); }
  });

  // --------------------------------------------------------------------- //
  // Réglages (langue / thème) + déconnexion secondaire
  // --------------------------------------------------------------------- //
  function syncSettings() {
    refreshUser();
    const theme = document.documentElement.getAttribute("data-theme") || "light";
    if ($("set-theme")) $("set-theme").value = theme;
    const lang = (window.SafeCityI18n && window.SafeCityI18n.current()) || "fr";
    if ($("set-lang")) $("set-lang").value = lang;
  }
  if ($("set-theme")) $("set-theme").addEventListener("change", (e) => {
    const mode = e.target.value;
    localStorage.setItem("safecity_theme", mode);
    document.documentElement.setAttribute("data-theme", mode);
    const btn = $("theme-toggle");
    if (btn) btn.textContent = mode === "light" ? "☀️" : "🌙";
  });
  if ($("set-lang")) $("set-lang").addEventListener("change", (e) => {
    if (window.SafeCityI18n) window.SafeCityI18n.setLang(e.target.value);
  });
  // Bouton « Se déconnecter » de l'écran Paramètres : réutilise la logique existante.
  if ($("btn-logout-2")) $("btn-logout-2").addEventListener("click", () => {
    const lo = $("btn-logout"); if (lo) lo.click();
  });

  // --------------------------------------------------------------------- //
  // Démarrage
  // --------------------------------------------------------------------- //
  function boot() {
    refreshUser();
    renderLastAlert();
    syncFromAppScreens();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  // Filet de sécurité : re-synchronise après le démarrage de app.js.
  setTimeout(boot, 300);
})();
