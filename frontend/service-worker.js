const CACHE_NAME = "aida-shell-v3";
const SHELL_FILES = [
  "/",
  "/css/styles.css",
  "/js/app.js",
  "/manifest.json",
  "/vendor/katex/katex.min.css",
  "/vendor/katex/katex.min.js",
  "/vendor/katex/auto-render.min.js",
  "/vendor/marked/marked.min.js",
  "/vendor/dompurify/purify.min.js",
  "/vendor/katex/fonts/KaTeX_AMS-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Caligraphic-Bold.woff2",
  "/vendor/katex/fonts/KaTeX_Caligraphic-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Fraktur-Bold.woff2",
  "/vendor/katex/fonts/KaTeX_Fraktur-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Main-Bold.woff2",
  "/vendor/katex/fonts/KaTeX_Main-BoldItalic.woff2",
  "/vendor/katex/fonts/KaTeX_Main-Italic.woff2",
  "/vendor/katex/fonts/KaTeX_Main-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Math-BoldItalic.woff2",
  "/vendor/katex/fonts/KaTeX_Math-Italic.woff2",
  "/vendor/katex/fonts/KaTeX_SansSerif-Bold.woff2",
  "/vendor/katex/fonts/KaTeX_SansSerif-Italic.woff2",
  "/vendor/katex/fonts/KaTeX_SansSerif-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Script-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Size1-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Size2-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Size3-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Size4-Regular.woff2",
  "/vendor/katex/fonts/KaTeX_Typewriter-Regular.woff2",
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

// GET /api/curriculum est mis en cache pour rester consultable hors-ligne
// (faiblesse #5 : cout des donnees en Afrique de l'Ouest). Les appels IA
// (POST /api/ask, /api/upload-exercice, /api/report) ont besoin du reseau a
// chaque fois et ne sont jamais mis en cache.
const CACHEABLE_API_GET = [/^\/api\/curriculum$/];

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
