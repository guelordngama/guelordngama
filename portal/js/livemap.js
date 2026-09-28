/* SafeCity — carte en temps réel du portail agents.
 * Même système visuel que la carte du poste opérateur : alertes (pulsation
 * tant qu'elles sont en attente), citoyens, agents disponibles / en
 * intervention, trajets, quartier et rue, précision GPS.
 *
 *   const live = LiveMap(map, { selfId, onAccept(id), onLocate(id) });
 *   live.setAlerts(list); live.setAgents(list); live.setSelf([lat,lng], acc);
 *   live.setMyRoute(alertId, route); live.focusAlert(id); live.fitAll();
 */
(function () {
  "use strict";
  var URGENCY = { faible: "#22c55e", moyenne: "#eab308", haute: "#f97316", critique: "#ef4444" };
  var URG_LABEL = { faible: "Faible", moyenne: "Moyen", haute: "Élevé", critique: "Critique" };
  var TYPE_NAMES = { vol: "Vol", braquage: "Braquage", incendie: "Incendie", accident: "Accident",
                     violence: "Violence", agression: "Agression", autre: "Autre" };
  var STATUS = { active: ["EN ATTENTE", "#ef4444"], assignee: ["EN COURS", "#f97316"],
                 cloturee: ["TRAITÉ", "#16a34a"] };
  // N° d'intervention « SC-2026-0048 » (repli : code de suivi).
  function num(a) { return a.incident_number || a.reference || String(a.id); }
  var AVAIL = { available: ["Disponible", "#16a34a"], busy: ["En intervention", "#f97316"],
                offline: ["Hors service", "#64748b"] };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  }
  function gps(lat, lng) { return lat == null ? "—" : (+lat).toFixed(6) + ", " + (+lng).toFixed(6); }
  function dist(a, b) {
    var R = 6371000, r = Math.PI / 180, dLat = (b[0] - a[0]) * r, dLng = (b[1] - a[1]) * r;
    var x = Math.pow(Math.sin(dLat / 2), 2) + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.pow(Math.sin(dLng / 2), 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  function km(m) { return m < 1000 ? Math.round(m) + " m" : (m / 1000).toFixed(1).replace(".", ",") + " km"; }
  function mins(s) { return Math.max(1, Math.round(s / 60)) + " min"; }
  function initials(name) {
    var p = String(name || "").split(/\s+/).filter(Boolean);
    if (!p.length) return "?";
    var b = p[1] ? (/^\d+$/.test(p[1]) ? (p[1].replace(/^0+/, "")[0] || p[1].slice(-1)) : p[1][0]) : "";
    return (p[0][0] + b).toUpperCase();
  }
  function streetParts(street) {
    var s = String(street || "").trim(), low = s.toLowerCase();
    var kinds = [[["avenue ", "av. ", "av "], "Avenue"], [["rue "], "Rue"], [["boulevard ", "bd "], "Boulevard"],
                 [["route "], "Route"], [["chaussée "], "Chaussée"]];
    for (var i = 0; i < kinds.length; i++) for (var j = 0; j < kinds[i][0].length; j++)
      if (low.indexOf(kinds[i][0][j]) === 0) return [kinds[i][1], s.slice(kinds[i][0][j].length).trim() || s];
    return ["Avenue / Rue", s];
  }
  function placeLine(a) {
    var st = a.street ? streetParts(a.street) : null, parts = [];
    if (st) parts.push((st[0] === "Avenue / Rue" ? "" : st[0] + " ") + st[1]);
    if (a.neighborhood) parts.push(a.neighborhood);
    var s = parts.join(", ");
    if (a.commune) s += (s ? " — " : "") + "commune " + a.commune;
    return s || (a.position_approx ? "Position approximative" : "Adresse en cours de recherche…");
  }
  function precision(a) {
    if (a.position_approx) return "⚠️ Approximative";
    if (a.position_manual) return "Placée à la main";
    return a.gps_accuracy_m != null ? "±" + Math.round(a.gps_accuracy_m) + " m" : "Non communiquée";
  }
  function ageMin(iso) {
    if (!iso) return null;
    var t = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
    return isNaN(t) ? null : Math.round((Date.now() - t) / 60000);
  }

  window.LiveMap = function (map, opts) {
    opts = opts || {};
    var alerts = {}, agents = {}, self = null, selfAcc = null, myRoute = null, myRouteFor = null;

    var L_ALERTS = L.layerGroup().addTo(map), L_CITIZENS = L.layerGroup().addTo(map),
        L_FREE = L.layerGroup().addTo(map), L_BUSY = L.layerGroup().addTo(map),
        L_ROUTES = L.layerGroup().addTo(map), L_ACC = L.layerGroup().addTo(map),
        L_ME = L.layerGroup().addTo(map);
    var LAYERS = [["🚨 Alertes", L_ALERTS], ["👤 Citoyens", L_CITIZENS], ["🟢 Agents disponibles", L_FREE],
                  ["🟠 Agents en intervention", L_BUSY], ["🧭 Trajets", L_ROUTES], ["◎ Précision GPS", L_ACC]];

    // ---- Contrôle : compteurs + couches (repliable, pratique sur téléphone) ----
    var ctl = L.control({ position: "topright" }), box;
    ctl.onAdd = function () {
      box = L.DomUtil.create("div", "lm-ctl");
      var html = '<button type="button" class="lm-toggle" title="Compteurs et couches">☰ <span>Carte en direct</span>' +
        '<i class="lm-live"></i></button><div class="lm-body"><div class="lm-counters">' +
        '<div><b id="lm-wait" style="color:#ef4444">0</b><span>En attente</span></div>' +
        '<div><b id="lm-prog" style="color:#f97316">0</b><span>En intervention</span></div>' +
        '<div><b id="lm-free" style="color:#16a34a">0</b><span>Agents dispo</span></div>' +
        '<div><b id="lm-busy" style="color:#f97316">0</b><span>Agents occupés</span></div></div><div class="lm-layers">';
      LAYERS.forEach(function (l, i) {
        html += '<label><input type="checkbox" checked data-i="' + i + '"> ' + l[0] + "</label>";
      });
      html += '</div><button type="button" class="lm-fit">⤢ Tout afficher</button></div>';
      box.innerHTML = html;
      L.DomEvent.disableClickPropagation(box);
      L.DomEvent.disableScrollPropagation(box);
      if (window.matchMedia && window.matchMedia("(max-width: 820px)").matches) box.classList.add("collapsed");
      box.querySelector(".lm-toggle").onclick = function () { box.classList.toggle("collapsed"); };
      box.querySelector(".lm-fit").onclick = function () { api.fitAll(); };
      box.addEventListener("change", function (e) {
        var l = LAYERS[+e.target.dataset.i][1];
        if (e.target.checked) map.addLayer(l); else map.removeLayer(l);
      });
      return box;
    };
    ctl.addTo(map);

    // ---- Actions des fiches (capture : avant que Leaflet ne bloque le clic) ----
    map.getContainer().addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("[data-lm]");
      if (!b) return;
      e.preventDefault();
      e.stopPropagation();
      var parts = b.getAttribute("data-lm").split(":"), id = +parts[1];
      if (parts[0] === "accept" && opts.onAccept) opts.onAccept(id);
      if (parts[0] === "locate" && opts.onLocate) opts.onLocate(id);
    }, true);

    function isMine(a) { return a.assigned_agent && a.assigned_agent.id === opts.selfId; }

    function alertIcon(a) {
      var c = URGENCY[a.urgency] || "#ef4444";
      var ring = a.status === "active" ? '<div class="ring" style="border-color:' + c + '"></div>' : "";
      var mine = isMine(a) ? " mine" : "";
      return L.divIcon({ className: "", iconSize: [22, 22], iconAnchor: [11, 11], popupAnchor: [0, -10],
        html: '<div class="lm-alert' + mine + '">' + ring + '<div class="core" style="background:' + c + '"></div></div>' });
    }
    function citizenIcon(a) {
      return L.divIcon({ className: "", iconSize: null, iconAnchor: [-14, 30],
        html: '<div class="lm-label">👤 ' + esc(a.reporter_name || "Citoyen") + "</div>" });
    }
    function agentIcon(g) {
      var st = AVAIL[g.availability] || AVAIL.offline;
      var stale = (ageMin(g.last_seen) || 0) > 10 ? " stale" : "";
      return L.divIcon({ className: "", iconSize: null, iconAnchor: [14, 13], popupAnchor: [0, -12],
        html: '<div class="lm-label lm-agent' + stale + '" style="border-color:' + st[1] + '"><span class="av" style="background:' +
              st[1] + '">' + esc(initials(g.name)) + "</span>👮 " + esc(g.name) + "</div>" });
    }
    var meIcon = L.divIcon({ className: "", iconSize: null, iconAnchor: [14, 13], popupAnchor: [0, -12],
      html: '<div class="lm-label lm-me"><span class="av">🚓</span>Moi</div>' });

    function alertFiche(a) {
      var st = STATUS[a.status] || [String(a.status || "—").toUpperCase(), "#64748b"];
      var sp = streetParts(a.street), r = myRouteFor === a.id ? myRoute : null;
      var rows = [
        ["Type", esc(TYPE_NAMES[a.type] || a.type || "—") + " · " + (URG_LABEL[a.urgency] || "")],
        ["Citoyen", esc(a.reporter_name || "Anonyme")],
        ["Téléphone", a.reporter_phone ? '<a href="tel:' + esc(a.reporter_phone) + '">📞 ' + esc(a.reporter_phone) + "</a>" : "Non communiqué"],
        ["Commune", esc(a.commune || "—")], [sp[0], esc(sp[1] || "—")],
        ["Quartier", esc(a.neighborhood || "—")], ["Ville", esc(a.city || "—")],
        ["GPS", gps(a.lat, a.lng)], ["Précision", esc(precision(a))], ["Heure", esc(a.time || "—")],
        ["Statut", '<span style="color:' + st[1] + '">' + st[0] + "</span>"]];
      if (a.assigned_agent) rows.push(["Agent", "👮 " + esc(isMine(a) ? "Moi (" + a.assigned_agent.name + ")" : a.assigned_agent.name) +
                                       " → Intervention #" + esc(num(a))]);
      if (r) rows.push(["Mon trajet", km(r.distance_m) + " · " + mins(r.duration_s) + (r.source === "direct" ? " (estimé)" : "")]);
      else if (self) rows.push(["Distance", km(dist(self, [a.lat, a.lng])) + " de vous (vol d'oiseau)"]);
      var html = '<div class="lm-fiche"><h3>' + (a.status === "active" ? "🔴 " : "🟠 ") +
        esc((TYPE_NAMES[a.type] || a.type || "").toUpperCase()) + " #" + esc(num(a)) + "</h3><table>";
      rows.forEach(function (x) {
        html += "<tr" + (x[0] === "GPS" ? ' class="sep"' : "") + "><td>" + esc(x[0]) + " :</td><td>" + x[1] + "</td></tr>";
      });
      html += '</table><div class="acts">';
      if (a.status === "active") html += '<a href="#" class="lm-btn primary" data-lm="accept:' + a.id + '">✅ Accepter la mission</a>';
      html += '<a class="lm-btn" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=' +
              a.lat + "," + a.lng + '">🧭 Google Maps</a></div></div>';
      return html;
    }
    function agentFiche(g) {
      var st = AVAIL[g.availability] || AVAIL.offline, a = g.current_alert_id != null ? alerts[g.current_alert_id] : null;
      var age = ageMin(g.last_seen);
      var html = '<div class="lm-fiche"><h3>👮 ' + esc(g.name) + "</h3><table>" +
        '<tr><td>Statut :</td><td><span style="color:' + st[1] + '">' + st[0] + "</span></td></tr>" +
        "<tr><td>Position :</td><td>" + (age == null ? "—" : age < 1 ? "à l'instant" : "il y a " + age + " min") + "</td></tr>";
      if (self) html += "<tr><td>Distance :</td><td>" + km(dist(self, [g.lat, g.lng])) + " de vous</td></tr>";
      if (a) html += '<tr class="sep"><td>Intervention :</td><td>#' + esc(num(a)) + " · " + esc(TYPE_NAMES[a.type] || a.type) +
        "</td></tr><tr><td>Lieu :</td><td>" + esc(placeLine(a)) + "</td></tr>";
      return html + "</table></div>";
    }

    var mAlert = {}, mCitizen = {}, mAcc = {}, mAgent = {}, mMe = null, mMeAcc = null;
    // Marges de recentrage des fiches : ne jamais passer sous le panneau des
    // compteurs (en haut à droite) ni sortir de la carte.
    function popupOpts() {
      var open = box && !box.classList.contains("collapsed");
      return { maxWidth: 300, autoPan: true, autoPanPaddingTopLeft: L.point(16, 16),
               autoPanPaddingBottomRight: L.point(open ? 275 : 16, 16) };
    }
    function upsert(store, id, ll, icon, layer, popup) {
      var m = store[id];
      if (!m) { m = L.marker(ll, { icon: icon, riseOnHover: true }).addTo(layer); if (popup) m.bindPopup(popup, popupOpts()); store[id] = m; }
      else { m.setLatLng(ll); m.setIcon(icon); if (popup) m.setPopupContent(popup); }
      return m;
    }
    function prune(store, keep, layers) {
      Object.keys(store).forEach(function (k) {
        if (!keep[k]) { layers.forEach(function (l) { l.removeLayer(store[k]); }); delete store[k]; }
      });
    }

    function render() {
      var keepA = {}, keepG = {}, nWait = 0, nProg = 0, nFree = 0, nBusy = 0;
      Object.keys(alerts).forEach(function (k) {
        var a = alerts[k];
        if (a.status === "cloturee") return;
        keepA[k] = true;
        if (a.status === "active") nWait++; else nProg++;
        var ll = [a.lat, a.lng];
        var m = upsert(mAlert, k, ll, alertIcon(a), L_ALERTS, alertFiche(a));
        m.setZIndexOffset(a.status === "active" ? 1000 : 500);
        upsert(mCitizen, k, ll, citizenIcon(a), L_CITIZENS, alertFiche(a));
        var acc = a.position_approx ? 800 : a.gps_accuracy_m;
        if (acc) {
          if (!mAcc[k]) mAcc[k] = L.circle(ll, { radius: acc, color: URGENCY[a.urgency] || "#ef4444", weight: 1,
                                                 fillOpacity: 0.08, dashArray: a.position_approx ? "6,6" : null }).addTo(L_ACC);
          else { mAcc[k].setLatLng(ll); mAcc[k].setRadius(acc); }
        } else if (mAcc[k]) { L_ACC.removeLayer(mAcc[k]); delete mAcc[k]; }
      });
      prune(mAlert, keepA, [L_ALERTS]); prune(mCitizen, keepA, [L_CITIZENS]); prune(mAcc, keepA, [L_ACC]);

      Object.keys(agents).forEach(function (k) {
        var g = agents[k];
        if (g.availability === "available") nFree++; else if (g.availability === "busy") nBusy++;
        if (+k === opts.selfId || g.lat == null || g.lng == null || g.availability === "offline") return;
        keepG[k] = true;
        var layer = g.availability === "busy" ? L_BUSY : L_FREE, m = mAgent[k];
        if (m && !layer.hasLayer(m)) { L_FREE.removeLayer(m); L_BUSY.removeLayer(m); layer.addLayer(m); }
        upsert(mAgent, k, [g.lat, g.lng], agentIcon(g), layer, agentFiche(g));
      });
      prune(mAgent, keepG, [L_FREE, L_BUSY]);

      if (self) {
        if (!mMe) mMe = L.marker(self, { icon: meIcon, zIndexOffset: 2000 }).addTo(L_ME).bindPopup("🚓 Ma position");
        else mMe.setLatLng(self);
        if (selfAcc) {
          if (!mMeAcc) mMeAcc = L.circle(self, { radius: selfAcc, color: "#2563eb", weight: 1, fillOpacity: 0.07 }).addTo(L_ME);
          else { mMeAcc.setLatLng(self); mMeAcc.setRadius(selfAcc); }
        }
      }
      drawRoutes();

      if (box) {
        box.querySelector("#lm-wait").textContent = nWait;
        box.querySelector("#lm-prog").textContent = nProg;
        box.querySelector("#lm-free").textContent = nFree;
        box.querySelector("#lm-busy").textContent = nBusy;
      }
    }

    function drawRoutes() {
      L_ROUTES.clearLayers();
      // Mon trajet (calculé par le serveur) : trait plein bleu.
      if (myRoute && myRoute.coordinates && myRoute.coordinates.length > 1 && alerts[myRouteFor]) {
        L.polyline(myRoute.coordinates, { color: "#fff", weight: 9, opacity: 0.9 }).addTo(L_ROUTES);
        L.polyline(myRoute.coordinates, { color: "#2563eb", weight: 6, opacity: 0.95,
                                         dashArray: myRoute.source === "direct" ? "8,8" : null })
          .bindTooltip("🧭 Mon trajet → Intervention #" + esc(num(alerts[myRouteFor])) + " · " + km(myRoute.distance_m) + " · " + mins(myRoute.duration_s) +
                       (myRoute.source === "direct" ? " (estimé)" : ""), { permanent: true, direction: "center", className: "lm-route-label" })
          .addTo(L_ROUTES);
      }
      // Collègues en intervention : ligne pointillée orange vers leur alerte.
      Object.keys(agents).forEach(function (k) {
        var g = agents[k], a = g.current_alert_id != null ? alerts[g.current_alert_id] : null;
        if (+k === opts.selfId || !a || a.status !== "assignee" || g.lat == null) return;
        L.polyline([[g.lat, g.lng], [a.lat, a.lng]], { color: "#f97316", weight: 3, dashArray: "6,8", opacity: 0.9 })
          .bindTooltip("👮 " + esc(g.name) + " → Intervention #" + esc(num(a)) + " · " + km(dist([g.lat, g.lng], [a.lat, a.lng])),
                       { sticky: true }).addTo(L_ROUTES);
      });
    }

    var timer = null;
    function schedule() { clearTimeout(timer); timer = setTimeout(render, 60); }

    var api = {
      setAlerts: function (list) { alerts = {}; (list || []).forEach(function (a) { alerts[a.id] = a; }); schedule(); },
      setAgents: function (list) { agents = {}; (list || []).forEach(function (g) { agents[g.id] = g; }); schedule(); },
      upsertAgent: function (g) { if (g && g.id != null) { agents[g.id] = Object.assign(agents[g.id] || {}, g); schedule(); } },
      removeAgent: function (id) { delete agents[id]; schedule(); },
      setSelf: function (pos, acc) { self = pos; selfAcc = acc || null; schedule(); },
      setMyRoute: function (alertId, route) { myRouteFor = route ? alertId : null; myRoute = route || null; schedule(); },
      focusAlert: function (id) {
        render();
        var m = mAlert[id];
        if (!m) return;
        // Sans animation : la fiche s'ouvre ensuite correctement cadrée.
        if (myRouteFor === id && myRoute && myRoute.coordinates.length > 1)
          map.fitBounds(L.latLngBounds(myRoute.coordinates), { padding: [50, 50], maxZoom: 17, animate: false });
        else map.setView(m.getLatLng(), 16, { animate: false });
        var po = m.getPopup();
        if (po) L.setOptions(po, popupOpts());
        m.openPopup();
      },
      fitAll: function () {
        var pts = [];
        Object.keys(mAlert).forEach(function (k) { pts.push(mAlert[k].getLatLng()); });
        Object.keys(mAgent).forEach(function (k) { pts.push(mAgent[k].getLatLng()); });
        if (self) pts.push(L.latLng(self));
        if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [50, 50], maxZoom: 16 });
      },
    };
    return api;
  };
})();
