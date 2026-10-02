/* SafeCity — Portail des agents d'intervention.
 * Connexion, alertes temps réel, carte, prise en charge, envoi de position.
 */
(function () {
  "use strict";
  const API = window.SAFECITY_CONFIG.API_BASE;
  // Icônes de repère Leaflet servies localement (pas de CDN).
  if (typeof L !== "undefined") L.Icon.Default.imagePath = "vendor/leaflet/images/";
  const URGENCY = { faible: "#22c55e", moyenne: "#eab308", haute: "#f97316", critique: "#ef4444" };
  const URG_LABEL = { faible: "Faible", moyenne: "Moyen", haute: "Élevé", critique: "Critique" };

  const state = { token: null, agent: null, alerts: {}, map: null, markers: {}, self: null, socket: null };
  const $ = (id) => document.getElementById(id);

  function escapeAttr(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function initials(name) {
    const letters = (name || "").replace(/[^A-Za-zÀ-ÿ ]/g, "").trim().split(/\s+/).filter(Boolean);
    if (!letters.length) return "?";
    return ((letters[0][0] || "") + (letters[1] ? letters[1][0] : "")).toUpperCase() || "?";
  }
  function avatarUrl(u) {
    if (!u || !u.avatar_url) return null;
    return u.avatar_url.startsWith("http") ? u.avatar_url : API + u.avatar_url;
  }
  function fillAvatar(el, name, photo) {
    if (!el) return;
    el.innerHTML = photo
      ? '<img src="' + escapeAttr(photo) + '" alt="" loading="lazy">'
      : escapeAttr(initials(name));
  }
  // Réduit la photo avant envoi (voir web/js/shell.js pour le même mécanisme
  // côté app citoyenne : évite les gros fichiers de téléphone, plus rapide).
  function compressImage(file, maxSize, quality) {
    return new Promise((resolve) => {
      const fallback = () => {
        const r = new FileReader();
        r.onload = () => resolve(r.result);
        r.onerror = () => resolve(null);
        r.readAsDataURL(file);
      };
      try {
        const img = new Image();
        const reader = new FileReader();
        reader.onload = () => {
          img.onload = () => {
            try {
              let { width, height } = img;
              if (width > maxSize || height > maxSize) {
                if (width > height) { height = Math.round((height * maxSize) / width); width = maxSize; }
                else { width = Math.round((width * maxSize) / height); height = maxSize; }
              }
              const canvas = document.createElement("canvas");
              canvas.width = width; canvas.height = height;
              canvas.getContext("2d").drawImage(img, 0, 0, width, height);
              resolve(canvas.toDataURL("image/jpeg", quality));
            } catch (e) { fallback(); }
          };
          img.onerror = fallback;
          img.src = reader.result;
        };
        reader.onerror = fallback;
        reader.readAsDataURL(file);
      } catch (e) { fallback(); }
    });
  }
  const ROLE_LABELS = { admin: "Administrateur", supervisor: "Superviseur",
                        operator: "Opérateur", agent: "Agent" };
  function renderProfile() {
    const u = state.agent;
    const name = (u && u.name) || "—";
    const photo = avatarUrl(u);
    if ($("agent-name")) $("agent-name").textContent = u ? name + " · " + (ROLE_LABELS[u.role] || u.role) : "—";
    fillAvatar($("agent-initials"), name, photo);
    fillAvatar($("profile-initials"), name, photo);
    if ($("profile-name")) $("profile-name").textContent = name;
    if ($("profile-role")) $("profile-role").textContent = u ? (ROLE_LABELS[u.role] || u.role) : "—";
    if ($("avatar-remove-link")) $("avatar-remove-link").hidden = !photo;
  }

  // Thème clair / sombre (préférence mémorisée).
  (function initTheme() {
    const KEY = "safecity_theme";
    const root = document.documentElement;
    apply(localStorage.getItem(KEY) || "light");
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
      renderProfile();
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
    loadAgentPositions();
    setInterval(loadAgentPositions, 30000);   // filet de sécurité si le temps réel coupe

    $("availability").addEventListener("change", async (e) => {
      try { await api("POST", "/api/agents/me/status", { availability: e.target.value }); } catch (err) {}
    });

    // Historique des interventions
    $("btn-history").addEventListener("click", openHistory);
    $("history-close").addEventListener("click", () => $("history-modal").classList.add("hidden"));
    $("history-modal").addEventListener("click", (e) => {
      if (e.target.id === "history-modal") $("history-modal").classList.add("hidden");
    });

    // Mon profil (photo)
    $("agent-avatar-btn").addEventListener("click", () => {
      renderProfile();
      $("profile-modal").classList.remove("hidden");
    });
    $("profile-close").addEventListener("click", () => $("profile-modal").classList.add("hidden"));
    $("profile-modal").addEventListener("click", (e) => {
      if (e.target.id === "profile-modal") $("profile-modal").classList.add("hidden");
    });
    $("profile-avatar-btn").addEventListener("click", () => $("avatar-input").click());
    $("avatar-input").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      const durl = await compressImage(file, 480, 0.85);
      if (!durl) { alert("Photo illisible, réessayez avec une autre image."); return; }
      const btn = $("profile-avatar-btn");
      btn.classList.add("avatar-edit-busy");
      try {
        state.agent = await api("POST", "/api/auth/me/avatar", { photo: durl });
        renderProfile();
      } catch (err) {
        alert("Impossible de changer la photo : " + err.message);
      } finally {
        btn.classList.remove("avatar-edit-busy");
      }
    });
    $("avatar-remove-link").addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        state.agent = await api("DELETE", "/api/auth/me/avatar");
        renderProfile();
      } catch (err) {
        alert("Impossible de retirer la photo : " + err.message);
      }
    });

    // Messagerie
    initChatFile();
    initChatVideo();
    initChatVoice();
    initChatInfo();
    loadMessages();
    $("chat-send").addEventListener("click", sendMessage);
    $("chat-text").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });
    if (state.socket) state.socket.on("chat_message", addMessage);
  }

  // Dernier point de lecture de la messagerie (persistant, par agent) : conservé
  // même après fermeture/relance, pour reprendre là où on s'était arrêté.
  function chatLastRead() {
    const id = state.agent && state.agent.id;
    const v = parseInt(localStorage.getItem("chat_last_read_" + id) || "0", 10);
    return isNaN(v) ? 0 : v;
  }
  function setChatLastRead(mid) {
    const id = state.agent && state.agent.id;
    if (!id || !mid) return;
    if (mid > chatLastRead()) localStorage.setItem("chat_last_read_" + id, String(mid));
  }
  function addChatDivider(box, label) {
    const el = document.createElement("div");
    el.className = "chat-divider-new";
    el.textContent = "──  " + label + "  ──";
    box.appendChild(el);
    return el;
  }

  async function loadMessages() {
    state.lastChatDay = null;
    const box = $("chat-messages");
    box.innerHTML = "";
    let msgs = [];
    try { msgs = await api("GET", "/api/messages?limit=40"); } catch (e) {}
    if (!Array.isArray(msgs)) msgs = [];

    // Reprise au dernier point de lecture : les messages postérieurs, venant
    // d'autres, sont « non lus » (séparateur + surlignage), et la vue se
    // positionne dessus au lieu de descendre tout en bas.
    const lastRead = chatLastRead();
    const meId = state.agent && state.agent.id;
    let dividerEl = null, dividerDone = false, maxId = lastRead;
    msgs.forEach((m) => {
      const isUnread = m.id && m.id > lastRead && m.sender_id !== meId;
      if (isUnread && !dividerDone) { dividerEl = addChatDivider(box, "Nouveaux messages"); dividerDone = true; }
      addMessage(m, { unread: isUnread, noScroll: true });
      if (m.id && m.id > maxId) maxId = m.id;
    });

    state.chatReady = true;  // les messages suivants déclencheront un bip
    // Positionnement : sur le séparateur si présent, sinon en bas.
    if (dividerEl) {
      const br = box.getBoundingClientRect(), er = dividerEl.getBoundingClientRect();
      box.scrollTop += (er.top - br.top) - 8;
    } else {
      box.scrollTop = box.scrollHeight;
    }
    // Consultation → on avance le point de lecture + accusé de lecture.
    setChatLastRead(maxId);
    markRead();              // j'ai ouvert la messagerie → accusé de lecture
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
  let chatVideo = null;
  function initChatVideo() {
    const f = $("chat-video");
    if (!f) return;
    f.addEventListener("change", () => {
      const file = f.files[0];
      if (!file) { chatVideo = null; return; }
      if (file.size > 20 * 1024 * 1024) {
        alert("Vidéo trop volumineuse (max 20 Mo). Filmez une courte séquence.");
        f.value = ""; return;
      }
      const reader = new FileReader();
      reader.onload = () => { chatVideo = reader.result;
        f.parentElement.classList.add("armed"); };
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
    if (!t && !chatAttachment && !chatVoice && !chatVideo) return;
    const body = { text: t };
    if (chatAttachment) body.attachment = chatAttachment;
    if (chatVideo) body.video = chatVideo;
    if (chatVoice) { body.voice = chatVoice; if (chatVoiceDur) body.voice_duration = chatVoiceDur; }
    $("chat-text").value = "";
    chatAttachment = null;
    chatVideo = null;
    $("chat-file").value = "";
    if ($("chat-video")) { $("chat-video").value = ""; $("chat-video").parentElement.classList.remove("armed"); }
    document.querySelectorAll(".chat-attach").forEach((el) => el.classList.remove("armed"));
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
    // Horodatage serveur en UTC sans suffixe : on le précise pour le navigateur.
    const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(raw) ? raw : raw + "Z");
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

  function addMessage(m, opts) {
    opts = opts || {};
    const box = $("chat-messages");
    const mine = state.agent && m.sender_id === state.agent.id;
    if (!mine && state.chatReady && !opts.noScroll) {
      soundPing();  // bip pour un message entrant
      notify("💬 Nouveau message — SafeCity",
             (m.sender_name || "Centre") + " : " + (m.text || "pièce jointe"));
    }
    maybeAddDateDivider(box, m);
    const div = document.createElement("div");
    div.className = "chat-msg " + (mine ? "mine" : "other") + (opts.unread ? " unread" : "");
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = (opts.unread && !mine ? "🔵 " : "")
      + (mine ? "Moi" : (m.sender_name || "Centre")) + " · " + (m.time || "");
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
    if (m.video_url) {
      const vid = document.createElement("video");
      vid.controls = true;
      vid.className = "chat-video-msg";
      vid.src = API + m.video_url;
      div.appendChild(vid);
    }
    // Accusé de lecture (✓ / ✓✓) sur MES messages uniquement.
    if (mine) {
      div.dataset.created = m.created_at || "";
      if (m.read) div.dataset.read = "1";
      const tick = document.createElement("span");
      tick.className = "chat-tick";
      div.appendChild(tick);
      updateTick(div);
    }
    box.appendChild(div);
    if (!opts.noScroll) {
      box.scrollTop = box.scrollHeight;
      if (!mine) markRead();          // j'ai « vu » un message reçu (en direct)
      if (m.id) setChatLastRead(m.id); // je consulte → avance le point de lecture
    }
  }

  // ---- Accusés de lecture ----
  function updateTick(div) {
    const tick = div.querySelector(".chat-tick");
    if (!tick) return;
    const created = div.dataset.created || "";
    const read = div.dataset.read === "1" || (created && created <= (state.readFrontier || ""));
    tick.textContent = read ? "✓✓" : "✓";
    tick.classList.toggle("read", !!read);
  }
  function refreshTicks() {
    document.querySelectorAll("#chat-messages .chat-msg.mine").forEach(updateTick);
  }
  let markReadTimer = null;
  function markRead() {
    clearTimeout(markReadTimer);
    markReadTimer = setTimeout(() => { api("POST", "/api/messages/read").catch(() => {}); }, 400);
  }

  function initMap() {
    if (typeof L === "undefined") { throw new Error("Leaflet non chargé"); }
    // Centre de Lubumbashi (jamais Kinshasa).
    state.map = L.map("map").setView([-11.6647, 27.4794], 13);
    // Tuiles servies par le proxy du serveur SafeCity (/tiles/…) : contourne le
    // blocage des CDN externes par le pare-feu.
    L.tileLayer(API + "/tiles/v2/{z}/{x}/{y}.png",
      { attribution: "© OpenStreetMap", maxZoom: 20, maxNativeZoom: 19 }).addTo(state.map);
    // Carte en temps réel (alertes, citoyens, agents, trajets, rue/quartier).
    if (window.LiveMap) {
      state.live = window.LiveMap(state.map, {
        selfId: state.agent && state.agent.id,
        onAccept: (id) => accept(id),
      });
    }
  }

  // ---- Temps réel ----
  function connectRealtime() {
    if (typeof io === "undefined") { throw new Error("Socket.IO non chargé"); }
    try {
      // Jeton obligatoire : sans lui, le serveur n'envoie aucune donnée.
      // (Fonction → le jeton courant est renvoyé à chaque reconnexion.)
      state.socket = io(API, { transports: ["polling", "websocket"],
                               auth: (cb) => cb({ token: state.token || "" }) });
      state.socket.on("connect", () => {
        setConn(true);
        if (state.agent) state.socket.emit("identify", { uid: state.agent.id });
      });
      state.socket.on("disconnect", () => setConn(false));
      state.socket.on("new_alert", (a) => {
        addAlert(a, true);
        soundAlarm();
        toast("🚨 Nouvelle alerte : " + (a.type || "").toUpperCase(), URGENCY[a.urgency]);
        notify("🚨 Nouvelle alerte — SafeCity",
               (a.type || "Alerte").toUpperCase() + " · " + (a.neighborhood || ""));
      });
      state.socket.on("alert_updated", onAlertUpdated);
      state.socket.on("agent_updated", (g) => {
        if (state.live && g && g.role === "agent") state.live.upsertAgent(pickAgent(g));
      });
      state.socket.on("agent_deleted", (d) => { if (state.live && d) state.live.removeAgent(d.id); });
      state.socket.on("messages_read", (d) => {
        if (state.agent && d.reader_id === state.agent.id) return;  // ma propre lecture
        if (d.seen_at && d.seen_at > (state.readFrontier || "")) state.readFrontier = d.seen_at;
        refreshTicks();
        if (state.infoOpen) loadParticipants();
      });
      state.socket.on("presence", () => { if (state.infoOpen) loadParticipants(); });
    } catch (e) { console.warn(e); }
  }

  // ---- Onglet « Infos » (participants) ----
  function initChatInfo() {
    const btn = $("chat-info-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      state.infoOpen = !state.infoOpen;
      const panel = $("chat-info");
      panel.hidden = !state.infoOpen;
      btn.classList.toggle("active", state.infoOpen);
      if (state.infoOpen) loadParticipants();
    });
  }
  async function loadParticipants() {
    let list = [];
    try { list = await api("GET", "/api/messages/participants"); } catch (e) { return; }
    const panel = $("chat-info");
    panel.innerHTML =
      '<div class="chat-info-legend">🟢 en ligne · ⚪ hors ligne · ✓✓ a vu le dernier message</div>';
    list.forEach((u) => {
      const row = document.createElement("div");
      row.className = "chat-info-row";
      const dot = u.online ? "🟢" : "⚪";
      const seen = u.read_latest ? "<span class='seen'>✓✓ a vu</span>" : "<span class='unseen'>… pas encore</span>";
      row.innerHTML = `<span>${dot} ${u.name} <em>(${u.role})</em></span> ${seen}`;
      panel.appendChild(row);
    });
  }
  function setConn(ok) {
    const el = $("conn-status");
    el.classList.toggle("online", ok);
    el.classList.toggle("offline", !ok);
  }

  async function loadAlerts() {
    // « active » (pas encore prises en charge) ET « assignee » (déjà en
    // cours) : sinon une mission assignée avant la connexion de l'agent
    // n'apparaissait qu'après le prochain événement temps réel.
    try {
      const [a, b] = await Promise.all([
        api("GET", "/api/alerts?status=active&page=1&page_size=50"),
        api("GET", "/api/alerts?status=assignee&page=1&page_size=50"),
      ]);
      (a.items || a).forEach((al) => addAlert(al, false));
      (b.items || b).forEach((al) => addAlert(al, false));
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
    syncMap();
    renderList();
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // ---- Fiche d'alerte (format du centre) ----
  const TYPE_NAMES = { vol: "Vol", braquage: "Braquage", incendie: "Incendie", accident: "Accident",
    violence: "Violence", agression: "Agression", autre: "Autre" };
  const STATUS_FICHE = { active: ["EN ATTENTE", "#ef4444"], assignee: ["EN COURS", "#f97316"],
    cloturee: ["TRAITÉ", "#16a34a"] };
  const STAGE_FICHE = {
    received: ["📨 Reçue", "#64748b"], assigned: ["👮 Assignée", "#3b82f6"],
    en_route: ["🚓 Agent en route", "#f97316"], on_site: ["📍 Sur place", "#8b5cf6"],
    resolved: ["✅ Résolue", "#16a34a"],
  };
  // « Avenue Kasai » -> ["Avenue", "Kasai"] ; inconnu -> ["Avenue / Rue", …]
  function streetParts(street) {
    const s = (street || "").trim(), low = s.toLowerCase();
    const kinds = [[["avenue ", "av. ", "av "], "Avenue"], [["rue "], "Rue"],
      [["boulevard ", "bd "], "Boulevard"], [["route "], "Route"], [["chaussée "], "Chaussée"]];
    for (const [prefixes, label] of kinds) {
      for (const p of prefixes) if (low.startsWith(p)) return [label, s.slice(p.length).trim() || s];
    }
    return ["Avenue / Rue", s];
  }
  function gpsSigned(lat, lng) {
    if (lat == null || lng == null) return "—";
    return Number(lat).toFixed(6) + ", " + Number(lng).toFixed(6);
  }
  // « 13:48 » si l'incident date d'aujourd'hui, sinon « 27/09 13:48 » — évite
  // toute ambiguïté pour une mission restée ouverte depuis un autre jour.
  function whenText(a) {
    const loc = a.created_local;
    if (!loc || loc.indexOf(" ") === -1) return a.time || "—";
    const [day, hm] = loc.split(" ");
    const n = new Date();
    const today = n.getFullYear() + "-" + String(n.getMonth() + 1).padStart(2, "0")
      + "-" + String(n.getDate()).padStart(2, "0");
    if (day === today) return hm || a.time || "—";
    const [, m, d] = day.split("-");
    return d + "/" + m + " " + hm;
  }
  function precisionText(a) {
    if (a.position_approx) return "⚠️ Approximative (GPS non obtenu)";
    if (a.position_manual) return "Placée à la main sur la carte";
    return a.gps_accuracy_m != null ? Math.round(a.gps_accuracy_m) + " m" : "Non communiquée";
  }
  function ficheRow(label, value) {
    return '<div class="fiche-row"><span>' + escapeHtml(label) + '</span><b>' + value + "</b></div>";
  }

  // Coordonnées GPS lisibles : « 11.66470°S, 27.47940°E ».
  function fmtCoords(lat, lng) {
    if (lat == null || lng == null) return "—";
    const ns = lat >= 0 ? "N" : "S", ew = lng >= 0 ? "E" : "O";
    return Math.abs(lat).toFixed(5) + "°" + ns + ", " + Math.abs(lng).toFixed(5) + "°" + ew;
  }

  // Affiche les médias joints à une alerte (photo cliquable, vocal, vidéo).
  function renderAlertMedia(box, a) {
    if (!box) return;
    box.innerHTML = "";
    const abs = (u) => (u && u.charAt(0) === "/" ? API + u : u);
    if (a.photo_url) {
      const link = document.createElement("a");
      link.href = abs(a.photo_url); link.target = "_blank"; link.rel = "noopener";
      const img = document.createElement("img");
      img.className = "alert-photo"; img.src = abs(a.photo_url);
      img.alt = "Photo du citoyen"; img.loading = "lazy";
      link.appendChild(img); box.appendChild(link);
    }
    if (a.audio_url) {
      const au = document.createElement("audio");
      au.controls = true; au.preload = "none"; au.src = abs(a.audio_url);
      box.appendChild(au);
    }
    if (a.video_url) {
      const vi = document.createElement("video");
      vi.controls = true; vi.preload = "metadata"; vi.src = abs(a.video_url);
      vi.className = "alert-video";
      box.appendChild(vi);
    }
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
      const dup = a.duplicate_count || 0;
      node.querySelector(".alert-type").textContent =
        (a.type || "").toUpperCase() + (dup > 0 ? "  🔁" + (dup + 1) : "");
      const badge = node.querySelector(".alert-badge");
      badge.textContent = URG_LABEL[a.urgency] || a.urgency;
      badge.style.background = color + "26"; badge.style.color = color;
      const dupLine = dup > 0
        ? "🔁 " + (dup + 1) + " signalements du même incident (regroupés)<br>"
        : "";
      const descLine = a.description
        ? "📝 " + escapeHtml(a.description) + "<br>"
        : "";
      const approxLine = a.position_approx
        ? '<span class="alert-approx">⚠️ Position approximative (GPS non obtenu) — '
          + 'rappeler le citoyen</span><br>'
        : "";
      const [stLabel, stValue] = streetParts(a.street);
      const st = STATUS_FICHE[a.status] || [(a.status || "—").toUpperCase(), "#64748b"];
      node.querySelector(".alert-type").textContent =
        (TYPE_NAMES[a.type] || (a.type || "").toUpperCase()).toUpperCase() +
        "  #" + (a.incident_number || a.reference || a.id) + (dup > 0 ? "  🔁" + (dup + 1) : "");
      node.querySelector(".alert-meta").innerHTML =
        dupLine + approxLine +
        '<div class="fiche">' +
        ficheRow("Type", escapeHtml(TYPE_NAMES[a.type] || a.type || "—")) +
        ficheRow("Citoyen", escapeHtml(a.reporter_name || "Anonyme") +
          (a.reporter_phone ? ' · <a href="tel:' + escapeHtml(a.reporter_phone) + '">📞 ' +
            escapeHtml(a.reporter_phone) + "</a>" : "")) +
        ficheRow("Commune", escapeHtml(a.commune || "—")) +
        ficheRow(stLabel, escapeHtml(stValue || "—")) +
        ficheRow("Quartier", escapeHtml(a.neighborhood || "—")) +
        ficheRow("Ville", escapeHtml(a.city || "—")) +
        '<div class="fiche-sep"></div>' +
        ficheRow("GPS", '<span class="alert-coords" title="Cliquer pour copier la position">' +
          gpsSigned(a.lat, a.lng) + "</span>") +
        ficheRow("Précision", escapeHtml(precisionText(a))) +
        ficheRow("Heure", escapeHtml(whenText(a)) +
          (a.distance_m != null ? " · 📏 " + Math.round(a.distance_m) + " m" : "")) +
        ficheRow("Statut", '<span class="fiche-status" style="color:' + st[1] + "\">" + st[0] + "</span>") +
        ficheRow("Progression", (() => {
          const sg = STAGE_FICHE[a.stage] || STAGE_FICHE.received;
          return '<span class="fiche-status" style="color:' + sg[1] + '">' + sg[0] + "</span>";
        })()) +
        (a.assigned_agent ? ficheRow("Agent", "👮 " + escapeHtml(a.assigned_agent.name) + " → Intervention #" +
          escapeHtml(a.incident_number || a.reference || a.id)) : "") +
        "</div>" + descLine;
      // Position GPS exacte cliquable → copie (pour la transmettre par radio/tel).
      const coordsEl = node.querySelector(".alert-coords");
      if (coordsEl) {
        coordsEl.addEventListener("click", () => {
          const v = gpsSigned(a.lat, a.lng);
          const ok = () => { const o = coordsEl.textContent; coordsEl.textContent = "✓ copié"; setTimeout(() => { coordsEl.textContent = o; }, 1400); };
          if (navigator.clipboard) navigator.clipboard.writeText(v).then(ok, ok); else ok();
        });
      }

      // Médias joints par le citoyen (photo / vocal / vidéo) : les agents sur le
      // terrain doivent aussi les voir, pas seulement l'opérateur.
      renderAlertMedia(node.querySelector(".alert-media"), a);
      const accepted = a.assigned_agent && state.agent && a.assigned_agent.id === state.agent.id;
      if (accepted) card.classList.add("accepted");
      const bAccept = node.querySelector(".btn-accept");
      bAccept.textContent = accepted ? "✅ Prise en charge" : "✅ Accepter";
      bAccept.disabled = accepted;
      bAccept.addEventListener("click", () => accept(a.id));
      // Itinéraire Google Maps vers le citoyen (téléphone de l'agent).
      const gm = node.querySelector(".btn-gmaps");
      if (gm) gm.href = "https://www.google.com/maps/dir/?api=1&destination=" + a.lat + "," + a.lng;
      node.querySelector(".btn-locate").addEventListener("click", () => {
        if (state.live) state.live.focusAlert(a.id);
        else if (state.map) state.map.setView([a.lat, a.lng], 16);
      });
      // Bouton « Terminer l'intervention » : visible seulement si l'alerte
      // m'est assignée.
      const bComplete = node.querySelector(".btn-complete");
      bComplete.hidden = !accepted;
      bComplete.addEventListener("click", () => complete(a.id));
      // Bouton « Arrivé sur place » : visible une fois la mission acceptée, tant
      // que l'étape « Sur place » n'est pas déjà atteinte.
      const bArrived = node.querySelector(".btn-arrived");
      const onSiteOrLater = a.stage === "on_site" || a.stage === "resolved";
      bArrived.hidden = !accepted || onSiteOrLater;
      bArrived.addEventListener("click", () => arrived(a.id));
      list.appendChild(node);
    });
  }

  function drawMarker() { syncMap(); }
  function syncMap() {
    if (state.live) state.live.setAlerts(Object.values(state.alerts));
    updateMyRoute(false);
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

  async function arrived(id) {
    try {
      const updated = await api("POST", "/api/alerts/" + id + "/arrived");
      addAlert(updated, false);
      toast("📍 Arrivée signalée", "#8b5cf6");
    } catch (e) { alert("Échec : " + e.message); }
  }

  async function complete(id) {
    if (!confirm("Terminer cette intervention ?")) return;
    try {
      await api("POST", "/api/alerts/" + id + "/complete");
      removeAlert(id);                    // l'alerte clôturée quitte la liste
      updateMyRoute(false);               // plus de mission : trajet retiré
      $("availability").value = "available";
      soundAck();
      toast("🏁 Intervention terminée", "#22c55e");
    } catch (e) { alert("Échec : " + e.message); }
  }

  // ---- Mon itinéraire vers ma mission (calculé par le serveur SafeCity) ----
  // Le serveur interroge OSRM (avec cache) : pas d'appel externe depuis le
  // téléphone. Recalcul seulement si je me suis déplacé d'environ 100 m.
  let routeKey = null, routeBusy = false;
  function myMission() {
    const me = state.agent && state.agent.id;
    return Object.values(state.alerts).find((a) =>
      a.status === "assignee" && a.assigned_agent && a.assigned_agent.id === me) || null;
  }
  async function updateMyRoute(force) {
    if (!state.live) return;
    const a = myMission();
    if (!a) { if (routeKey) { routeKey = null; state.live.setMyRoute(null, null); } return; }
    if (!state.selfPos) return;
    const key = a.id + ":" + state.selfPos[0].toFixed(3) + "," + state.selfPos[1].toFixed(3);
    if ((!force && key === routeKey) || routeBusy) return;
    routeBusy = true;
    try {
      const r = await api("GET", "/api/geo/route?from=" + state.selfPos[0] + "," + state.selfPos[1] +
                                 "&to=" + a.lat + "," + a.lng);
      routeKey = key;
      state.live.setMyRoute(a.id, r);
      if (force) state.live.focusAlert(a.id);
    } catch (e) { /* réseau : on retentera au prochain déplacement */ }
    finally { routeBusy = false; }
  }
  function showRoute() { updateMyRoute(true); }

  // ---- Positions des collègues (carte) ----
  function pickAgent(g) {
    return { id: g.id, name: g.name, role: g.role, availability: g.availability, lat: g.lat,
             lng: g.lng, last_seen: g.last_seen, current_alert_id: g.current_alert_id };
  }
  async function loadAgentPositions() {
    if (!state.live) return;
    try {
      const list = await api("GET", "/api/agents/positions");
      state.live.setAgents((list || []).map(pickAgent));
    } catch (e) { /* ancien serveur ou réseau : la carte reste utilisable */ }
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
        const date = a.created_local || (a.created_at || "").replace("T", " ").slice(0, 16);
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
      if (state.live) { state.live.setSelf(state.selfPos, pos.coords.accuracy); updateMyRoute(false); return; }
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
