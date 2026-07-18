/* SafeCity — logique de l'application citoyenne.
 * Géolocalisation, sélection du danger, photo/audio, envoi et confirmation.
 */
(function () {
  "use strict";

  const API = window.SAFECITY_CONFIG.API_BASE;

  // État courant de l'alerte en cours de composition.
  const state = {
    lat: null,
    lng: null,
    neighborhood: null,
    address: null,
    type: null,
    photo: null, // data URL
    audio: null, // data URL
  };

  // --- Raccourcis DOM ---
  const $ = (id) => document.getElementById(id);
  const screens = {
    alert: $("screen-alert"),
    details: $("screen-details"),
    confirm: $("screen-confirm"),
  };

  function show(name) {
    Object.values(screens).forEach((s) => s.classList.remove("active"));
    screens[name].classList.add("active");
  }

  // ---------------------------------------------------------------------- //
  // Connexion temps réel (indicateur d'état)
  // ---------------------------------------------------------------------- //
  let socket = null;
  try {
    // polling uniquement : le backend Waitress (WSGI) ne gère pas les websockets.
    socket = io(API, { transports: ["polling"] });
    socket.on("connect", () => setConn(true));
    socket.on("disconnect", () => setConn(false));
  } catch (e) {
    console.warn("Socket.IO indisponible :", e);
  }
  function setConn(ok) {
    const el = $("conn-status");
    el.classList.toggle("online", ok);
    el.classList.toggle("offline", !ok);
    el.title = ok ? "Connecté au centre SafeCity" : "Hors ligne";
  }

  // ---------------------------------------------------------------------- //
  // Géolocalisation
  // ---------------------------------------------------------------------- //
  function acquireGPS() {
    if (!navigator.geolocation) {
      $("gps-text").textContent = "Géolocalisation non supportée par ce navigateur.";
      return;
    }
    $("gps-text").textContent = "Acquisition de la position…";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        state.lat = pos.coords.latitude;
        state.lng = pos.coords.longitude;
        $("gps-text").textContent =
          "Position : " + state.lat.toFixed(5) + ", " + state.lng.toFixed(5) +
          " (±" + Math.round(pos.coords.accuracy) + " m)";
        resolveNeighborhood();
      },
      (err) => {
        $("gps-text").textContent = "Position indisponible : " + err.message +
          ". Vous pouvez tout de même envoyer, une position par défaut sera utilisée.";
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  }

  // Récupère quartier/adresse via le backend (reverse geocode).
  function resolveNeighborhood() {
    if (state.lat == null) return;
    // Le backend fournira quartier/adresse à la création ; on affiche une
    // estimation locale simple en attendant.
    state.neighborhood = state.neighborhood || "En cours…";
    state.address = state.address ||
      state.lat.toFixed(5) + ", " + state.lng.toFixed(5);
    $("ls-neighborhood").textContent = state.neighborhood;
    $("ls-address").textContent = state.address;
  }

  // ---------------------------------------------------------------------- //
  // Écran 1 -> 2 : bouton ALERTE
  // ---------------------------------------------------------------------- //
  $("btn-alert").addEventListener("click", () => {
    if (state.lat == null) acquireGPS();
    show("details");
  });
  $("btn-back").addEventListener("click", () => show("alert"));

  // ---------------------------------------------------------------------- //
  // Sélection du type de danger
  // ---------------------------------------------------------------------- //
  document.querySelectorAll(".danger-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".danger-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      state.type = chip.dataset.type;
    });
  });

  // ---------------------------------------------------------------------- //
  // Photo
  // ---------------------------------------------------------------------- //
  $("photo-input").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      state.photo = reader.result;
      renderPreview();
    };
    reader.readAsDataURL(file);
  });

  // ---------------------------------------------------------------------- //
  // Message vocal (MediaRecorder)
  // ---------------------------------------------------------------------- //
  let mediaRecorder = null;
  let audioChunks = [];
  $("btn-record").addEventListener("click", async () => {
    const btn = $("btn-record");
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }
    if (!navigator.mediaDevices) {
      alert("Enregistrement audio non supporté.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = (ev) => audioChunks.push(ev.data);
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        const reader = new FileReader();
        reader.onload = () => {
          state.audio = reader.result;
          renderPreview();
        };
        reader.readAsDataURL(blob);
        btn.classList.remove("recording");
        btn.textContent = "🎤 Message vocal";
      };
      mediaRecorder.start();
      btn.classList.add("recording");
      btn.textContent = "⏹️ Arrêter";
    } catch (err) {
      alert("Microphone inaccessible : " + err.message);
    }
  });

  function renderPreview() {
    const box = $("attach-preview");
    box.innerHTML = "";
    if (state.photo) {
      const img = document.createElement("img");
      img.src = state.photo;
      box.appendChild(img);
    }
    if (state.audio) {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = state.audio;
      box.appendChild(audio);
    }
  }

  // ---------------------------------------------------------------------- //
  // Envoi de l'alerte
  // ---------------------------------------------------------------------- //
  $("btn-send").addEventListener("click", async () => {
    const btn = $("btn-send");
    btn.disabled = true;
    btn.textContent = "Envoi en cours…";

    // Coordonnées par défaut si le GPS a échoué (centre-ville de démonstration).
    const lat = state.lat != null ? state.lat : -4.325;
    const lng = state.lng != null ? state.lng : 15.3222;

    const payload = {
      type: state.type || "autre",
      description: $("description").value,
      reporter_name: $("citizen-name").value,
      reporter_phone: $("citizen-phone").value,
      lat: lat,
      lng: lng,
      photo: state.photo,
      audio: state.audio,
    };

    try {
      if (!navigator.onLine) throw new Error("offline");
      const alert = await postAlert(payload);
      showConfirmation(alert);
    } catch (err) {
      // Mode hors-ligne : on met l'alerte en file d'attente pour envoi différé.
      queueAlert(payload);
      showQueued();
    } finally {
      btn.disabled = false;
      btn.textContent = "Envoyer l'alerte 🚀";
    }
  });

  // ---------------------------------------------------------------------- //
  // Mode hors-ligne : file d'attente locale + renvoi automatique
  // ---------------------------------------------------------------------- //
  const QUEUE_KEY = "safecity_pending";

  async function postAlert(payload) {
    const res = await fetch(API + "/api/alerts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  function getQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch (e) { return []; }
  }
  function setQueue(q) { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); }
  function queueAlert(payload) {
    const q = getQueue();
    q.push({ payload: payload, at: Date.now() });
    setQueue(q);
    updatePendingBadge();
  }

  let flushing = false;
  async function flushQueue() {
    // Verrou : évite l'envoi en double si deux flush se lancent en même temps
    // (événement "online" + intervalle périodique).
    if (flushing || !navigator.onLine) return;
    const q = getQueue();
    if (!q.length) return;
    flushing = true;
    try {
      const remaining = [];
      for (const item of q) {
        try { await postAlert(item.payload); } catch (e) { remaining.push(item); }
      }
      setQueue(remaining);
      updatePendingBadge();
      if (q.length && !remaining.length) {
        toast("✅ " + q.length + " alerte(s) en attente envoyée(s).");
      }
    } finally {
      flushing = false;
    }
  }

  function updatePendingBadge() {
    const n = getQueue().length;
    let el = document.getElementById("pending-badge");
    if (n > 0) {
      if (!el) {
        el = document.createElement("div");
        el.id = "pending-badge";
        el.className = "pending-badge";
        el.addEventListener("click", flushQueue);
        document.body.appendChild(el);
      }
      el.textContent = "📴 " + n + " alerte(s) en attente d'envoi";
    } else if (el) {
      el.remove();
    }
  }

  function showQueued() {
    $("cf-type").textContent = capitalize(state.type || "autre");
    $("cf-urgency").textContent = "En attente";
    $("cf-urgency").className = "";
    $("cf-neighborhood").textContent = state.neighborhood || "—";
    $("cf-distance").textContent = "—";
    $("cf-eta").textContent = "—";
    $("cf-type").closest("#screen-confirm").querySelector(".confirm-sub").textContent =
      "📴 Pas de réseau : votre alerte est enregistrée et sera envoyée automatiquement au retour de la connexion.";
    show("confirm");
  }

  function toast(msg) {
    const t = document.createElement("div");
    t.className = "pending-badge";
    t.style.background = "#22c55e";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  window.addEventListener("online", flushQueue);
  setInterval(flushQueue, 20000);
  flushQueue();
  updatePendingBadge();

  // ---------------------------------------------------------------------- //
  // Écran de confirmation + mini-carte
  // ---------------------------------------------------------------------- //
  let miniMap = null;
  function showConfirmation(alert) {
    const sub = document.querySelector("#screen-confirm .confirm-sub");
    if (sub) sub.textContent = "Le centre de surveillance a bien reçu votre signalement.";
    $("cf-type").textContent = capitalize(alert.type);
    const urg = $("cf-urgency");
    urg.textContent = capitalize(alert.urgency);
    urg.className = "urg-" + alert.urgency;
    $("cf-neighborhood").textContent = alert.neighborhood || "—";
    $("cf-distance").textContent =
      alert.distance_m != null ? Math.round(alert.distance_m) + " m" : "—";
    $("cf-eta").textContent =
      alert.eta_moto_min != null ? alert.eta_moto_min + " min" : "—";

    show("confirm");

    // Carte Leaflet centrée sur l'alerte.
    setTimeout(() => {
      if (!miniMap) {
        miniMap = L.map("mini-map").setView([alert.lat, alert.lng], 15);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "© OpenStreetMap",
          maxZoom: 19,
        }).addTo(miniMap);
      } else {
        miniMap.setView([alert.lat, alert.lng], 15);
      }
      L.marker([alert.lat, alert.lng]).addTo(miniMap)
        .bindPopup(capitalize(alert.type) + " — " + (alert.neighborhood || ""))
        .openPopup();
      miniMap.invalidateSize();
    }, 100);
  }

  $("btn-new").addEventListener("click", () => {
    // Réinitialise l'état pour une nouvelle alerte.
    state.type = null;
    state.photo = null;
    state.audio = null;
    $("description").value = "";
    $("citizen-name").value = "";
    $("citizen-phone").value = "";
    $("attach-preview").innerHTML = "";
    document.querySelectorAll(".danger-chip").forEach((c) => c.classList.remove("selected"));
    show("alert");
    acquireGPS();
  });

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  // Pré-acquisition de la position au chargement.
  acquireGPS();
})();
