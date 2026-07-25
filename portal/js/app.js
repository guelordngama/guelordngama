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

  // Thème clair / sombre (préférence mémorisée).
  (function initTheme() {
    const KEY = "safecity_theme";
    const root = document.documentElement;
    apply(localStorage.getItem(KEY) || "dark");
    function apply(mode) {
      root.setAttribute("data-theme", mode);
      const btn = document.getElementById("theme-toggle");
      if (btn) btn.textContent = mode === "light" ? "☀️" : "🌙";
    }
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      localStorage.setItem(KEY, next); apply(next);
    });
  })();

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
  function setLoading(btn, on) {
    btn.disabled = on;
    const sp = btn.querySelector(".spinner");
    if (sp) sp.hidden = !on;
  }
  function loginError(msg, ok) {
    const el = $("login-error");
    el.textContent = msg || "";
    el.style.color = ok ? "var(--green)" : "";
  }

  // Afficher / masquer les mots de passe (délégation).
  document.addEventListener("click", (e) => {
    const eye = e.target.closest(".pw-eye");
    if (!eye) return;
    const inp = $(eye.dataset.target); if (!inp) return;
    const reveal = inp.type === "password";
    inp.type = reveal ? "text" : "password";
    eye.textContent = reveal ? "🙈" : "👁️";
  });

  $("btn-login").addEventListener("click", login);
  $("password").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });

  async function login() {
    loginError("");
    unlockAudio();  // le clic « Se connecter » débloque le son (autoplay)
    try {
      if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();  // notifications système (arrière-plan)
      }
    } catch (e) {}
    const btn = $("btn-login");
    setLoading(btn, true);
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
      loginError("Échec : " + e.message);
    } finally {
      setLoading(btn, false);
    }
  }

  // ---- Mot de passe oublié (par e-mail) ----
  $("go-forgot").addEventListener("click", (e) => {
    e.preventDefault();
    $("forgot-email").value = $("email").value.trim();
    $("login-form").hidden = true;
    $("forgot-form").hidden = false;
    loginError("");
  });
  $("forgot-back").addEventListener("click", (e) => {
    e.preventDefault();
    $("forgot-form").hidden = true;
    $("login-form").hidden = false;
    loginError("");
  });
  $("btn-forgot").addEventListener("click", async () => {
    const email = $("forgot-email").value.trim();
    if (!email || !email.includes("@")) { loginError("Entrez un e-mail valide."); return; }
    const btn = $("btn-forgot");
    setLoading(btn, true); loginError("");
    try {
      const data = await api("POST", "/api/auth/forgot-password", { email });
      loginError(data.message || "Si un compte existe, un e-mail a été envoyé.", true);
    } catch (e) {
      loginError("Échec : " + e.message);
    } finally {
      setLoading(btn, false);
    }
  });

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

    // Historique des interventions
    $("btn-history").addEventListener("click", openHistory);
    $("history-close").addEventListener("click", () => $("history-modal").classList.add("hidden"));
    $("history-modal").addEventListener("click", (e) => {
      if (e.target.id === "history-modal") $("history-modal").classList.add("hidden");
    });

    // Messagerie
    initChatFile();
    initChatVoice();
    loadMessages();
    $("chat-send").addEventListener("click", sendMessage);
    $("chat-text").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });
    if (state.socket) state.socket.on("chat_message", addMessage);
  }

  async function loadMessages() {
    state.lastChatDay = null;
    $("chat-messages").innerHTML = "";
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
  // ---- Message vocal (MediaRecorder) ----
  let chatVoice = null;         // data URL de l'enregistrement prêt à envoyer
  let chatVoiceDur = 0;         // durée (s) de l'enregistrement prêt à envoyer
  let voiceRecorder = null;
  let voiceChunks = [];
  let voiceTimer = null;
  let voiceStream = null;
  let voiceStarted = 0;

  function initChatVoice() {
    const mic = $("chat-mic");
    if (!mic) return;
    if (!navigator.mediaDevices || typeof MediaRecorder === "undefined") {
      mic.style.display = "none";  // navigateur sans capture audio
      return;
    }
    mic.addEventListener("click", toggleVoice);
    const cancel = $("chat-voice-cancel");
    if (cancel) cancel.addEventListener("click", clearVoice);
  }

  async function toggleVoice() {
    if (voiceRecorder && voiceRecorder.state === "recording") {
      voiceRecorder.stop();
      return;
    }
    clearVoice();
    try {
      voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      alert("Micro indisponible ou permission refusée.");
      return;
    }
    voiceChunks = [];
    voiceRecorder = new MediaRecorder(voiceStream);
    voiceRecorder.ondataavailable = (ev) => { if (ev.data.size) voiceChunks.push(ev.data); };
    voiceRecorder.onstop = () => {
      chatVoiceDur = Math.round((Date.now() - voiceStarted) / 1000);
      const blob = new Blob(voiceChunks, { type: "audio/webm" });
      const reader = new FileReader();
      reader.onload = () => {
        chatVoice = reader.result;
        const audio = $("chat-voice-audio");
        if (audio) audio.src = chatVoice;
        $("chat-voice-preview").hidden = false;
      };
      reader.readAsDataURL(blob);
      stopVoiceStream();
      $("chat-mic").classList.remove("recording");
      $("chat-rec").hidden = true;
      clearInterval(voiceTimer);
    };
    voiceRecorder.start();
    $("chat-mic").classList.add("recording");
    $("chat-rec").hidden = false;
    voiceStarted = Date.now();
    $("chat-rec-time").textContent = "0:00";
    voiceTimer = setInterval(() => {
      const s = Math.floor((Date.now() - voiceStarted) / 1000);
      $("chat-rec-time").textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
      if (s >= 120) voiceRecorder.stop();  // limite de sécurité : 2 min
    }, 250);
  }

  function fmtDur(s) {
    s = Math.max(0, Math.round(s || 0));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  function stopVoiceStream() {
    if (voiceStream) { voiceStream.getTracks().forEach((t) => t.stop()); voiceStream = null; }
  }

  function clearVoice() {
    chatVoice = null;
    chatVoiceDur = 0;
    voiceChunks = [];
    const p = $("chat-voice-preview");
    if (p) p.hidden = true;
    const a = $("chat-voice-audio");
    if (a) a.removeAttribute("src");
  }

  async function sendMessage() {
    const t = $("chat-text").value.trim();
    if (!t && !chatAttachment && !chatVoice) return;
    const body = { text: t };
    if (chatAttachment) body.attachment = chatAttachment;
    if (chatVoice) { body.voice = chatVoice; if (chatVoiceDur) body.voice_duration = chatVoiceDur; }
    $("chat-text").value = "";
    chatAttachment = null;
    $("chat-file").value = "";
    document.querySelector(".chat-attach").classList.remove("armed");
    clearVoice();
    try { await api("POST", "/api/messages", body); } catch (e) { alert("Échec : " + e.message); }
  }
  // Séparateur de date façon WhatsApp : Aujourd'hui / Hier / jour de la
  // semaine (moins de 7 j) / date complète (« 24 juillet 2026 »).
  const JOURS_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
  const MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                   "août", "septembre", "octobre", "novembre", "décembre"];

  function msgDay(m) {
    const raw = m.created_at || "";
    if (!raw) return null;
    const d = new Date(raw);
    if (isNaN(d.getTime())) return null;
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function dayLabel(day) {
    const today = new Date();
    const t0 = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const diff = Math.round((t0 - day) / 86400000);
    if (diff === 0) return "Aujourd'hui";
    if (diff === 1) return "Hier";
    if (diff > 1 && diff < 7) return JOURS_FR[day.getDay()].replace(/^./, c => c.toUpperCase());
    return day.getDate() + " " + MOIS_FR[day.getMonth()] + " " + day.getFullYear();
  }

  function maybeAddDateDivider(box, m) {
    const day = msgDay(m);
    if (!day) return;
    const key = day.getTime();
    if (state.lastChatDay === key) return;
    state.lastChatDay = key;
    const sep = document.createElement("div");
    sep.className = "chat-date";
    sep.textContent = dayLabel(day);
    box.appendChild(sep);
  }

  function addMessage(m) {
    const box = $("chat-messages");
    const mine = state.agent && m.sender_id === state.agent.id;
    if (!mine && state.chatReady) {
      soundPing();  // bip pour un message entrant
      notify("💬 Nouveau message — SafeCity",
             (m.sender_name || "Centre") + " : " + (m.text || "pièce jointe"));
    }
    maybeAddDateDivider(box, m);
    const div = document.createElement("div");
    div.className = "chat-msg " + (mine ? "mine" : "other");
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = (mine ? "Moi" : (m.sender_name || "Centre")) + " · " + (m.time || "");
    div.appendChild(who);
    if (m.text) { const txt = document.createElement("span"); txt.textContent = m.text; div.appendChild(txt); }
    if (m.voice_url) {
      const cap = document.createElement("span");
      cap.className = "chat-voice-cap";
      cap.textContent = "🎤 Message vocal" + (m.voice_duration ? " · " + fmtDur(m.voice_duration) : "");
      div.appendChild(cap);
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.className = "chat-voice";
      audio.src = API + m.voice_url;
      // Repli : si la durée n'a pas été fournie, l'afficher dès que connue.
      if (!m.voice_duration) {
        audio.addEventListener("loadedmetadata", () => {
          const d = audio.duration;
          if (isFinite(d) && d > 0) cap.textContent = "🎤 Message vocal · " + fmtDur(d);
        });
      }
      div.appendChild(audio);
    }
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
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      { attribution: "© OpenStreetMap © CARTO", subdomains: "abcd", maxZoom: 19 }).addTo(state.map);
  }

  // ---- Temps réel ----
  function connectRealtime() {
    if (typeof io === "undefined") { throw new Error("Socket.IO non chargé"); }
    try {
      state.socket = io(API, { transports: ["polling", "websocket"] });
      state.socket.on("connect", () => setConn(true));
      state.socket.on("disconnect", () => setConn(false));
      state.socket.on("new_alert", (a) => {
        addAlert(a, true);
        soundAlarm();
        toast("🚨 Nouvelle alerte : " + (a.type || "").toUpperCase(), URGENCY[a.urgency]);
        notify("🚨 Nouvelle alerte — SafeCity",
               (a.type || "Alerte").toUpperCase() + " · " + (a.neighborhood || ""));
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
      // Bouton « Terminer l'intervention » : visible seulement si l'alerte
      // m'est assignée.
      const bComplete = node.querySelector(".btn-complete");
      bComplete.hidden = !accepted;
      bComplete.addEventListener("click", () => complete(a.id));
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

  async function complete(id) {
    if (!confirm("Terminer cette intervention ?")) return;
    try {
      await api("POST", "/api/alerts/" + id + "/complete");
      removeAlert(id);                    // l'alerte clôturée quitte la liste
      if (typeof clearRoute === "function") clearRoute();
      if (routeLine && state.map) { state.map.removeLayer(routeLine); routeLine = null; }
      $("availability").value = "available";
      soundAck();
      toast("🏁 Intervention terminée", "#22c55e");
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
  // Un SEUL contexte audio, débloqué à la première interaction utilisateur
  // (les navigateurs bloquent le son tant qu'il n'y a pas eu de geste).
  let audioCtx = null;
  function unlockAudio() {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
    } catch (e) {}
  }
  ["click", "keydown", "touchstart"].forEach((ev) =>
    document.addEventListener(ev, unlockAudio, { passive: true }));

  function playTones(segments) {
    try {
      unlockAudio();
      const ctx = audioCtx;
      if (!ctx) return;
      if (ctx.state === "suspended") ctx.resume();
      let t = ctx.currentTime + 0.02;
      segments.forEach(([freq, dur, vol]) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = freq; o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(vol, t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        o.start(t); o.stop(t + dur + 0.02);
        t += dur + 0.04;
      });
    } catch (e) {}
  }

  // Notification système (utile quand l'onglet est en arrière-plan).
  function notify(title, body) {
    try {
      if (!("Notification" in window) || Notification.permission !== "granted") return;
      if (!document.hidden) return;  // déjà visible : le son + toast suffisent
      const n = new Notification(title, { body: body, tag: "safecity", renotify: true });
      setTimeout(() => n.close(), 6000);
    } catch (e) {}
  }

  // Alarme générale (nouvelle alerte diffusée à tous les agents).
  function soundAlarm() {
    playTones([[660, 0.16, 0.3], [990, 0.16, 0.3], [660, 0.16, 0.3]]);
    if (navigator.vibrate) navigator.vibrate([200, 80, 200]);
  }
  // Alarme renforcée : une intervention vous est assignée.
  function soundAssigned() {
    playTones([[880, 0.14, 0.35], [1174, 0.14, 0.35], [1568, 0.22, 0.35]]);
    if (navigator.vibrate) navigator.vibrate([250, 100, 250, 100, 300]);
  }
  // Accusé de réception : l'agent accepte l'intervention.
  function soundAck() { playTones([[880, 0.10, 0.28], [1174, 0.14, 0.28]]); }
  // Bip de message (double ton, clairement audible) + vibration courte.
  function soundPing() {
    playTones([[1046, 0.09, 0.24], [1319, 0.12, 0.24]]);
    if (navigator.vibrate) navigator.vibrate(120);
  }

  // ---- Historique des interventions de l'agent ----
  async function openHistory() {
    try {
      const d = await api("GET", "/api/agents/me/interventions");
      $("history-summary").textContent =
        `${d.total} intervention(s) · ${d.resolved} résolue(s)` +
        (d.avg_response_min != null ? ` · réponse moy. ${d.avg_response_min} min` : "") +
        ` · ${(d.distance_m / 1000).toFixed(2)} km`;
      const list = $("history-list");
      list.innerHTML = "";
      if (!d.items.length) {
        list.innerHTML = '<div class="empty">Aucune intervention pour le moment.</div>';
      }
      d.items.forEach((a) => {
        const color = URGENCY[a.urgency] || "#ef4444";
        const div = document.createElement("div");
        div.className = "history-item";
        div.style.borderLeftColor = color;
        const date = (a.created_at || "").replace("T", " ").slice(0, 16);
        div.innerHTML =
          "<b>" + (a.type || "").toUpperCase() + "</b> " +
          '<span style="color:' + color + '">' + (URG_LABEL[a.urgency] || "") + "</span><br>" +
          '<span class="muted">' + date + " · " + (a.neighborhood || "—") +
          " · " + (a.status === "cloturee" ? "✅ Résolue" : a.status) + "</span>";
        list.appendChild(div);
      });
      $("history-modal").classList.remove("hidden");
    } catch (e) { alert("Échec : " + e.message); }
  }

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
