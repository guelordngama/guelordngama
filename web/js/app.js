/* SafeCity — logique de l'application citoyenne.
 * Géolocalisation, sélection du danger, photo/audio, envoi et confirmation.
 */
(function () {
  "use strict";

  const API = window.SAFECITY_CONFIG.API_BASE;

  // E-mail requis à l'inscription ? (vrai si aucun SMS n'est configuré côté
  // serveur : le code de vérification ne peut alors être envoyé que par e-mail).
  let emailRequired = false;
  (function fetchMeta() {
    fetch(API + "/api/meta").then((r) => r.json()).then((m) => {
      emailRequired = !!m.email_required;
      if (!emailRequired) return;
      const label = document.getElementById("reg-email-label");
      const hint = document.getElementById("reg-email-hint");
      const input = document.getElementById("reg-email");
      if (label) label.innerHTML = "✉️ E-mail <strong>(requis)</strong>";
      if (input) input.setAttribute("required", "required");
      if (hint) hint.textContent =
        "Votre code de vérification vous sera envoyé à cette adresse.";
    }).catch(() => {});
  })();

  // ---------------------------------------------------------------------- //
  // Thème clair / sombre (préférence mémorisée)
  // ---------------------------------------------------------------------- //
  (function initTheme() {
    const THEME_KEY = "safecity_theme";
    const root = document.documentElement;
    const saved = localStorage.getItem(THEME_KEY) || "dark";
    applyTheme(saved);
    function applyTheme(mode) {
      root.setAttribute("data-theme", mode);
      const btn = document.getElementById("theme-toggle");
      if (btn) btn.textContent = mode === "light" ? "☀️" : "🌙";
    }
    document.addEventListener("click", (e) => {
      if (!e.target.closest("#theme-toggle")) return;
      const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  })();

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
    auth: $("screen-auth"),
    alert: $("screen-alert"),
    details: $("screen-details"),
    confirm: $("screen-confirm"),
  };

  function show(name) {
    Object.values(screens).forEach((s) => s.classList.remove("active"));
    screens[name].classList.add("active");
  }

  // ---------------------------------------------------------------------- //
  // Authentification (compte citoyen)
  // ---------------------------------------------------------------------- //
  const AUTH_KEY = "safecity_auth";

  function getAuth() {
    try { return JSON.parse(localStorage.getItem(AUTH_KEY)) || null; } catch (e) { return null; }
  }
  function setAuth(data) { localStorage.setItem(AUTH_KEY, JSON.stringify(data)); }
  function clearAuth() { localStorage.removeItem(AUTH_KEY); }

  function refreshUserChip() {
    const auth = getAuth();
    const chip = $("user-chip");
    if (auth && auth.user) {
      $("user-name").textContent = auth.user.name || auth.user.phone || "Mon compte";
      chip.hidden = false;
    } else {
      chip.hidden = true;
    }
  }

  function authError(msg) {
    const box = $("auth-error");
    box.textContent = msg;
    box.hidden = !msg;
    box.style.color = "";  // revient au rouge défini par la CSS
  }

  let pendingOtpPhone = null;   // numéro en cours de vérification
  let resetPhone = null;        // numéro en cours de réinitialisation

  const AUTH_FORMS = ["form-login", "form-register", "form-otp", "form-forgot", "form-reset"];
  function showForm(id) {
    AUTH_FORMS.forEach((f) => { const el = $(f); if (el) el.hidden = f !== id; });
    $("tab-login").classList.toggle("active", id === "form-login");
    $("tab-register").classList.toggle("active", id === "form-register");
    authError("");
  }
  function switchAuthTab(mode) { showForm(mode === "login" ? "form-login" : "form-register"); }

  function setLoading(btn, on) {
    btn.disabled = on;
    const sp = btn.querySelector(".spinner");
    if (sp) sp.hidden = !on;
  }
  function infoMsg(msg) {
    const box = $("auth-error");
    box.textContent = msg; box.hidden = false; box.style.color = "#22c55e";
  }
  function fieldErr(id, msg) {
    const el = $(id); if (!el) return;
    el.textContent = msg || ""; el.hidden = !msg;
  }
  function validPhone(p) { return (p || "").replace(/\D/g, "").length >= 8; }

  // ---- Afficher / masquer les mots de passe ----
  document.addEventListener("click", (e) => {
    const eye = e.target.closest(".pw-eye");
    if (!eye) return;
    const inp = $(eye.dataset.target); if (!inp) return;
    const reveal = inp.type === "password";
    inp.type = reveal ? "text" : "password";
    eye.textContent = reveal ? "🙈" : "👁️";
  });

  // ---- Robustesse du mot de passe (inscription) ----
  function pwScore(p) {
    let s = 0;
    if (p.length >= 6) s++;
    if (p.length >= 10) s++;
    if (/[A-Z]/.test(p) && /[a-z]/.test(p)) s++;
    if (/\d/.test(p)) s++;
    if (/[^A-Za-z0-9]/.test(p)) s++;
    return Math.min(s, 4);
  }
  $("reg-password").addEventListener("input", () => {
    const p = $("reg-password").value;
    const score = pwScore(p);
    const pct = [0, 25, 50, 75, 100][score];
    const colors = ["#ef4444", "#ef4444", "#f97316", "#eab308", "#22c55e"];
    const words = ["Très faible", "Très faible", "Faible", "Moyen", "Fort"];
    $("reg-strength").style.width = (p ? Math.max(pct, 10) : 0) + "%";
    $("reg-strength").style.background = colors[score];
    $("reg-strength-label").textContent = p ? "Robustesse : " + words[score] : "";
  });

  // ---- Cases de saisie du code (6 chiffres) ----
  function setupCodeBoxes(hostId, hiddenId, onComplete) {
    const host = $(hostId), hidden = $(hiddenId);
    host.innerHTML = "";
    const boxes = [];
    const sync = () => {
      const code = boxes.map((b) => b.value).join("");
      hidden.value = code;
      if (code.length === 6 && onComplete) onComplete(code);
    };
    for (let i = 0; i < 6; i++) {
      const inp = document.createElement("input");
      inp.type = "text"; inp.inputMode = "numeric"; inp.maxLength = 1;
      inp.autocomplete = i === 0 ? "one-time-code" : "off";
      inp.addEventListener("input", () => {
        inp.value = inp.value.replace(/\D/g, "").slice(0, 1);
        if (inp.value && i < 5) boxes[i + 1].focus();
        sync();
      });
      inp.addEventListener("keydown", (ev) => {
        if (ev.key === "Backspace" && !inp.value && i > 0) boxes[i - 1].focus();
      });
      inp.addEventListener("paste", (ev) => {
        ev.preventDefault();
        const d = (ev.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
        for (let k = 0; k < 6; k++) boxes[k].value = d[k] || "";
        boxes[Math.min(d.length, 5)].focus();
        sync();
      });
      host.appendChild(inp); boxes.push(inp);
    }
    return {
      clear() { boxes.forEach((b) => (b.value = "")); hidden.value = ""; },
      focus() { boxes[0].focus(); },
    };
  }
  const otpBoxes = setupCodeBoxes("otp-boxes", "otp-code",
    () => $("form-otp").requestSubmit());
  const resetBoxes = setupCodeBoxes("reset-boxes", "reset-code", null);

  // ---- Compte à rebours « renvoyer le code » ----
  function startResendTimer(linkId, timerId, seconds) {
    const link = $(linkId), timer = $(timerId);
    let left = seconds;
    link.style.pointerEvents = "none"; link.style.opacity = "0.45";
    timer.textContent = "(" + left + " s)";
    const iv = setInterval(() => {
      left--;
      if (left <= 0) {
        clearInterval(iv); timer.textContent = "";
        link.style.pointerEvents = ""; link.style.opacity = "";
      } else timer.textContent = "(" + left + " s)";
    }, 1000);
  }

  // Affiche l'écran de saisie du code (vérification du téléphone).
  // `channel` = "sms" | "email" | "dev" : adapte le texte d'explication.
  function showOtp(phone, channel) {
    pendingOtpPhone = phone;
    $("otp-phone").textContent = phone;
    const intro = $("otp-intro");
    if (intro) {
      if (channel === "email") {
        intro.innerHTML = "📧 Un code de vérification à 6 chiffres a été envoyé à " +
          "<strong>votre adresse e-mail</strong>. Saisissez-le pour activer votre compte.";
      } else {
        intro.innerHTML = "📲 Un code de vérification a été envoyé par SMS au " +
          "<strong id=\"otp-phone\">" + phone + "</strong>. Saisissez-le pour activer votre compte.";
      }
    }
    showForm("form-otp");
    otpBoxes.clear(); otpBoxes.focus();
    startResendTimer("otp-resend", "otp-timer", 45);
  }

  $("tab-login").addEventListener("click", () => switchAuthTab("login"));
  $("tab-register").addEventListener("click", () => switchAuthTab("register"));
  $("go-register").addEventListener("click", (e) => { e.preventDefault(); switchAuthTab("register"); });
  $("go-login").addEventListener("click", (e) => { e.preventDefault(); switchAuthTab("login"); });

  async function authRequest(path, body) {
    const res = await fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  }

  // ---- Connexion ----
  $("form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    setLoading(btn, true); authError("");
    const identifier = $("login-identifier").value.trim();
    const password = $("login-password").value;
    if (!identifier || !password) {
      authError("Renseignez votre identifiant et votre mot de passe.");
      setLoading(btn, false); return;
    }
    try {
      const { ok, data } = await authRequest("/api/auth/login", { identifier, password });
      if (!ok) {
        if (data.error && data.error.code === "phone_not_verified") {
          showOtp(identifier);
          authRequest("/api/auth/resend-otp", { phone: identifier });
          return;
        }
        authError((data.error && data.error.message) || "Connexion impossible.");
        return;
      }
      onAuthenticated(data);
    } catch (err) {
      authError("Réseau indisponible. Vérifiez votre connexion.");
    } finally {
      setLoading(btn, false);
    }
  });

  // ---- Inscription ----
  $("form-register").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    setLoading(btn, true); authError("");
    const name = $("reg-name").value.trim();
    const phone = $("reg-phone").value.trim();
    const password = $("reg-password").value;

    const email = $("reg-email").value.trim();

    // Validations côté client (retour immédiat, par champ).
    let bad = false;
    if (!name) { fieldErr("err-name", "Votre nom est requis."); bad = true; } else fieldErr("err-name", "");
    if (!validPhone(phone)) { fieldErr("err-phone", "Numéro invalide (au moins 8 chiffres)."); bad = true; } else fieldErr("err-phone", "");
    if (emailRequired && !email) {
      fieldErr("err-email", "Un e-mail est requis pour recevoir votre code de vérification."); bad = true;
    } else if (email && !email.includes("@")) {
      fieldErr("err-email", "Adresse e-mail invalide."); bad = true;
    } else fieldErr("err-email", "");
    if (password.length < 6) { authError("Le mot de passe doit contenir au moins 6 caractères."); bad = true; }
    if (password !== $("reg-password2").value) { fieldErr("err-password2", "Les mots de passe ne correspondent pas."); bad = true; } else fieldErr("err-password2", "");
    if (!$("reg-consent").checked) { authError("Vous devez accepter la politique de confidentialité."); bad = true; }
    if (bad) { setLoading(btn, false); return; }

    const body = { name, phone, email, password, consent: true };
    try {
      const { ok, status, data } = await authRequest("/api/auth/register", body);
      if (!ok) {
        const field = data.error && data.error.details && data.error.details.field;
        if (field === "email") {
          fieldErr("err-email", (data.error && data.error.message) ||
            "Un e-mail est requis pour recevoir votre code de vérification.");
          return;
        }
        const msg = (data.error && data.error.message) ||
          (status === 409 ? "Ce numéro existe déjà. Connectez-vous ou utilisez un autre numéro."
                          : "Inscription impossible.");
        authError(msg);
        if (status === 409 && field === "phone") {
          $("login-identifier").value = body.phone;
        }
        return;
      }
      if (data.verification_required) { showOtp(data.phone || body.phone, data.channel); return; }
      onAuthenticated(data);
    } catch (err) {
      authError("Réseau indisponible. Vérifiez votre connexion.");
    } finally {
      setLoading(btn, false);
    }
  });

  // ---- Vérification du code SMS (OTP) ----
  $("form-otp").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    const code = $("otp-code").value.trim();
    if (code.length !== 6) { authError("Entrez le code à 6 chiffres reçu par SMS ou e-mail."); return; }
    setLoading(btn, true); authError("");
    try {
      const { ok, data } = await authRequest("/api/auth/verify-otp",
        { phone: pendingOtpPhone, code });
      if (!ok) {
        authError((data.error && data.error.message) || "Vérification impossible.");
        otpBoxes.clear(); otpBoxes.focus();
        return;
      }
      onAuthenticated(data);
    } catch (err) {
      authError("Réseau indisponible. Vérifiez votre connexion.");
    } finally {
      setLoading(btn, false);
    }
  });

  $("otp-resend").addEventListener("click", async (e) => {
    e.preventDefault();
    if (!pendingOtpPhone) return;
    try {
      await authRequest("/api/auth/resend-otp", { phone: pendingOtpPhone });
      infoMsg("📩 Un nouveau code vient d'être envoyé.");
      startResendTimer("otp-resend", "otp-timer", 45);
    } catch (err) { authError("Réseau indisponible."); }
  });

  // ---- Mot de passe oublié (par SMS) ----
  $("go-forgot").addEventListener("click", (e) => {
    e.preventDefault();
    const id = $("login-identifier").value.trim();
    if (id && !id.includes("@")) $("forgot-phone").value = id;
    showForm("form-forgot");
  });
  $("forgot-back").addEventListener("click", (e) => { e.preventDefault(); showForm("form-login"); });

  $("form-forgot").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    const phone = $("forgot-phone").value.trim();
    if (!validPhone(phone)) { authError("Entrez un numéro de téléphone valide."); return; }
    setLoading(btn, true); authError("");
    try {
      await authRequest("/api/auth/forgot-password-sms", { phone });
      resetPhone = phone;
      $("reset-phone").textContent = phone;
      showForm("form-reset");
      resetBoxes.clear(); resetBoxes.focus();
      startResendTimer("reset-resend", "reset-timer", 45);
    } catch (err) {
      authError("Réseau indisponible. Vérifiez votre connexion.");
    } finally {
      setLoading(btn, false);
    }
  });

  $("reset-resend").addEventListener("click", async (e) => {
    e.preventDefault();
    if (!resetPhone) return;
    try {
      await authRequest("/api/auth/forgot-password-sms", { phone: resetPhone });
      infoMsg("📩 Un nouveau code vient d'être envoyé.");
      startResendTimer("reset-resend", "reset-timer", 45);
    } catch (err) { authError("Réseau indisponible."); }
  });

  $("form-reset").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    const code = $("reset-code").value.trim();
    const np = $("reset-password").value;
    if (code.length !== 6) { authError("Entrez le code à 6 chiffres reçu par SMS."); return; }
    if (np.length < 6) { fieldErr("err-reset", "Au moins 6 caractères."); return; }
    fieldErr("err-reset", "");
    setLoading(btn, true); authError("");
    try {
      const { ok, data } = await authRequest("/api/auth/reset-password-sms",
        { phone: resetPhone, code, new_password: np });
      if (!ok) {
        authError((data.error && data.error.message) || "Réinitialisation impossible.");
        resetBoxes.clear(); resetBoxes.focus();
        return;
      }
      onAuthenticated(data);
    } catch (err) {
      authError("Réseau indisponible. Vérifiez votre connexion.");
    } finally {
      setLoading(btn, false);
    }
  });

  function onAuthenticated(data) {
    setAuth(data);
    refreshUserChip();
    // Pré-remplit les champs déclarant avec le compte.
    if (data.user) {
      if (data.user.name) $("citizen-name").value = data.user.name;
      if (data.user.phone) $("citizen-phone").value = data.user.phone;
    }
    authError("");
    show("alert");
    acquireGPS();
  }

  $("btn-logout").addEventListener("click", () => {
    clearAuth();
    refreshUserChip();
    $("login-password").value = "";
    showForm("form-login");
    show("auth");
  });

  // ---- Politique de confidentialité (modale) ----
  function openPrivacy(e) { if (e) e.preventDefault(); $("privacy-modal").hidden = false; }
  function closePrivacy() { $("privacy-modal").hidden = true; }
  $("open-privacy").addEventListener("click", openPrivacy);
  $("open-privacy-2").addEventListener("click", openPrivacy);
  $("close-privacy").addEventListener("click", closePrivacy);
  $("privacy-modal").addEventListener("click", (e) => {
    if (e.target === $("privacy-modal")) closePrivacy();
  });

  // ---- Droit à l'effacement : suppression du compte ----
  $("btn-delete-account").addEventListener("click", async (e) => {
    e.preventDefault();
    const auth = getAuth();
    if (!auth || !auth.token) return;
    if (!confirm("Supprimer définitivement votre compte ? Vos données personnelles "
      + "seront effacées. Cette action est irréversible.")) return;
    try {
      const res = await fetch(API + "/api/auth/me", {
        method: "DELETE",
        headers: { "Authorization": "Bearer " + auth.token },
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      clearAuth();
      refreshUserChip();
      alert("Votre compte et vos données personnelles ont été supprimés.");
      show("auth");
    } catch (err) {
      alert("Suppression impossible pour le moment. Réessayez plus tard.");
    }
  });

  // ---------------------------------------------------------------------- //
  // Connexion temps réel (indicateur d'état)
  // ---------------------------------------------------------------------- //
  let socket = null;
  try {
    // polling d'abord, puis montée en websocket si le serveur le permet
    // (production eventlet/Nginx). En dev (Waitress), reste en polling.
    socket = io(API, { transports: ["polling", "websocket"] });
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

    const auth = getAuth();
    const payload = {
      type: state.type || "autre",
      description: $("description").value,
      reporter_name: $("citizen-name").value || (auth && auth.user && auth.user.name) || "",
      reporter_phone: $("citizen-phone").value || (auth && auth.user && auth.user.phone) || "",
      reporter_id: auth && auth.user ? auth.user.id : null,
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
        L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
          attribution: "© OpenStreetMap © CARTO",
          subdomains: "abcd",
          maxZoom: 20,
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

  // ---------------------------------------------------------------------- //
  // Démarrage : compte requis avant d'accéder au bouton d'alerte
  // ---------------------------------------------------------------------- //
  refreshUserChip();
  if (getAuth()) {
    const u = getAuth().user || {};
    if (u.name) $("citizen-name").value = u.name;
    if (u.phone) $("citizen-phone").value = u.phone;
    show("alert");
    acquireGPS(); // pré-acquisition de la position
  } else {
    show("auth"); // première visite : inviter à créer un compte / se connecter
  }
})();
