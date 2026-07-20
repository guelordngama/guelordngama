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

    // Messagerie
    initChatFile();
    loadMessages();
    $("chat-send").addEventListener("click", sendMessage);
    $("chat-text").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });
    if (state.socket) state.socket.on("chat_message", addMessage);
  }

  async function loadMessages() {
    try { (await api("GET", "/api/messages?limit=40")).forEach(addMessage); } catch (e) {}
    state.chatReady = true;  // les messages suivants déclencheront un bip
  }
  let chatAttachment = null;
  function initChatFile() {
    const f = $("chat-file");
    if (!f) return;
    f.addEventListener("change", () => {
      const file = f.files[0];
      if (!file) { chatAttachment = null; return; }
      const reader = new FileReader();
      reader.onload = () => { chatAttachment = reader.result;
        document.querySelector(".chat-attach").classList.add("armed"); };
      reader.readAsDataURL(file);
    });
  }
  async function sendMessage() {
    const t = $("chat-text").value.trim();
    if (!t && !chatAttachment) return;
    const body = { text: t };
    if (chatAttachment) body.attachment = chatAttachment;
    $("chat-text").value = "";
    chatAttachment = null;
    $("chat-file").value = "";
    document.querySelector(".chat-attach").classList.remove("armed");
    try { await api("POST", "/api/messages", body); } catch (e) { alert("Échec : " + e.message); }
  }
  function addMessage(m) {
    const box = $("chat-messages");
    const mine = state.agent && m.sender_id === state.agent.id;
    if (!mine && state.chatReady) soundPing();  // bip pour un message entrant
    const div = document.createElement("div");
    div.className = "chat-msg " + (mine ? "mine" : "other");
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = (mine ? "Moi" : (m.sender_name || "Centre")) + " · " + (m.time || "");
    div.appendChild(who);
    if (m.text) { const txt = document.createElement("span"); txt.textContent = m.text; div.appendChild(txt); }
    if (m.attachment_url) {
      const img = document.createElement("img");
      img.src = API + m.attachment_url;
      img.addEventListener("click", () => window.open(API + m.attachment_url, "_blank"));
      div.appendChild(img);
    }
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
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
      state.socket.on("new_alert", (a) => {
        addAlert(a, true);
        soundAlarm();
        toast("🚨 Nouvelle alerte : " + (a.type || "").toUpperCase(), URGENCY[a.urgency]);
      });
      state.socket.on("alert_updated", onAlertUpdated);
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

  // Une alerte est mise à jour : si elle vient de m'être assignée, alarme forte.
  function onAlertUpdated(a) {
    const prev = state.alerts[a.id];
    const me = state.agent && state.agent.id;
    const mineNow = a.assigned_agent && a.assigned_agent.id === me;
    const mineBefore = prev && prev.assigned_agent && prev.assigned_agent.id === me;
    addAlert(a, false);
    if (mineNow && !mineBefore) {
      soundAssigned();
      toast("🚔 Une intervention vous est assignée : " + (a.type || "").toUpperCase(), "#f97316");
      if (state.selfPos) showRoute(state.selfPos, [a.lat, a.lng]);
      $("availability").value = "busy";
    }
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
      soundAck();  // accusé de réception : intervention acceptée
      toast("✅ Intervention acceptée", "#22c55e");
      // Trace l'itinéraire le plus rapide depuis ma position vers l'incident.
      if (state.selfPos) showRoute(state.selfPos, [updated.lat, updated.lng]);
    } catch (e) { alert("Échec : " + e.message); }
  }

  // ---- Itinéraire (OSRM + repli ligne droite) ----
  let routeLine = null;
  function showRoute(a, b) {
    if (!state.map || typeof L === "undefined") return;
    if (routeLine) { state.map.removeLayer(routeLine); routeLine = null; }
    const url = "https://router.project-osrm.org/route/v1/driving/" +
      a[1] + "," + a[0] + ";" + b[1] + "," + b[0] + "?overview=full&geometries=geojson";
    fetch(url).then((r) => r.json()).then((d) => {
      if (d.routes && d.routes.length) {
        const coords = d.routes[0].geometry.coordinates.map((c) => [c[1], c[0]]);
        routeLine = L.polyline(coords, { color: "#3d8bff", weight: 6, opacity: 0.85 }).addTo(state.map);
        const km = (d.routes[0].distance / 1000).toFixed(2), min = Math.round(d.routes[0].duration / 60);
        routeLine.bindPopup("🧭 " + km + " km · ~" + min + " min").openPopup();
        state.map.fitBounds(routeLine.getBounds(), { padding: [40, 40] });
      } else { straight(a, b); }
    }).catch(() => straight(a, b));
    function straight(a, b) {
      routeLine = L.polyline([a, b], { color: "#3d8bff", weight: 4, dashArray: "8,8" }).addTo(state.map);
      state.map.fitBounds(routeLine.getBounds(), { padding: [40, 40] });
    }
  }

  // ---- Sons de notification (Web Audio) ----
  function playTones(segments) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      let t = ctx.currentTime;
      segments.forEach(([freq, dur, vol]) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = freq; o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(vol, t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        o.start(t); o.stop(t + dur);
        t += dur + 0.04;
      });
    } catch (e) {}
  }
  // Alarme générale (nouvelle alerte diffusée à tous les agents).
  function soundAlarm() {
    playTones([[660, 0.16, 0.3], [990, 0.16, 0.3]]);
    if (navigator.vibrate) navigator.vibrate([200, 80, 200]);
  }
  // Alarme renforcée : une intervention vous est assignée.
  function soundAssigned() {
    playTones([[880, 0.14, 0.35], [1174, 0.14, 0.35], [1568, 0.22, 0.35]]);
    if (navigator.vibrate) navigator.vibrate([250, 100, 250, 100, 300]);
  }
  // Accusé de réception : l'agent accepte l'intervention.
  function soundAck() { playTones([[880, 0.10, 0.28], [1174, 0.14, 0.28]]); }
  // Bip discret : nouveau message du centre.
  function soundPing() { playTones([[1046, 0.08, 0.18]]); }

  // ---- Toast (notification visuelle) ----
  function toast(text, color) {
    const t = document.createElement("div");
    t.className = "portal-toast";
    t.style.borderColor = color || "#ef4444";
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 5000);
  }

  // ---- Géolocalisation de l'agent ----
  function startGeolocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.watchPosition(async (pos) => {
      const { latitude, longitude } = pos.coords;
      state.selfPos = [latitude, longitude];
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
