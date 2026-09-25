import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useAuth } from './stores/auth'
import './style.css'
import { registerSW } from 'virtual:pwa-register'

// 发布版本标识（老设备检测到新版本时主动清空旧 CacheStorage 并拉取最新 Service Worker）
export const APP_VERSION = 'v1.1.0'
const storedVersion = localStorage.getItem('app_version')
if (storedVersion && storedVersion !== APP_VERSION) {
  if ('caches' in window) {
    caches.keys().then((names) => {
      names.forEach((name) => caches.delete(name))
    })
  }
}
localStorage.setItem('app_version', APP_VERSION)

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
      }, 60 * 1000)
    }
  },
})

// 启动即恢复登录状态（HttpOnly Cookie → GET /api/auth/me）；不阻塞渲染，
// 受保护路由由守卫 await init() 等待结果后再放行
useAuth().init()

createApp(App).use(router).mount('#app')

