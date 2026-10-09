// 위판 당직 서비스 워커: 웹 푸시 수신과 알림 클릭 처리.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let data = { title: '위판 당직', body: '새 입항 예보가 있습니다.', url: '/' }
  try { data = { ...data, ...event.data.json() } } catch (err) { console.error('푸시 내용 해석 실패', err) }
  event.waitUntil(self.registration.showNotification(data.title, {
    body: data.body, icon: '/icon.svg', badge: '/icon.svg', data: { url: data.url }, tag: 'wipan', renotify: true,
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data?.url || '/'
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ('focus' in c) return c.focus() }
    return self.clients.openWindow(url)
  }))
})
