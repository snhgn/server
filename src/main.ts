import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useAuth } from './stores/auth'
import './style.css'
import { registerSW } from 'virtual:pwa-register'

// 注册 PWA Service Worker 实现全站离线强缓存与 0ms 秒开
registerSW({ immediate: true })

// 启动即恢复登录状态（HttpOnly Cookie → GET /api/auth/me）；不阻塞渲染，
// 受保护路由由守卫 await init() 等待结果后再放行
useAuth().init()

createApp(App).use(router).mount('#app')
