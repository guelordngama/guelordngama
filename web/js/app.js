/* SafeCity — logique de l'application citoyenne.
 * Géolocalisation, sélection du danger, photo/audio, envoi et confirmation.
 */
(function () {
  "use strict";

  const API = window.SAFECITY_CONFIG.API_BASE;

  // Icônes de repère Leaflet servies localement (pas de CDN).
  if (typeof L !== "undefined") L.Icon.Default.imagePath = "vendor/leaflet/images/";

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
    const saved = localStorage.getItem(THEME_KEY) || "light";
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

  // Centre-ville de Lubumbashi : repli UNIQUEMENT si le GPS est indisponible
  // (l'alerte est alors marquée « position approximative »). Jamais Kinshasa.
  const LBB_LAT = -11.6647, LBB_LNG = 27.4794;

  // État courant de l'alerte en cours de composition.
  const state = {
    lat: null,
    lng: null,
    neighborhood: null,
    address: null,
    type: null,
    photo: null, // data URL
    audio: null, // data URL
    video: null, // data URL
  };

  // --- Raccourcis DOM ---
  const $ = (id) => document.getElementById(id);
  const screens = {
    auth: $("screen-auth"),
    alert: $("screen-alert"),
    details: $("screen-details"),
    confirm: $("screen-confirm"),
    track: $("screen-track"),
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
  // Affinage du GPS : la 1re position d'un téléphone vient souvent du Wi-Fi ou
  // des antennes (±100 à 1000 m). On écoute le GPS quelques secondes et on garde
  // la position la plus PRÉCISE, jusqu'à ±10 m ou 30 s maximum.
  const GPS_TARGET_M = 10, GPS_MAX_MS = 30000;
  let gpsWatch = null, gpsStopTimer = null;
  state.searching = false;
  state.place = null;          // {street, neighborhood, commune, city, available}
  state.placeFor = null;       // position pour laquelle l'adresse a été cherchée
  state.placeLoading = false;

  function stopGpsWatch() {
    if (gpsWatch != null && navigator.geolocation) navigator.geolocation.clearWatch(gpsWatch);
    gpsWatch = null;
    if (gpsStopTimer) { clearTimeout(gpsStopTimer); gpsStopTimer = null; }
    if (state.searching) { state.searching = false; renderLocation(); }
  }

  function acquireGPS() {
    if (!navigator.geolocation) {
      $("gps-text").textContent = tr("gps.unsupported", "Géolocalisation non supportée par ce navigateur.");
      return;
    }
    stopGpsWatch();
    state.searching = true;
    const box = $("gps-box");
    if (box) box.classList.remove("gps-error");
    renderLocation();
    gpsWatch = navigator.geolocation.watchPosition(onGpsFix, onGpsError,
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
    gpsStopTimer = setTimeout(stopGpsWatch, GPS_MAX_MS);
  }

  function onGpsFix(pos) {
    if (state.manual) return;       // ne pas écraser un point placé à la main
    const acc = pos.coords.accuracy;
    // Pendant l'affinage, on ne remplace une position que par une plus précise.
    if (state.lat != null && state.accuracy != null && state.fixAt &&
        Date.now() - state.fixAt < GPS_MAX_MS && acc > state.accuracy) return;
    state.lat = pos.coords.latitude;
    state.lng = pos.coords.longitude;
    state.accuracy = acc;           // précision en mètres
    state.fixAt = Date.now();
    const box = $("gps-box");
    if (box) { box.classList.remove("gps-error"); box.classList.add("gps-ok"); }
    if (pickMarker) pickMarker.setLatLng([state.lat, state.lng]);
    if (pickMap) pickMap.setView([state.lat, state.lng], 17);
    if (acc <= GPS_TARGET_M) stopGpsWatch();
    renderLocation();
    lookupAddress();
  }

  function onGpsError(err) {
    // Une position existe déjà : erreur passagère (délai, signal perdu un
    // instant) pendant l'affinage → on garde la position ET on continue
    // d'écouter le GPS (le minuteur de 30 s arrêtera l'affinage). Seul un refus
    // d'autorisation arrête tout.
    if (state.lat != null && state.lng != null) {
      if (err && err.code === 1) stopGpsWatch();
      return;
    }
    // Pas encore de position : délai dépassé (code 3) → on patiente encore
    // tant que le minuteur global court ; sinon on affiche l'aide.
    if (err && err.code === 3 && gpsStopTimer) return;
    stopGpsWatch();
    const box = $("gps-box");
    if (box) { box.classList.remove("gps-ok"); box.classList.add("gps-error"); }
    $("gps-text").innerHTML =
      "⚠️ <b>" + tr("gps.notObtained", "Position GPS non obtenue") + "</b> (" + escapeHtml(err.message) + "). " +
      tr("gps.errorHelp", "Activez la localisation puis") + ' <a href="#" id="gps-retry">' +
      tr("gps.retry", "réessayez") + "</a>, " + tr("gps.orTapMap",
      "ou touchez la carte pour placer votre position. Sinon l'alerte partira avec une position approximative.");
    const r = $("gps-retry");
    if (r) r.addEventListener("click", (e) => { e.preventDefault(); acquireGPS(); });
    renderSummary();
  }

  // ---- Adresse (commune, avenue, quartier, ville) via le serveur SafeCity ----
  let addrTimer = null;
  function distM(a, b) {
    const R = 6371000, r = Math.PI / 180;
    const dLat = (b[0] - a[0]) * r, dLng = (b[1] - a[1]) * r;
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  function lookupAddress() {
    if (state.lat == null) return;
    const here = [state.lat, state.lng];
    // Inutile de redemander pour quelques mètres d'écart.
    if (state.placeFor && distM(state.placeFor, here) < 15 && state.place) { renderLocation(); return; }
    clearTimeout(addrTimer);
    state.placeLoading = true;
    renderLocation();
    addrTimer = setTimeout(async () => {
      const q = [state.lat, state.lng];
      try {
        const r = await fetch(API + "/api/geo/reverse?lat=" + q[0] + "&lng=" + q[1]);
        if (!r.ok) throw new Error("HTTP " + r.status);
        const d = await r.json();
        // La position a pu changer entre-temps : on ne garde que la réponse à jour.
        if (state.lat === q[0] && state.lng === q[1]) { state.place = d; state.placeFor = q; }
      } catch (e) {
        state.place = { available: false };
        state.placeFor = null;
      } finally {
        state.placeLoading = false;
        renderLocation();
      }
    }, 1200);
  }

  function escapeHtml(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function gpsSigned(lat, lng) {
    return lat == null ? "—" : Number(lat).toFixed(6) + ", " + Number(lng).toFixed(6);
  }
  // « Avenue Sendwe » -> ["Avenue", "Sendwe"]
  function streetParts(street) {
    const s = (street || "").trim(), low = s.toLowerCase();
    const kinds = [[["avenue ", "av. ", "av "], "Avenue"], [["rue "], "Rue"],
      [["boulevard ", "bd "], "Boulevard"], [["route "], "Route"], [["chaussée "], "Chaussée"]];
    for (const [pre, label] of kinds) for (const p of pre) if (low.startsWith(p)) return [label, s.slice(p.length).trim() || s];
    return [tr("loc.street", "Avenue / Rue"), s];
  }
  function quality(acc) {
    if (acc == null) return null;
    if (acc <= 10) return ["excellent", tr("gps.q.excellent", "Excellente"), "#16a34a"];
    if (acc <= 30) return ["good", tr("gps.q.good", "Bonne"), "#16a34a"];
    if (acc <= 100) return ["medium", tr("gps.q.medium", "Moyenne"), "#d97706"];
    return ["weak", tr("gps.q.weak", "Faible"), "#dc2626"];
  }
  function placeValue(key) {
    if (state.lat == null) return "—";
    if (state.place && state.place[key]) return escapeHtml(state.place[key]);
    if (key === "city" && state.place && state.place.city) return escapeHtml(state.place.city);
    if (state.placeLoading) return '<span class="loc-wait">' + tr("geo.searching", "Recherche…") + "</span>";
    return "—";
  }
  function locRows() {
    const [stLabel, stVal] = streetParts(state.place && state.place.street);
    const q = quality(state.accuracy);
    const prec = state.manual ? tr("gps.manualShort", "Placée à la main")
      : state.accuracy == null ? "—"
      : "±" + Math.round(state.accuracy) + " m · <b style=\"color:" + q[2] + "\">" + q[1] + "</b>";
    return [
      [tr("loc.commune", "Commune"), placeValue("commune")],
      [stLabel, stVal ? escapeHtml(stVal) : placeValue("street")],
      [tr("loc.quartier", "Quartier"), placeValue("neighborhood")],
      [tr("loc.city", "Ville"), placeValue("city")],
      ["GPS", '<span class="loc-gps">' + gpsSigned(state.lat, state.lng) + "</span>"],
      [tr("gps.precision", "Précision"), prec],
    ];
  }
  function rowsHTML(rows) {
    return rows.map(([k, v]) => '<div class="loc-row"><span>' + escapeHtml(k) + "</span><b>" + v + "</b></div>").join("");
  }

  // Carte « Ma position actuelle » (accueil).
  function renderLocation() {
    const el = $("gps-text");
    if (!el) return;
    if (state.lat == null) {
      el.innerHTML = '<div class="loc-status searching"><span class="dot"></span>' +
        (state.searching ? tr("gps.searching", "Recherche du signal GPS…") : tr("gps.waiting", "Position non disponible")) + "</div>";
      renderSummary();
      return;
    }
    const q = quality(state.accuracy);
    let status;
    if (state.manual) status = '<div class="loc-status manual"><span class="dot"></span>' + tr("gps.manual", "Position placée à la main") + "</div>";
    else if (state.searching) status = '<div class="loc-status searching"><span class="dot"></span>' + tr("gps.refining", "GPS actif · amélioration de la précision…") + "</div>";
    else status = '<div class="loc-status ok"><span class="dot"></span>' + tr("gps.active", "GPS actif") + "</div>";
    let bar = "";
    if (q && !state.manual) {
      const pct = { excellent: 100, good: 75, medium: 45, weak: 18 }[q[0]];
      bar = '<div class="loc-bar"><i style="width:' + pct + "%;background:" + q[2] + '"></i></div>';
    }
    let hint = "";
    if (q && !state.manual && !state.searching && (q[0] === "medium" || q[0] === "weak")) {
      hint = '<p class="loc-hint">' + tr("gps.weakHint", "Précision faible : sortez à découvert et activez la localisation précise.") +
        ' <a href="#" id="gps-improve">' + tr("gps.improve", "Améliorer") + "</a></p>";
    }
    el.innerHTML = status + '<div class="loc-coords">' + gpsSigned(state.lat, state.lng) + "</div>" + bar +
      '<div class="loc-rows">' + rowsHTML(locRows().filter((r) => r[0] !== "GPS")) + "</div>" + hint;
    const imp = $("gps-improve");
    if (imp) imp.addEventListener("click", (e) => { e.preventDefault(); acquireGPS(); });
    renderSummary();
  }

  // Changement de langue (bouton SW/FR ou Réglages) : on redessine la position.
  document.addEventListener("click", (e) => {
    if (e.target.closest("#lang-toggle")) setTimeout(renderLocation, 0);
  });
  document.addEventListener("change", (e) => {
    if (e.target && e.target.id === "set-lang") setTimeout(renderLocation, 0);
  });

  // Récapitulatif « Ma position » de l'écran Détails.
  function renderSummary() {
    const host = $("loc-summary");
    if (!host) return;
    host.innerHTML = state.lat == null
      ? '<p class="loc-wait">' + tr("gps.waiting", "Position non disponible") + "</p>"
      : rowsHTML(locRows());
  }

  // ---------------------------------------------------------------------- //
  // Placement manuel de la position sur la carte
  // ---------------------------------------------------------------------- //
  let pickMap = null, pickMarker = null;
  function setPickedPosition(latlng) {
    state.lat = latlng.lat;
    state.lng = latlng.lng;
    state.manual = true;      // choix volontaire → position considérée fiable
    state.accuracy = null;    // pas de précision GPS pour un point placé à la main
    stopGpsWatch();
    if (pickMarker) pickMarker.setLatLng(latlng);
    const box = $("gps-box");
    if (box) { box.classList.remove("gps-error"); box.classList.add("gps-ok"); }
    renderLocation();
    lookupAddress();
  }
  function initPickMap() {
    if (typeof L === "undefined") return;  // Leaflet indisponible
    const center = (state.lat != null && state.lng != null)
      ? [state.lat, state.lng] : [LBB_LAT, LBB_LNG];
    if (!pickMap) {
      pickMap = L.map("pick-map").setView(center, 15);
      L.tileLayer(API + "/tiles/{z}/{x}/{y}.png",
        { attribution: "© OpenStreetMap © CARTO", maxZoom: 20 }).addTo(pickMap);
      pickMarker = L.marker(center, { draggable: true }).addTo(pickMap);
      pickMap.on("click", (e) => setPickedPosition(e.latlng));
      pickMarker.on("dragend", () => setPickedPosition(pickMarker.getLatLng()));
    } else {
      pickMap.setView(center, 15);
      pickMarker.setLatLng(center);
    }
    // La carte a été créée dans un conteneur masqué : recalcule sa taille.
    setTimeout(() => { if (pickMap) pickMap.invalidateSize(); }, 200);
  }

  // ---------------------------------------------------------------------- //
  // Écran 1 -> 2 : bouton ALERTE
  // ---------------------------------------------------------------------- //
  $("btn-alert").addEventListener("click", () => {
    // Position absente ou datant de plus d'une minute : on relance le GPS.
    if (!state.manual && (state.lat == null || !state.fixAt || Date.now() - state.fixAt > 60000)) acquireGPS();
    show("details");
    setTimeout(initPickMap, 120);  // carte visible → on l'initialise
  });

  // Recentrer sur la position GPS (annule un éventuel placement manuel).
  $("btn-use-gps").addEventListener("click", () => {
    state.manual = false;
    state.accuracy = null; state.fixAt = null;
    acquireGPS();
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

  // ---------------------------------------------------------------------- //
  // Vidéo (fichier ou capture caméra)
  // ---------------------------------------------------------------------- //
  // Limite côté client : la vidéo est encodée en base64 (~+33 %) dans la requête
  // JSON, qui est plafonnée à 32 Mo côté serveur. On refuse au-delas de ~18 Mo.
  const MAX_VIDEO_MB = 18;
  $("video-input").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > MAX_VIDEO_MB * 1024 * 1024) {
      toast("⚠️ Vidéo trop lourde (max " + MAX_VIDEO_MB + " Mo). Filmez plus court.");
      e.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      state.video = reader.result;
      renderPreview();
    };
    reader.readAsDataURL(file);
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
    if (state.video) {
      const video = document.createElement("video");
      video.controls = true;
      video.src = state.video;
      video.style.maxWidth = "100%";
      video.style.borderRadius = "10px";
      box.appendChild(video);
    }
  }

  // ---------------------------------------------------------------------- //
  // Envoi de l'alerte
  // ---------------------------------------------------------------------- //
  $("btn-send").addEventListener("click", async () => {
    const btn = $("btn-send");
    btn.disabled = true;
    btn.textContent = "Envoi en cours…";

    // Position : GPS réel si disponible, sinon repli sur le centre de Lubumbashi
    // (JAMAIS Kinshasa) et l'alerte est marquée « position approximative » pour
    // que l'opérateur et la patrouille sachent que ce n'est pas la position exacte.
    const hasGPS = state.lat != null && state.lng != null;
    const lat = hasGPS ? state.lat : LBB_LAT;
    const lng = hasGPS ? state.lng : LBB_LNG;

    const auth = getAuth();
    const payload = {
      type: state.type || "autre",
      description: $("description").value,
      reporter_name: $("citizen-name").value || (auth && auth.user && auth.user.name) || "",
      reporter_phone: $("citizen-phone").value || (auth && auth.user && auth.user.phone) || "",
      reporter_id: auth && auth.user ? auth.user.id : null,
      lat: lat,
      lng: lng,
      position_approx: !hasGPS,
      // Précision GPS (m) et mode de localisation, pour la fiche de l'opérateur.
      accuracy: hasGPS && !state.manual ? state.accuracy : null,
      position_manual: hasGPS && !!state.manual,
      photo: state.photo,
      audio: state.audio,
      video: state.video,
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
    $("cf-type").textContent = typeLabel(state.type || "autre");
    $("cf-urgency").textContent = "En attente";
    $("cf-urgency").className = "";
    $("cf-neighborhood").textContent = placeLine() || "—";
    $("cf-distance").textContent = "—";
    $("cf-eta").textContent = "—";
    $("cf-type").closest("#screen-confirm").querySelector(".confirm-sub").textContent =
      "📴 Pas de réseau : votre alerte est enregistrée et sera envoyée automatiquement au retour de la connexion.";
    // Pas encore de référence (envoi différé) : on masque le suivi.
    stopTrackPoll();
    $("cf-ref-box").hidden = true;
    $("cf-timeline").hidden = true;
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
  // ---- Suivi d'alerte (référence + chronologie d'avancement) ----
  const TRACK_LABELS = {
    received: "Alerte reçue",
    assigned: "Prise en charge",
    resolved: "Résolue",
  };

  function fmtTime(iso) {
    if (!iso) return "";
    // Le serveur stocke en UTC sans suffixe de fuseau : on l'indique au navigateur.
    const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
    if (isNaN(d)) return "";
    return d.toLocaleString("fr-FR", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  }

  // Traduit une clé si i18n est chargé, sinon repli sur le texte fourni.
  const tr = (key, fallback) =>
    (window.t ? window.t(key) : null) || fallback || key;

  // Coordonnées GPS formatées façon « 11.66470°S, 27.48000°E ».
  function formatCoords(lat, lng) {
    if (lat == null || lng == null) return "—";
    const ns = lat >= 0 ? "N" : "S", ew = lng >= 0 ? "E" : "O";
    return Math.abs(lat).toFixed(5) + "°" + ns + ", " + Math.abs(lng).toFixed(5) + "°" + ew;
  }

  // Nom traduit d'un type d'incident (Vol/Wizi…), repli sur le type capitalisé.
  function typeLabel(type) {
    if (!type) return "—";
    const k = "typename." + type;
    const v = window.t ? window.t(k) : null;
    return v && v !== k ? v : capitalize(type);
  }

  // Construit/rafraîchit une chronologie (élément <ol>) à partir des étapes.
  function renderTimeline(ol, steps) {
    ol.innerHTML = "";
    (steps || []).forEach((s) => {
      const li = document.createElement("li");
      li.className = "tl-step" + (s.done ? " done" : "");
      const icon = document.createElement("span");
      icon.className = "tl-icon";
      icon.textContent = s.done ? "✓" : "•";
      const body = document.createElement("div");
      const label = document.createElement("div");
      label.className = "tl-label";
      // Libellé traduit (FR/SW) selon la clé d'étape ; repli sur le libellé serveur.
      label.textContent = tr("step." + s.key, s.label || TRACK_LABELS[s.key] || s.key);
      body.appendChild(label);
      if (s.at) {
        const when = document.createElement("div");
        when.className = "tl-when";
        when.textContent = fmtTime(s.at);
        body.appendChild(when);
      }
      li.appendChild(icon);
      li.appendChild(body);
      ol.appendChild(li);
    });
  }

  let trackPoll = null;      // intervalle de rafraîchissement du suivi (confirm)
  function stopTrackPoll() {
    if (trackPoll) { clearInterval(trackPoll); trackPoll = null; }
  }

  async function fetchTrack(ref) {
    const res = await fetch(API + "/api/alerts/track/" + encodeURIComponent(ref));
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  // Suit l'alerte de l'écran de confirmation : affiche puis rafraîchit toutes
  // les 15 s tant que l'alerte n'est pas résolue (repli si le socket est bloqué).
  function startConfirmTracking(ref) {
    stopTrackPoll();
    if (!ref) return;
    const box = $("cf-ref-box");
    $("cf-ref").textContent = ref;
    box.hidden = false;
    const ol = $("cf-timeline");
    ol.hidden = false;
    const update = async () => {
      try {
        const st = await fetchTrack(ref);
        renderTimeline(ol, st.steps);
        const sub = document.querySelector("#screen-confirm .confirm-sub");
        if (sub) {
          if (st.status === "cloturee") {
            sub.textContent = tr("confirm.resolved", "✅ Votre alerte a été traitée et clôturée. Merci.");
          } else if (st.status === "assignee") {
            sub.textContent = st.agent_first_name
              ? tr("confirm.assignedAgent", "🚓 Un agent a été affecté.").replace("{name}", st.agent_first_name)
              : tr("confirm.assigned", "🚓 Votre alerte a été prise en charge.");
          }
        }
        if (st.status === "cloturee") stopTrackPoll();
      } catch (e) { /* réseau : on retentera au prochain tick */ }
    };
    update();
    trackPoll = setInterval(update, 15000);
  }

  let miniMap = null;
  function showConfirmation(alert) {
    const sub = document.querySelector("#screen-confirm .confirm-sub");
    if (sub) sub.textContent = "Le centre de surveillance a bien reçu votre signalement.";
    $("cf-type").textContent = typeLabel(alert.type);
    const urg = $("cf-urgency");
    urg.textContent = capitalize(alert.urgency);
    urg.className = "urg-" + alert.urgency;
    $("cf-neighborhood").textContent = alert.neighborhood || placeLine() || "—";
    $("cf-distance").textContent =
      alert.distance_m != null ? Math.round(alert.distance_m) + " m" : "—";
    $("cf-eta").textContent =
      alert.eta_moto_min != null ? alert.eta_moto_min + " min" : "—";
    // Coordonnées GPS : affichées ; si approximatives, on avertit clairement.
    $("cf-coords-val").textContent = gpsSigned(alert.lat, alert.lng) +
      (alert.gps_accuracy_m != null ? "  (±" + Math.round(alert.gps_accuracy_m) + " m)" : "");
    const approx = !!alert.position_approx;
    $("cf-coords").classList.toggle("approx", approx);
    $("cf-approx").hidden = !approx;
    document.querySelector("#cf-coords .cf-coords-label").textContent =
      approx ? tr("confirm.coordsApprox", "📍 Position approximative")
             : tr("confirm.coords", "📍 Position exacte");

    show("confirm");
    // Affiche la référence et démarre le suivi en direct de l'avancement.
    startConfirmTracking(alert.reference);

    // Carte Leaflet centrée sur l'alerte.
    setTimeout(() => {
      if (!miniMap) {
        miniMap = L.map("mini-map").setView([alert.lat, alert.lng], 15);
        // Tuiles servies par le proxy du serveur SafeCity (/tiles/…) : contourne
        // le blocage des CDN externes par le pare-feu.
        L.tileLayer(API + "/tiles/{z}/{x}/{y}.png", {
          attribution: "© OpenStreetMap © CARTO",
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

  // ---- Navigation du suivi par référence ----
  $("btn-track-later").addEventListener("click", () => {
    $("track-result").hidden = true;
    $("track-error").hidden = true;
    show("track");
  });

  // Cliquer sur la position exacte la copie (pratique pour la transmettre).
  $("cf-coords").addEventListener("click", () => {
    const v = ($("cf-coords-val").textContent || "").split("  (")[0];
    if (!v || v === "—") return;
    const done = () => toast("📍 " + tr("confirm.coordsCopied", "Position copiée") + " : " + v);
    if (navigator.clipboard) navigator.clipboard.writeText(v).then(done, done);
    else done();
  });
  $("btn-track-back").addEventListener("click", () => {
    // Revenir à l'écran précédent : confirmation si une alerte y est suivie,
    // sinon l'écran d'alerte.
    show($("cf-ref-box").hidden ? "alert" : "confirm");
  });
  async function runTrackLookup() {
    const ref = ($("track-input").value || "").trim().toUpperCase();
    if (!ref) return;
    $("track-error").hidden = true;
    try {
      const st = await fetchTrack(ref);
      $("tk-ref").textContent = st.reference || ref;
      $("tk-type").textContent = st.type ? typeLabel(st.type) : "—";
      $("tk-neighborhood").textContent = st.neighborhood || "—";
      $("tk-agent").textContent = st.agent_first_name || "—";
      renderTimeline($("tk-timeline"), st.steps);
      $("track-result").hidden = false;
    } catch (e) {
      $("track-result").hidden = true;
      $("track-error").hidden = false;
    }
  }
  $("btn-track-go").addEventListener("click", runTrackLookup);
  $("track-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); runTrackLookup(); }
  });

  $("btn-new").addEventListener("click", () => {
    stopTrackPoll();
    $("cf-ref-box").hidden = true;
    $("cf-timeline").hidden = true;
    // Réinitialise l'état pour une nouvelle alerte.
    state.type = null;
    state.photo = null;
    state.audio = null;
    state.video = null;
    state.manual = false;
    $("description").value = "";
    $("citizen-name").value = "";
    $("citizen-phone").value = "";
    $("attach-preview").innerHTML = "";
    document.querySelectorAll(".danger-chip").forEach((c) => c.classList.remove("selected"));
    show("alert");
    acquireGPS();
  });

  // « Bongonga, commune Kenya » d'après l'adresse trouvée avant l'envoi.
  function placeLine() {
    const p = state.place || {};
    return [p.neighborhood, p.commune && tr("loc.communeOf", "commune") + " " + p.commune].filter(Boolean).join(", ");
  }

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
