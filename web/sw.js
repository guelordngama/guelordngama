/* Service Worker SafeCity — met en cache la coquille de l'app pour un
 * fonctionnement hors-ligne (chargement de la page sans réseau). */
const CACHE = "safecity-v1";
const SHELL = [
  "./",
  "./index.html",
  "./css/style.css",
  "./js/config.js",
  "./js/app.js",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  // Ne jamais mettre en cache les appels API (toujours réseau).
  if (req.method !== "GET" || req.url.includes("/api/")) return;
  // Cache-first pour la coquille, avec repli réseau.
  e.respondWith(
    caches.match(req).then((cached) => cached || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      return res;
    }).catch(() => cached))
  );
});
