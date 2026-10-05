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
  function escapeAttr(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function avatarUrl(u) {
    if (!u || !u.avatar_url) return null;
    const API = (window.SAFECITY_CONFIG && window.SAFECITY_CONFIG.API_BASE) || "";
    return u.avatar_url.startsWith("http") ? u.avatar_url : API + u.avatar_url;
  }
  // Remplit un avatar (initiales OU photo) : utilisé pour la pastille du
  // haut (petite) et la fiche profil (grande) — même logique, tailles différentes.
  function fillAvatar(el, name, photo) {
    if (!el) return;
    el.innerHTML = photo
      ? '<img src="' + escapeAttr(photo) + '" alt="" loading="lazy">'
      : escapeAttr(initials(name) || "?");
  }
  function refreshUser() {
    const a = getAuth();
    const name = (a && a.user && (a.user.name || a.user.phone)) || "";
    const photo = avatarUrl(a && a.user);
    fillAvatar($("user-initials"), name, photo);
    fillAvatar($("profile-initials"), name, photo);
    if ($("profile-name")) $("profile-name").textContent = (a && a.user && a.user.name) || "Citoyen";
    if ($("profile-phone")) $("profile-phone").textContent = (a && a.user && a.user.phone) || "—";
    if ($("avatar-remove-link")) $("avatar-remove-link").hidden = !photo;
  }

  // --------------------------------------------------------------------- //
  // Photo de profil : changer / retirer
  // --------------------------------------------------------------------- //
  function shellToast(msg, ok) {
    const t = document.createElement("div");
    t.className = "pending-badge";
    t.style.background = ok === false ? "#dc2626" : "#22c55e";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }
  // Message d'erreur exploitable : le serveur renvoie { error: { message } } —
  // on l'affiche tel quel (ex. « Type de fichier non autorisé ») au lieu d'un
  // message générique qui ne dit pas ce qui a réellement échoué.
  async function errorMessage(res, fallback) {
    try {
      const body = await res.json();
      return (body && body.error && body.error.message) || fallback;
    } catch (e) {
      return fallback;
    }
  }
  // Jeton expiré (session de plusieurs heures) : un toast d'erreur seul
  // laisse l'utilisateur bloqué sur un tableau de bord qui a l'air connecté
  // mais où plus aucune action protégée ne fonctionnera. On déconnecte et on
  // revient à l'écran de connexion avec un message clair, plutôt que de le
  // laisser deviner qu'il doit se reconnecter.
  function handleExpiredSession() {
    localStorage.removeItem("safecity_auth");
    try { sessionStorage.setItem("safecity_session_expired", "1"); } catch (e) {}
    location.reload();
  }
  async function uploadAvatar(dataUrl) {
    const a = getAuth();
    if (!a || !a.token) return;
    const API = (window.SAFECITY_CONFIG && window.SAFECITY_CONFIG.API_BASE) || "";
    const wrap = $("profile-avatar-wrap");
    if (wrap) wrap.classList.add("avatar-edit-busy");
    try {
      const res = await fetch(API + "/api/auth/me/avatar", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + a.token },
        body: JSON.stringify({ photo: dataUrl }),
      });
      if (res.status === 401) return handleExpiredSession();
      if (!res.ok) {
        throw new Error(await errorMessage(res, "Échec de l'envoi (" + res.status + ")."));
      }
      const user = await res.json();
      a.user = user;
      localStorage.setItem("safecity_auth", JSON.stringify(a));
      refreshUser();
      shellToast(tr("settings.photoUpdated", "Photo de profil mise à jour."));
    } catch (e) {
      shellToast(e.message || tr("settings.photoError", "Impossible de changer la photo. Réessayez."), false);
    } finally {
      if (wrap) wrap.classList.remove("avatar-edit-busy");
    }
  }
  async function removeAvatar() {
    const a = getAuth();
    if (!a || !a.token) return;
    const API = (window.SAFECITY_CONFIG && window.SAFECITY_CONFIG.API_BASE) || "";
    try {
      const res = await fetch(API + "/api/auth/me/avatar", {
        method: "DELETE",
        headers: { "Authorization": "Bearer " + a.token },
      });
      if (res.status === 401) return handleExpiredSession();
      if (!res.ok) {
        throw new Error(await errorMessage(res, "Échec de la suppression (" + res.status + ")."));
      }
      const user = await res.json();
      a.user = user;
      localStorage.setItem("safecity_auth", JSON.stringify(a));
      refreshUser();
      shellToast(tr("settings.photoRemoved", "Photo de profil retirée."));
    } catch (e) {
      shellToast(e.message || tr("settings.photoError", "Impossible de changer la photo. Réessayez."), false);
    }
  }
  // Badge « appareil photo » : toujours ouvrir le sélecteur de fichier (changer).
  if ($("profile-avatar-btn")) $("profile-avatar-btn").addEventListener("click", () => {
    const inp = $("avatar-input");
    if (inp) inp.click();
  });
  // La photo elle-même : si une photo est déjà définie, l'agrandir (façon
  // WhatsApp) ; sinon, comme il n'y a rien à voir, ouvrir directement le
  // sélecteur de fichier (première photo).
  if ($("profile-initials")) $("profile-initials").addEventListener("click", () => {
    const a = getAuth();
    const url = avatarUrl(a && a.user);
    if (url) openLightbox(url);
    else { const inp = $("avatar-input"); if (inp) inp.click(); }
  });
  if ($("avatar-input")) $("avatar-input").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const url = URL.createObjectURL(file);
    const cropped = await openCropper(url);
    URL.revokeObjectURL(url);
    if (cropped) uploadAvatar(cropped);
  });
  if ($("avatar-remove-link")) $("avatar-remove-link").addEventListener("click", (e) => {
    e.preventDefault();
    removeAvatar();
  });

  // --------------------------------------------------------------------- //
  // Rognage de la photo avant envoi : cadre circulaire, glisser pour
  // déplacer, pincer / molette / curseur pour zoomer. Le résultat exporté
  // est un carré (déjà affiché en rond partout via object-fit: cover).
  // --------------------------------------------------------------------- //
  const CROP_OUTPUT = 480;     // même taille que l'ancienne compression
  const CROP_VIEWPORT = 260;   // doit correspondre à la taille CSS du cadre
  const CROP_MAX_ZOOM = 3;     // facteur au-delà du cadrage « couvrant »
  let cropState = null;        // { natW, natH, baseScale, scale, x, y }
  let cropResolve = null;

  function clampBox(st, boxW, boxH) {
    const dispW = st.natW * st.scale, dispH = st.natH * st.scale;
    const minX = Math.min(0, boxW - dispW), minY = Math.min(0, boxH - dispH);
    st.x = Math.max(minX, Math.min(0, st.x));
    st.y = Math.max(minY, Math.min(0, st.y));
  }
  function renderCrop() {
    const img = $("crop-img");
    if (!img || !cropState) return;
    img.style.width = (cropState.natW * cropState.scale) + "px";
    img.style.height = (cropState.natH * cropState.scale) + "px";
    img.style.transform = "translate(" + cropState.x + "px," + cropState.y + "px)";
  }
  function zoomCropTo(newScale, anchorX, anchorY) {
    const st = cropState;
    newScale = Math.max(st.baseScale, Math.min(st.baseScale * CROP_MAX_ZOOM, newScale));
    const imgX = (anchorX - st.x) / st.scale, imgY = (anchorY - st.y) / st.scale;
    st.x = anchorX - imgX * newScale;
    st.y = anchorY - imgY * newScale;
    st.scale = newScale;
    clampBox(st, CROP_VIEWPORT, CROP_VIEWPORT);
    renderCrop();
    const slider = $("crop-zoom");
    if (slider) slider.value = String(Math.round((st.scale / st.baseScale) * 100));
  }
  function openCropper(url) {
    return new Promise((resolve) => {
      const modal = $("crop-modal");
      const img = $("crop-img");
      if (!modal || !img) return resolve(null);
      img.onload = () => {
        const natW = img.naturalWidth, natH = img.naturalHeight;
        const baseScale = Math.max(CROP_VIEWPORT / natW, CROP_VIEWPORT / natH);
        cropState = {
          natW, natH, baseScale, scale: baseScale,
          x: (CROP_VIEWPORT - natW * baseScale) / 2,
          y: (CROP_VIEWPORT - natH * baseScale) / 2,
        };
        if ($("crop-zoom")) $("crop-zoom").value = "100";
        renderCrop();
        modal.hidden = false;
        cropResolve = resolve;
      };
      img.src = url;
    });
  }
  function closeCropper(result) {
    const modal = $("crop-modal");
    if (modal) modal.hidden = true;
    cropState = null;
    if (cropResolve) { const r = cropResolve; cropResolve = null; r(result); }
  }
  function confirmCrop() {
    const img = $("crop-img"), st = cropState;
    if (!img || !st) return closeCropper(null);
    const sx = -st.x / st.scale, sy = -st.y / st.scale, sSize = CROP_VIEWPORT / st.scale;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = CROP_OUTPUT; canvas.height = CROP_OUTPUT;
      canvas.getContext("2d").drawImage(img, sx, sy, sSize, sSize, 0, 0, CROP_OUTPUT, CROP_OUTPUT);
      closeCropper(canvas.toDataURL("image/jpeg", 0.85));
    } catch (e) { closeCropper(null); }
  }
  // Un seul doigt/souris : déplace. Deux doigts : pince pour zoomer (molette
  // sur ordinateur). Même mécanique que la visionneuse ci-dessous.
  function wirePanZoom(el, getState, onPan, onZoom) {
    const pointers = new Map();
    let lastDist = null;
    const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
    const mid = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
    el.addEventListener("pointerdown", (e) => {
      el.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      lastDist = null;
    });
    el.addEventListener("pointermove", (e) => {
      if (!getState() || !pointers.has(e.pointerId)) return;
      const prev = pointers.get(e.pointerId);
      const cur = { x: e.clientX, y: e.clientY };
      pointers.set(e.pointerId, cur);
      if (pointers.size === 1) {
        onPan(cur.x - prev.x, cur.y - prev.y);
      } else if (pointers.size >= 2) {
        const pts = Array.from(pointers.values());
        const d = dist(pts[0], pts[1]);
        const m = mid(pts[0], pts[1]);
        const rect = el.getBoundingClientRect();
        if (lastDist != null) onZoom(d / lastDist, m.x - rect.left, m.y - rect.top);
        lastDist = d;
      }
    });
    const release = (e) => {
      pointers.delete(e.pointerId);
      if (pointers.size < 2) lastDist = null;
    };
    el.addEventListener("pointerup", release);
    el.addEventListener("pointercancel", release);
    el.addEventListener("wheel", (e) => {
      if (!getState()) return;
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      onZoom(e.deltaY < 0 ? 1.08 : 1 / 1.08, e.clientX - rect.left, e.clientY - rect.top);
    }, { passive: false });
  }
  if ($("crop-viewport")) {
    wirePanZoom($("crop-viewport"),
      () => cropState,
      (dx, dy) => { cropState.x += dx; cropState.y += dy; clampBox(cropState, CROP_VIEWPORT, CROP_VIEWPORT); renderCrop(); },
      (factor, x, y) => zoomCropTo(cropState.scale * factor, x, y));
  }
  if ($("crop-zoom")) $("crop-zoom").addEventListener("input", (e) => {
    if (!cropState) return;
    const pct = parseInt(e.target.value, 10) || 100;
    zoomCropTo(cropState.baseScale * (pct / 100), CROP_VIEWPORT / 2, CROP_VIEWPORT / 2);
  });
  if ($("crop-confirm")) $("crop-confirm").addEventListener("click", confirmCrop);
  if ($("crop-cancel")) $("crop-cancel").addEventListener("click", () => closeCropper(null));
  if ($("crop-cancel-x")) $("crop-cancel-x").addEventListener("click", () => closeCropper(null));

  // --------------------------------------------------------------------- //
  // Visionneuse plein écran de la photo de profil (façon WhatsApp) : toute
  // la photo visible au départ, pince/molette pour zoomer, glisser pour
  // déplacer une fois zoomé, double-clic/double-tap pour basculer vite.
  // --------------------------------------------------------------------- //
  let viewState = null; // { natW, natH, fitScale, scale, x, y, vw, vh }

  function renderView() {
    const img = $("avatar-view-img");
    if (!img || !viewState) return;
    img.style.width = (viewState.natW * viewState.scale) + "px";
    img.style.height = (viewState.natH * viewState.scale) + "px";
    img.style.transform = "translate(" + viewState.x + "px," + viewState.y + "px)";
  }
  function clampView() {
    const st = viewState;
    const dispW = st.natW * st.scale, dispH = st.natH * st.scale;
    st.x = dispW <= st.vw ? (st.vw - dispW) / 2 : Math.max(st.vw - dispW, Math.min(0, st.x));
    st.y = dispH <= st.vh ? (st.vh - dispH) / 2 : Math.max(st.vh - dispH, Math.min(0, st.y));
  }
  function zoomViewTo(newScale, anchorX, anchorY) {
    const st = viewState;
    newScale = Math.max(st.fitScale, Math.min(st.fitScale * 4, newScale));
    const imgX = (anchorX - st.x) / st.scale, imgY = (anchorY - st.y) / st.scale;
    st.x = anchorX - imgX * newScale;
    st.y = anchorY - imgY * newScale;
    st.scale = newScale;
    clampView();
    renderView();
  }
  function openLightbox(url) {
    const modal = $("avatar-view-modal"), img = $("avatar-view-img"), stage = $("avatar-view-stage");
    if (!modal || !img || !stage) return;
    // Rendre la modale visible AVANT de mesurer la scène : tant qu'elle est
    // `hidden`, sa taille est 0×0 (display: none), ce qui donnerait une photo
    // invisible (échelle calculée à partir d'une zone de taille nulle).
    modal.hidden = false;
    img.onload = () => {
      const rect = stage.getBoundingClientRect();
      const natW = img.naturalWidth, natH = img.naturalHeight;
      const fitScale = Math.min(rect.width / natW, rect.height / natH);
      viewState = {
        natW, natH, fitScale, scale: fitScale, vw: rect.width, vh: rect.height,
        x: (rect.width - natW * fitScale) / 2,
        y: (rect.height - natH * fitScale) / 2,
      };
      renderView();
    };
    img.src = url;
  }
  function closeLightbox() {
    const modal = $("avatar-view-modal");
    if (modal) modal.hidden = true;
    viewState = null;
  }
  if ($("avatar-view-stage")) {
    const stage = $("avatar-view-stage");
    wirePanZoom(stage,
      () => viewState,
      (dx, dy) => { viewState.x += dx; viewState.y += dy; clampView(); renderView(); },
      (factor, x, y) => zoomViewTo(viewState.scale * factor, x, y));
    stage.addEventListener("dblclick", (e) => {
      if (!viewState) return;
      const rect = stage.getBoundingClientRect();
      const target = viewState.scale > viewState.fitScale * 1.2 ? viewState.fitScale : viewState.fitScale * 2.5;
      zoomViewTo(target, e.clientX - rect.left, e.clientY - rect.top);
    });
  }
  if ($("avatar-view-close")) $("avatar-view-close").addEventListener("click", closeLightbox);
  if ($("avatar-view-modal")) $("avatar-view-modal").addEventListener("click", (e) => {
    if (e.target.id === "avatar-view-modal") closeLightbox();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if ($("avatar-view-modal") && !$("avatar-view-modal").hidden) closeLightbox();
    else if ($("crop-modal") && !$("crop-modal").hidden) closeCropper(null);
  });

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
