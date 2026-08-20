/* Offline app-shell cache. Bump CACHE on each release so clients update. */
const CACHE = "aahl-scoresheet-v1";
const SHELL = ["./", "index.html", "app.js", "styles.css", "manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Never cache API calls — they must hit the proxy (and fail loudly when offline).
  if (url.pathname.startsWith("/api/")) return;
  // Cache-first for the app shell so it loads with no signal at the rink.
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
