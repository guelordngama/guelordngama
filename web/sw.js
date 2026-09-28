/* Service Worker SafeCity — met en cache la coquille de l'app pour un
 * fonctionnement hors-ligne (chargement de la page sans réseau).
 *
 * Stratégie RÉSEAU D'ABORD : en ligne, on sert toujours la dernière version
 * publiée (mises à jour visibles immédiatement, sans Ctrl+F5) ; le cache ne sert
 * qu'en repli hors-ligne. Changer CACHE purge les anciennes copies.
 */
const CACHE = "safecity-v2";
const SHELL = [
  "./",
  "./index.html",
  "./css/style.css",
  "./js/config.js",
  "./js/i18n.js",
  "./js/shell.js",
  "./js/app.js",
  "./vendor/leaflet/leaflet.css",
  "./vendor/leaflet/leaflet.js",
  "./vendor/socket.io.min.js",
  "./manifest.json",
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
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Hors coquille : API, temps réel, tuiles de carte et pièces jointes passent
  // directement par le réseau (les tuiles ont leur propre cache HTTP ; les
  // mettre ici ferait grossir le stockage sans limite).
  if (url.origin !== self.location.origin) return;
  if (/\/(api|socket\.io|tiles|uploads)\//.test(url.pathname)) return;

  e.respondWith(
    fetch(req).then((res) => {
      if (res && res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match(req).then((cached) => cached || caches.match("./index.html")))
  );
});
