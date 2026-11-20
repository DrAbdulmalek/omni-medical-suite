// packages/core/mobile/static/service-worker.js
//
// Minimal PWA service worker for the OmniFile Mobile OCR Review app.
//
// Strategy:
//   - precache: the PWA shell (ocr-review.html) + manifest.json + a
//     fallback "offline" page so the user can launch the app even with
//     no network.
//   - runtime: network-first for /process, /save, /stats (always hit
//     network — these are dynamic and must not be served stale);
//     cache-first for static assets (/static/*, /mobile/*, images,
//     manifest).
//
// This is intentionally minimal — no Workbox, no complex routing. The
// goal is just enough offline support to satisfy PWA installability
// requirements and let users reopen the review page after the first
// visit.

const CACHE_NAME = "omnifile-mobile-v1";
const PRECACHE_URLS = [
    "/mobile/ocr-review.html",
    "/manifest.json",
    "/static/offline.html",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // Use addAll but tolerate individual failures (e.g. if
            // offline.html doesn't exist yet — it's a nice-to-have).
            return Promise.allSettled(
                PRECACHE_URLS.map((url) => cache.add(url))
            ).then(() => self.skipWaiting());
        })
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((k) => k !== CACHE_NAME)
                    .map((k) => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Never intercept non-GET requests (POST /save, POST /process, etc.
    // must always reach the server).
    if (req.method !== "GET") return;

    // Bypass cross-origin requests entirely.
    if (url.origin !== self.location.origin) return;

    // Dynamic endpoints — network-first, fall back to cache on offline.
    const DYNAMIC_PREFIXES = ["/process", "/save", "/load", "/stats", "/health"];
    if (DYNAMIC_PREFIXES.some((p) => url.pathname.startsWith(p))) {
        event.respondWith(
            fetch(req).catch(() => caches.match(req) || new Response(
                JSON.stringify({status: "offline", message: "no network"}),
                {headers: {"Content-Type": "application/json"}}
            ))
        );
        return;
    }

    // Static assets — cache-first, fall back to network.
    event.respondWith(
        caches.match(req).then((cached) =>
            cached || fetch(req).then((resp) => {
                // Cache a copy of successful same-origin responses.
                if (resp.ok && resp.type === "basic") {
                    const copy = resp.clone();
                    caches.open(CACHE_NAME).then((c) => c.put(req, copy));
                }
                return resp;
            }).catch(() => cached || caches.match("/static/offline.html"))
        )
    );
});
