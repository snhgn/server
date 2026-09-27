import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useAuth } from './stores/auth'
import './style.css'
import { initTheme } from './utils/theme'

initTheme()

// 彻底清除并注销所有历史 Service Worker 与 CacheStorage 缓存，彻底告别 PWA 缓存延迟
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((registrations) => {
    for (const registration of registrations) {
      registration.unregister()
    }
  })
}
if (typeof caches !== 'undefined') {
  caches.keys().then((names) => {
    for (const name of names) {
      caches.delete(name)
    }
  })
}

// 启动即恢复登录状态（HttpOnly Cookie → GET /api/auth/me）；不阻塞渲染，
// 受保护路由由守卫 await init() 等待结果后再放行
useAuth().init()

createApp(App).use(router).mount('#app')

