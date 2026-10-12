// Service worker du portail agents SafeCity : notifications push (écran verrouillé).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) {}
  event.waitUntil(self.registration.showNotification(d.title || "SafeCity", {
    body: d.body || "Nouvelle mission.",
    tag: d.tag || "safecity",
    renotify: true,
    requireInteraction: true,
    vibrate: [300, 150, 300, 150, 600],
    icon: "icon.svg",
    badge: "icon.svg",
    data: { url: d.url || "/portal/" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/portal/";
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    for (const c of list) {
      if (c.url.includes("/portal/") && "focus" in c) return c.focus();
    }
    return self.clients.openWindow(url);
  }));
});
