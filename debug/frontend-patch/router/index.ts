import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // ---- Guest 公开页面 ----
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('@/views/ProjectsView.vue'),
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/views/AboutView.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },

    // ---- User 页面（需要登录：user 或 admin）----
    {
      path: '/ai',
      name: 'ai',
      component: () => import('@/views/AiView.vue'),
      meta: { requiresAuth: true, role: 'user', fullScreen: true },
    },
    {
      path: '/scripts',
      name: 'scripts',
      component: () => import('@/views/ScriptsView.vue'),
      meta: { requiresAuth: true, role: 'user' },
    },
    {
      path: '/schedule',
      name: 'schedule',
      component: () => import('@/views/ScheduleView.vue'),
      meta: { requiresAuth: true, role: 'user' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { requiresAuth: true, role: 'user' },
    },

    // ---- Admin 页面 ----
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('@/views/KnowledgeView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/server',
      name: 'server',
      component: () => import('@/views/ServerView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/admin/scripts',
      name: 'admin-scripts',
      component: () => import('@/views/AdminScriptsView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },

    // ---- 旧路径重定向（兼容书签）----
    { path: '/dashboard/ai', redirect: '/ai' },
    { path: '/dashboard/scripts', redirect: '/scripts' },
    { path: '/dashboard/schedule', redirect: '/schedule' },

    // ---- 404 ----
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const { isAuthenticated, isAdmin, isUser, authReady, init } = useAuth()

  if (!to.meta.requiresAuth) {
    // 登录页：等状态恢复后再判断，已登录则跳首页（其他公开页不阻塞渲染）
    if (to.name === 'login') {
      if (!authReady.value) await init()
      if (isAuthenticated.value) {
        next('/')
        return
      }
    }
    next()
    return
  }

  // 需要登录：若登录状态还在恢复中（GET /api/auth/me 未返回），先等待，
  // 避免页面闪现"未登录"后被弹回登录页
  if (!authReady.value) {
    await init()
  }

  if (!isAuthenticated.value) {
    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }

  // 检查角色
  const requiredRole = to.meta.role as string
  if (requiredRole === 'admin' && !isAdmin.value) {
    next('/') // 普通用户访问 admin 页面，跳首页
    return
  }
  // user 路由：admin 也能访问
  if (requiredRole === 'user' && !isUser.value) {
    next({ name: 'login' })
    return
  }

  next()
})

export default router
