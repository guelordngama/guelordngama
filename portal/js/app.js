/* SafeCity — Portail des agents d'intervention.
 * Connexion, alertes temps réel, carte, prise en charge, envoi de position.
 */
(function () {
  "use strict";
  const API = window.SAFECITY_CONFIG.API_BASE;
  const URGENCY = { faible: "#22c55e", moyenne: "#eab308", haute: "#f97316", critique: "#ef4444" };
  const URG_LABEL = { faible: "Faible", moyenne: "Moyen", haute: "Élevé", critique: "Critique" };

  const state = { token: null, agent: null, alerts: {}, map: null, markers: {}, self: null, socket: null };
  const $ = (id) => document.getElementById(id);

  // ---- API helper ----
  async function api(method, path, body) {
    const res = await fetch(API + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(state.token ? { Authorization: "Bearer " + state.token } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      let msg = "HTTP " + res.status;
      try { msg = (await res.json()).error.message; } catch (e) {}
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  // ---- Connexion ----
  $("btn-login").addEventListener("click", login);
  $("password").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });

  async function login() {
    $("login-error").textContent = "";
    try {
      const data = await api("POST", "/api/auth/login",
        { email: $("email").value.trim(), password: $("password").value });
      state.token = data.token;
      state.agent = data.user;
      $("agent-name").textContent = data.user.name + " · " + data.user.role;
      $("login").classList.add("hidden");
      $("app").classList.remove("hidden");
      startApp();
    } catch (e) {
      $("login-error").textContent = "Échec : " + e.message;
    }
  }

  $("btn-logout").addEventListener("click", () => location.reload());

  // ---- Démarrage ----
  function startApp() {
    // Chaque brique est isolée : une carte ou un temps réel indisponible ne
    // doit pas empêcher l'affichage de la liste des alertes (via REST).
    try { initMap(); } catch (e) { console.warn("Carte indisponible :", e); }
    try { connectRealtime(); } catch (e) { console.warn("Temps réel indisponible :", e); }
    loadAlerts();
    try { startGeolocation(); } catch (e) {}

    $("availability").addEventListener("change", async (e) => {
      try { await api("POST", "/api/agents/me/status", { availability: e.target.value }); } catch (err) {}
    });
  }

  function initMap() {
    if (typeof L === "undefined") { throw new Error("Leaflet non chargé"); }
    state.map = L.map("map").setView([-4.325, 15.3222], 13);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { attribution: "© OpenStreetMap © CARTO", subdomains: "abcd", maxZoom: 19 }).addTo(state.map);
  }

  // ---- Temps réel ----
  function connectRealtime() {
    if (typeof io === "undefined") { throw new Error("Socket.IO non chargé"); }
    try {
      state.socket = io(API, { transports: ["polling"] });
      state.socket.on("connect", () => setConn(true));
      state.socket.on("disconnect", () => setConn(false));
      state.socket.on("new_alert", (a) => { addAlert(a, true); notify(a); });
      state.socket.on("alert_updated", (a) => addAlert(a, false));
    } catch (e) { console.warn(e); }
  }
  function setConn(ok) {
    const el = $("conn-status");
    el.classList.toggle("online", ok);
    el.classList.toggle("offline", !ok);
  }

  async function loadAlerts() {
    try {
      const list = await api("GET", "/api/alerts?status=active&page=1&page_size=50");
      (list.items || list).forEach((a) => addAlert(a, false));
    } catch (e) { console.warn(e); }
  }

  // ---- Rendu des alertes ----
  function addAlert(a, isNew) {
    if (a.status === "cloturee") { removeAlert(a.id); return; }
    state.alerts[a.id] = a;
    renderList();
    drawMarker(a);
  }
  function removeAlert(id) {
    delete state.alerts[id];
    if (state.markers[id]) { state.map.removeLayer(state.markers[id]); delete state.markers[id]; }
    renderList();
  }

  function renderList() {
    const list = $("alerts-list");
    const items = Object.values(state.alerts).sort((x, y) => (y.created_at || "").localeCompare(x.created_at || ""));
    $("alert-count").textContent = items.length;
    list.innerHTML = "";
    if (!items.length) {
      const e = document.createElement("div"); e.className = "empty";
      e.textContent = "Aucune alerte active."; list.appendChild(e); return;
    }
    const tpl = $("alert-card-tpl");
    items.forEach((a) => {
      const node = tpl.content.cloneNode(true);
      const card = node.querySelector(".alert-card");
      const color = URGENCY[a.urgency] || "#ef4444";
      card.style.borderLeftColor = color;
      node.querySelector(".alert-type").textContent = (a.type || "").toUpperCase();
      const badge = node.querySelector(".alert-badge");
      badge.textContent = URG_LABEL[a.urgency] || a.urgency;
      badge.style.background = color + "26"; badge.style.color = color;
      node.querySelector(".alert-meta").innerHTML =
        "👤 " + (a.reporter_name || "Anonyme") + " · 📞 " + (a.reporter_phone || "—") + "<br>" +
        "📍 " + (a.neighborhood || "—") + " · 🕒 " + (a.time || "—") + "<br>" +
        "🌐 " + a.lat.toFixed(5) + ", " + a.lng.toFixed(5) +
        (a.distance_m != null ? " · 📏 " + Math.round(a.distance_m) + " m" : "");
      const accepted = a.assigned_agent && state.agent && a.assigned_agent.id === state.agent.id;
      if (accepted) card.classList.add("accepted");
      const bAccept = node.querySelector(".btn-accept");
      bAccept.textContent = accepted ? "✅ Prise en charge" : "✅ Accepter";
      bAccept.disabled = accepted;
      bAccept.addEventListener("click", () => accept(a.id));
      node.querySelector(".btn-locate").addEventListener("click", () => {
        if (state.map) state.map.setView([a.lat, a.lng], 16);
        if (state.markers[a.id]) state.markers[a.id].openPopup();
      });
      list.appendChild(node);
    });
  }

  function drawMarker(a) {
    if (!state.map || typeof L === "undefined") return;
    if (state.markers[a.id]) state.map.removeLayer(state.markers[a.id]);
    const color = URGENCY[a.urgency] || "#ef4444";
    const icon = L.divIcon({ className: "",
      html: '<div style="width:16px;height:16px;border-radius:50%;background:' + color +
            ';border:3px solid #0b1220;box-shadow:0 0 0 2px ' + color + ',0 0 12px ' + color + '"></div>',
      iconSize: [16, 16], iconAnchor: [8, 8] });
    const m = L.marker([a.lat, a.lng], { icon }).addTo(state.map);
    m.bindPopup("<b>" + (a.type || "").toUpperCase() + "</b><br>" +
      (a.reporter_name || "Anonyme") + "<br>" + (a.neighborhood || ""));
    state.markers[a.id] = m;
  }

  async function accept(id) {
    try {
      const updated = await api("POST", "/api/alerts/" + id + "/accept");
      addAlert(updated, false);
      $("availability").value = "busy";
    } catch (e) { alert("Échec : " + e.message); }
  }

  // ---- Notification sonore + visuelle ----
  function notify(a) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [660, 990].forEach((f, i) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = f; o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.001, ctx.currentTime + i * 0.18);
        g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + i * 0.18 + 0.02);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.16);
        o.start(ctx.currentTime + i * 0.18); o.stop(ctx.currentTime + i * 0.18 + 0.18);
      });
    } catch (e) {}
    if (navigator.vibrate) navigator.vibrate([200, 80, 200]);
  }

  // ---- Géolocalisation de l'agent ----
  function startGeolocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.watchPosition(async (pos) => {
      const { latitude, longitude } = pos.coords;
      try { await api("POST", "/api/agents/me/location", { lat: latitude, lng: longitude }); } catch (e) {}
      if (!state.map || typeof L === "undefined") return;
      if (!state.self) {
        state.self = L.marker([latitude, longitude], {
          icon: L.divIcon({ className: "", html: '<div style="font-size:22px">🚓</div>', iconSize: [24, 24], iconAnchor: [12, 12] }),
        }).addTo(state.map).bindPopup("Ma position");
      } else {
        state.self.setLatLng([latitude, longitude]);
      }
    }, () => {}, { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 });
  }
})();
