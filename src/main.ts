import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useAuth } from './stores/auth'
import './style.css'
import { registerSW } from 'virtual:pwa-register'

// 发布版本标识（老设备检测到新版本时主动清空旧 CacheStorage、注销旧 SW 并重载以拉取最新界面）
export const APP_VERSION = 'v1.4.0'
const storedVersion = localStorage.getItem('app_version')

const isOldInstallation =
  storedVersion !== APP_VERSION && (!!storedVersion || !!navigator.serviceWorker?.controller)

if (isOldInstallation) {
  localStorage.setItem('app_version', APP_VERSION)
  const cleanAndReload = async () => {
    if (typeof caches !== 'undefined') {
      try {
        const names = await caches.keys()
        await Promise.all(names.map((name) => caches.delete(name)))
      } catch {}
    }
    if ('serviceWorker' in navigator) {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations()
        await Promise.all(registrations.map((r) => r.unregister()))
      } catch {}
    }
    window.location.reload()
  }
  cleanAndReload()
} else {
  localStorage.setItem('app_version', APP_VERSION)
}

// 注册 PWA Service Worker 并开启即时接管与刷新
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh() {
    updateSW(true)
  },
  onRegisteredSW(_swScriptUrl, registration) {
    if (registration) {
      registration.update()
      setInterval(() => {
        registration.update()
      }, 30 * 1000)
    }
  },
})

// 启动即恢复登录状态（HttpOnly Cookie → GET /api/auth/me）；不阻塞渲染，
// 受保护路由由守卫 await init() 等待结果后再放行
useAuth().init()

createApp(App).use(router).mount('#app')

