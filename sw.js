self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  return self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Leitet Anfragen normal an das Netzwerk weiter (wichtig für WebSockets & Audio)
  e.respondWith(fetch(e.request));
});