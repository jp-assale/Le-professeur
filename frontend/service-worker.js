const CACHE_NAME = "aida-shell-v1";
const SHELL_FILES = [
  "/",
  "/css/styles.css",
  "/js/app.js",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// GET /api/curriculum et /api/epreuves(/:id) sont mis en cache pour rester
// consultables hors-ligne (faiblesse #5 : cout des donnees en Afrique de
// l'Ouest). Les appels IA (POST /api/ask, /api/upload-exercice, /api/report)
// ont besoin du reseau a chaque fois et ne sont jamais mis en cache.
const CACHEABLE_API_GET = [/^\/api\/curriculum$/, /^\/api\/epreuves(\/.*)?$/];

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== "GET") return;

  const isApi = url.pathname.startsWith("/api/");
  const isCacheableApi = CACHEABLE_API_GET.some((re) => re.test(url.pathname));
  if (isApi && !isCacheableApi) return;

  // Reseau prioritaire pour voir un redeploiement immediatement, secours par
  // le cache (shell statique ou dernier contenu vu) si hors-ligne.
  event.respondWith(
    fetch(req)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return response;
      })
      .catch(() => caches.match(req))
  );
});
