// Self-destructing Service Worker to eliminate old PWA caches and unregister
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // 1. Unregister this service worker
      try {
        await self.registration.unregister();
      } catch (e) {}

      // 2. Clear all cache storages
      if (typeof caches !== 'undefined') {
        try {
          const keys = await caches.keys();
          await Promise.all(keys.map((k) => caches.delete(k)));
        } catch (e) {}
      }

      // 3. Force reload all active window clients so they fetch fresh files
      try {
        const clients = await self.clients.matchAll({ type: 'window' });
        for (const client of clients) {
          if (client.url && 'navigate' in client) {
            client.navigate(client.url);
          }
        }
      } catch (e) {}
    })()
  );
});
