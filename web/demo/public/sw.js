const SHELL_CACHE = "uttg-demo-shell-v3";
const DATA_CACHE = "uttg-demo-data-v3";
const SHELL = ["/", "/index.html", "/textures/earth-blue-marble.jpg", "/textures/earth-topology.png", "/favicon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => ![SHELL_CACHE, DATA_CACHE].includes(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/v1/")) {
    event.respondWith(networkFirst(event.request, DATA_CACHE));
  } else if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/textures/")) {
    event.respondWith(cacheFirst(event.request));
  } else if (event.request.mode === "navigate") {
    event.respondWith(networkFirst(new Request("/index.html"), SHELL_CACHE));
  }
});
