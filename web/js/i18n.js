// Internationalisation de l'application citoyenne SafeCity (Français / Swahili).
// Lubumbashi étant largement swahiliphone, l'appli propose une bascule FR/SW.
// Les éléments HTML portent data-i18n (texte), data-i18n-ph (placeholder) ou
// data-i18n-title (title + aria-label). Le code dynamique utilise window.t(clé).
(function () {
  var STRINGS = {
    fr: {
      "app.tagline": "Alerte d'urgence citoyenne",
      "header.logout": "Déconnexion",
      "lang.name": "Français",

      "auth.login": "Se connecter",
      "auth.register": "Créer un compte",
      "auth.intro": "Bienvenue sur SafeCity. Créez un compte pour signaler un danger, ou connectez-vous si vous en avez déjà un.",
      "auth.identifier": "📱 Téléphone ou e-mail",
      "auth.identifier.ph": "+243 … ou vous@exemple.com",
      "auth.password": "🔒 Mot de passe",
      "auth.password.ph": "Votre mot de passe",
      "auth.forgot": "Mot de passe oublié ?",
      "auth.noAccount": "Pas encore de compte ?",
      "auth.createOne": "Créez-en un",
      "auth.name": "👤 Nom complet",
      "auth.name.ph": "Nom et prénom",
      "auth.phone": "📱 Numéro de téléphone",
      "auth.email": "✉️ E-mail (optionnel)",
      "auth.email.ph": "vous@exemple.com",
      "auth.emailHint": "Utile pour récupérer votre mot de passe en cas d'oubli.",
      "auth.newPassword": "🔒 Mot de passe (min. 6 caractères)",
      "auth.newPassword.ph": "Choisissez un mot de passe",
      "auth.confirmPassword": "🔒 Confirmer le mot de passe",
      "auth.confirmPassword.ph": "Retapez le mot de passe",
      "auth.consent": "J'ai lu et j'accepte la",
      "auth.privacyPolicy": "politique de confidentialité",
      "auth.consentEnd": "(collecte du nom, téléphone, position et signalements).",
      "auth.createMyAccount": "Créer mon compte",
      "auth.already": "Déjà inscrit ?",
      "auth.doLogin": "Connectez-vous",
      "auth.forgotIntro": "🔑 Entrez le numéro de téléphone de votre compte. Un code de réinitialisation vous sera envoyé par SMS.",
      "auth.sendCode": "Envoyer le code",
      "auth.backToLogin": "← Retour à la connexion",

      "alert.intro": "En cas de danger, appuyez sur le bouton. Votre position GPS sera transmise immédiatement au centre de surveillance.",
      "alert.button": "ALERTE",
      "alert.gps": "Acquisition de la position…",
      "alert.legalHint": "⚖️ N'utilisez ce bouton qu'en cas de danger réel. Une fausse alerte est punie par la loi.",
      "alert.privacy": "Confidentialité",
      "alert.deleteAccount": "Supprimer mon compte",

      "details.title": "Détails de l'incident",
      "details.dangerType": "⚠️ Type de danger",
      "type.vol": "🕵️ Vol",
      "type.braquage": "🔫 Braquage",
      "type.incendie": "🔥 Incendie",
      "type.accident": "🚗 Accident",
      "type.violence": "👊 Violence",
      "type.autre": "❓ Autre",
      "details.yourName": "👤 Votre nom (optionnel)",
      "details.yourName.ph": "Nom / prénom",
      "details.yourPhone": "📞 Téléphone (optionnel)",
      "details.description": "📝 Description (optionnel)",
      "details.description.ph": "Décrivez brièvement la situation…",
      "details.photo": "📷 Photo",
      "details.voice": "🎤 Message vocal",
      "details.video": "🎬 Vidéo",
      "details.neighborhood": "Quartier",
      "details.position": "Position",
      "details.pickHint": "Touchez la carte pour indiquer votre position exacte (utile si le GPS ne marche pas).",
      "details.manualSet": "Position placée à la main",
      "details.useGps": "📍 Utiliser ma position GPS",
      "details.warningTitle": "Avertissement :",
      "details.warning": " ce service est réservé aux situations réelles. Tout signalement volontairement faux ou abusif mobilise inutilement les secours, met des vies en danger et constitue une infraction punie par la loi. En envoyant cette alerte, vous confirmez que les informations fournies sont exactes.",
      "details.cancel": "Annuler",
      "details.send": "Envoyer l'alerte 🚀",

      "confirm.title": "Alerte envoyée",
      "confirm.sub": "Le centre de surveillance a bien reçu votre signalement.",
      "confirm.refLabel": "Votre référence de suivi",
      "confirm.refHint": "Notez-la pour suivre votre alerte, même après avoir fermé la page.",
      "confirm.type": "Type",
      "confirm.urgency": "Urgence (IA)",
      "confirm.neighborhood": "Quartier",
      "confirm.distance": "Distance équipe",
      "confirm.eta": "Temps estimé (moto)",
      "confirm.coords": "📍 Position exacte",
      "confirm.coordsApprox": "📍 Position approximative",
      "confirm.approxWarn": "⚠️ Position approximative : le GPS n'a pas été obtenu. Activez la localisation et renvoyez une alerte, ou précisez votre position au centre.",
      "confirm.coordsCopied": "Position copiée",
      "confirm.new": "Nouvelle alerte",
      "confirm.trackLater": "🔎 Suivre une alerte par référence",
      "confirm.assigned": "🚓 Votre alerte a été prise en charge.",
      "confirm.assignedAgent": "🚓 Un agent ({name}) a été affecté à votre alerte.",
      "confirm.resolved": "✅ Votre alerte a été traitée et clôturée. Merci.",

      "track.title": "Suivre une alerte",
      "track.sub": "Saisissez la référence reçue lors de votre signalement (ex. SC-K7P2Q9).",
      "track.see": "Voir l'état",
      "track.error": "Référence introuvable. Vérifiez la saisie.",
      "track.ref": "Référence",
      "track.type": "Type",
      "track.neighborhood": "Quartier",
      "track.agent": "Agent",
      "track.back": "← Retour",

      "step.received": "Alerte reçue",
      "step.assigned": "Prise en charge",
      "step.resolved": "Résolue",

      "typename.vol": "Vol",
      "typename.braquage": "Braquage",
      "typename.incendie": "Incendie",
      "typename.accident": "Accident",
      "typename.violence": "Violence",
      "typename.autre": "Autre",
    },
    sw: {
      "app.tagline": "Tahadhari ya dharura ya raia",
      "header.logout": "Toka",
      "lang.name": "Kiswahili",

      "auth.login": "Ingia",
      "auth.register": "Fungua akaunti",
      "auth.intro": "Karibu SafeCity. Fungua akaunti ili kutoa taarifa ya hatari, au ingia kama unayo tayari.",
      "auth.identifier": "📱 Simu au barua pepe",
      "auth.identifier.ph": "+243 … au wewe@mfano.com",
      "auth.password": "🔒 Nywila",
      "auth.password.ph": "Nywila yako",
      "auth.forgot": "Umesahau nywila?",
      "auth.noAccount": "Huna akaunti bado?",
      "auth.createOne": "Fungua moja",
      "auth.name": "👤 Jina kamili",
      "auth.name.ph": "Jina na jina la ukoo",
      "auth.phone": "📱 Namba ya simu",
      "auth.email": "✉️ Barua pepe (hiari)",
      "auth.email.ph": "wewe@mfano.com",
      "auth.emailHint": "Inasaidia kupata tena nywila yako ukisahau.",
      "auth.newPassword": "🔒 Nywila (angalau herufi 6)",
      "auth.newPassword.ph": "Chagua nywila",
      "auth.confirmPassword": "🔒 Thibitisha nywila",
      "auth.confirmPassword.ph": "Andika tena nywila",
      "auth.consent": "Nimesoma na nakubali",
      "auth.privacyPolicy": "sera ya faragha",
      "auth.consentEnd": "(ukusanyaji wa jina, simu, mahali na taarifa).",
      "auth.createMyAccount": "Fungua akaunti yangu",
      "auth.already": "Tayari umejisajili?",
      "auth.doLogin": "Ingia",
      "auth.forgotIntro": "🔑 Andika namba ya simu ya akaunti yako. Utapokea namba ya kubadilisha nywila kwa SMS.",
      "auth.sendCode": "Tuma namba",
      "auth.backToLogin": "← Rudi kwenye kuingia",

      "alert.intro": "Ukiwa hatarini, bonyeza kitufe. Mahali pako (GPS) patatumwa mara moja kwa kituo cha usalama.",
      "alert.button": "TAHADHARI",
      "alert.gps": "Inatafuta mahali…",
      "alert.legalHint": "⚖️ Tumia kitufe hiki tu wakati wa hatari halisi. Taarifa ya uongo inaadhibiwa na sheria.",
      "alert.privacy": "Faragha",
      "alert.deleteAccount": "Futa akaunti yangu",

      "details.title": "Maelezo ya tukio",
      "details.dangerType": "⚠️ Aina ya hatari",
      "type.vol": "🕵️ Wizi",
      "type.braquage": "🔫 Unyang'anyi",
      "type.incendie": "🔥 Moto",
      "type.accident": "🚗 Ajali",
      "type.violence": "👊 Vurugu",
      "type.autre": "❓ Nyingine",
      "details.yourName": "👤 Jina lako (hiari)",
      "details.yourName.ph": "Jina / jina la ukoo",
      "details.yourPhone": "📞 Simu (hiari)",
      "details.description": "📝 Maelezo (hiari)",
      "details.description.ph": "Eleza kwa ufupi hali ilivyo…",
      "details.photo": "📷 Picha",
      "details.voice": "🎤 Ujumbe wa sauti",
      "details.video": "🎬 Video",
      "details.neighborhood": "Mtaa",
      "details.position": "Mahali",
      "details.pickHint": "Gusa ramani kuonyesha mahali pako hasa (inasaidia kama GPS haifanyi kazi).",
      "details.manualSet": "Mahali pamewekwa kwa mkono",
      "details.useGps": "📍 Tumia mahali pangu pa GPS",
      "details.warningTitle": "Onyo:",
      "details.warning": " huduma hii ni kwa hali halisi tu. Taarifa ya uongo au ya udanganyifu inawasumbua waokoaji bure, inahatarisha maisha na ni kosa linaloadhibiwa na sheria. Kwa kutuma tahadhari hii, unathibitisha kuwa taarifa ulizotoa ni sahihi.",
      "details.cancel": "Ghairi",
      "details.send": "Tuma tahadhari 🚀",

      "confirm.title": "Tahadhari imetumwa",
      "confirm.sub": "Kituo cha usalama kimepokea taarifa yako.",
      "confirm.refLabel": "Namba yako ya kufuatilia",
      "confirm.refHint": "Iandike ili kufuatilia tahadhari yako, hata baada ya kufunga ukurasa.",
      "confirm.type": "Aina",
      "confirm.urgency": "Uharaka (AI)",
      "confirm.neighborhood": "Mtaa",
      "confirm.distance": "Umbali wa timu",
      "confirm.eta": "Muda wa kadirio (pikipiki)",
      "confirm.coords": "📍 Mahali kamili",
      "confirm.coordsApprox": "📍 Mahali pa kukadiria",
      "confirm.approxWarn": "⚠️ Mahali pa kukadiria: GPS haikupatikana. Washa mahali (location) kisha tuma tena tahadhari, au eleza mahali pako kwa kituo.",
      "confirm.coordsCopied": "Mahali pamenakiliwa",
      "confirm.new": "Tahadhari mpya",
      "confirm.trackLater": "🔎 Fuatilia tahadhari kwa namba",
      "confirm.assigned": "🚓 Tahadhari yako imeshughulikiwa.",
      "confirm.assignedAgent": "🚓 Askari ({name}) amepangwa kwa tahadhari yako.",
      "confirm.resolved": "✅ Tahadhari yako imeshughulikiwa na kufungwa. Asante.",

      "track.title": "Fuatilia tahadhari",
      "track.sub": "Andika namba uliyopokea wakati wa taarifa yako (mf. SC-K7P2Q9).",
      "track.see": "Ona hali",
      "track.error": "Namba haipatikani. Angalia ulivyoandika.",
      "track.ref": "Namba",
      "track.type": "Aina",
      "track.neighborhood": "Mtaa",
      "track.agent": "Askari",
      "track.back": "← Rudi",

      "step.received": "Tahadhari imepokewa",
      "step.assigned": "Imeshughulikiwa",
      "step.resolved": "Imemalizika",

      "typename.vol": "Wizi",
      "typename.braquage": "Unyang'anyi",
      "typename.incendie": "Moto",
      "typename.accident": "Ajali",
      "typename.violence": "Vurugu",
      "typename.autre": "Nyingine",
    },
  };

  // La langue démarre TOUJOURS en Français : elle n'est pas mémorisée entre les
  // ouvertures/rechargements (choix produit). Le bouton SW/FR permet de basculer
  // pendant la visite, mais chaque nouvelle ouverture repart en Français.
  var _lang = "fr";
  function current() {
    return _lang === "sw" ? "sw" : "fr";
  }
  function setLang(l) {
    _lang = l === "sw" ? "sw" : "fr";
    apply();
  }
  // Traduit une clé ; {name} etc. remplacés par vars. Repli : FR puis la clé.
  function t(key, vars) {
    var lang = current();
    var s = (STRINGS[lang] && STRINGS[lang][key]);
    if (s == null) s = STRINGS.fr[key];
    if (s == null) return key;
    if (vars) {
      Object.keys(vars).forEach(function (k) {
        s = s.replace("{" + k + "}", vars[k]);
      });
    }
    return s;
  }
  function apply() {
    var lang = current();
    document.documentElement.setAttribute("lang", lang);
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var v = t(el.getAttribute("data-i18n"));
      if (v != null) el.textContent = v;
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      var v = t(el.getAttribute("data-i18n-ph"));
      if (v != null) el.setAttribute("placeholder", v);
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      var v = t(el.getAttribute("data-i18n-title"));
      if (v != null) { el.setAttribute("title", v); el.setAttribute("aria-label", v); }
    });
    // Bascule visuelle du bouton de langue.
    var btn = document.getElementById("lang-toggle");
    if (btn) btn.textContent = lang === "sw" ? "FR" : "SW";
  }

  window.SafeCityI18n = { t: t, apply: apply, setLang: setLang, current: current };
  window.t = t;
  document.addEventListener("DOMContentLoaded", function () {
    apply();
    var btn = document.getElementById("lang-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        setLang(current() === "sw" ? "fr" : "sw");
      });
    }
  });
})();
