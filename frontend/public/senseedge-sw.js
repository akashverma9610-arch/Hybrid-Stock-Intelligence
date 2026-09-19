// Only public, non-financial fallback assets are cached. Never cache app HTML,
// API responses, private read models, credentials or portfolio information.
const CACHE = 'senseedge-public-offline-v1';
const PUBLIC_ASSETS = ['/offline.html', '/senseedge-icon.svg'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC_ASSETS)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('senseedge-public-offline-') && key !== CACHE).map(key => caches.delete(key)))));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // Everything outside this tiny allowlist passes straight to the browser network.
  // In particular, no API or authenticated cross-origin request is intercepted.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (!url.search && PUBLIC_ASSETS.includes(url.pathname)) {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(url.pathname)).then(response => response || fetch(event.request)));
    return;
  }
  if (event.request.mode === 'navigate' && url.pathname === '/' && !url.search) {
    event.respondWith(fetch(event.request).catch(() => caches.open(CACHE).then(cache => cache.match('/offline.html'))));
  }
});
