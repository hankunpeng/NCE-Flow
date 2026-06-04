/**
 * NCE Flow Service Worker
 * 缓存策略：核心文件缓存优先，音频网络优先
 */

const CACHE_NAME = 'nce-flow-v1.8.0-sync1';

// 核心静态资源（预缓存）
const PRECACHE_ASSETS = [
  './',
  './index.html',
  './lesson.html',
  './favorites.html',
  './book.html',
  './about.html',
  './manifest.json',
  './favicon.ico',
  './assets/styles.css',
  './assets/utils.js',
  './assets/lesson.js',
  './assets/app.js',
  './assets/favorites.js',
  './assets/search.js',
  './assets/storage.js',
  './static/data.json',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon.ico'
];

// 安装：预缓存核心资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        const requests = PRECACHE_ASSETS.map((url) => new Request(url, { cache: 'reload' }));
        return cache.addAll(requests);
      })
      .then(() => self.skipWaiting())
  );
});

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// 接收页面消息（用于跳过等待）
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

const cacheResponse = (cache, request, response) => {
  if (!response || !response.ok || request.method !== 'GET') {
    return;
  }
  cache.put(request, response.clone());
};

const offlineResponse = () => new Response('离线不可用', {
  status: 503,
  headers: { 'Content-Type': 'text/plain; charset=utf-8' }
});

// 请求拦截
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 只处理同源请求
  if (url.origin !== location.origin) {
    return;
  }

  // 后端同步接口：始终走网络，绝不缓存（含 POST），避免读到陈旧数据
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  if (request.method !== 'GET') {
    return;
  }

  // 音频文件：网络优先（不缓存）
  if (url.pathname.endsWith('.mp3')) {
    event.respondWith(
      fetch(request).catch(() => {
        // 离线时返回友好提示（可选）
        return new Response('音频需要联网播放', { status: 503 });
      })
    );
    return;
  }

  // LRC 文件：网络优先，失败时用缓存
  if (url.pathname.endsWith('.lrc')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // 成功获取后更新缓存
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  const acceptHeader = request.headers.get('accept') || '';
  const isHTML = request.mode === 'navigate' || acceptHeader.includes('text/html');

  // 页面请求：网络优先，离线时回退缓存
  if (isHTML) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      try {
        const response = await fetch(request);
        cacheResponse(cache, request, response);
        return response;
      } catch (error) {
        const cachedResponse = await cache.match(request);
        return cachedResponse || offlineResponse();
      }
    })());
    return;
  }

  // 其他资源：Stale-While-Revalidate
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cachedResponse = await cache.match(request);
    const fetchPromise = fetch(request)
      .then((response) => {
        cacheResponse(cache, request, response);
        return response;
      })
      .catch(() => null);

    if (cachedResponse) {
      event.waitUntil(fetchPromise);
      return cachedResponse;
    }

    const networkResponse = await fetchPromise;
    return networkResponse || offlineResponse();
  })());
});
