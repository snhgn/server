<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'
import BrandWordmark from '@/components/BrandWordmark.vue'

const { isAuthenticated, isAdmin, isUser, username, role, logout } = useAuth()
const route = useRoute()
const router = useRouter()
const mobileMenuOpen = ref(false)
const userDropdownOpen = ref(false)

const links = computed(() => {
  const sid = (typeof localStorage !== 'undefined' ? localStorage.getItem('bjfu-student-id') : '') || ''
  const schedulePath = sid.trim() ? `/schedule?user=${encodeURIComponent(sid.trim())}` : '/schedule'

  const items: { to: string; label: string }[] = [
    { to: '/', label: '首页' },
    { to: schedulePath, label: '课表' },
    { to: '/projects', label: '项目' },
    { to: '/about', label: '关于' },
  ]

  if (isUser.value) {
    items.push(
      { to: '/ai', label: 'AI 助手' },
      { to: '/scripts', label: '脚本' },
    )
  }

  if (isAdmin.value) {
    items.push(
      { to: '/dashboard', label: '控制台' },
      { to: '/admin/scripts', label: '脚本管理' },
      { to: '/knowledge', label: '知识库' },
      { to: '/server', label: '服务器' },
    )
  }

  return items
})

function isActive(to: string) {
  return route.path === to
}

function handleLogout() {
  logout()
  userDropdownOpen.value = false
  mobileMenuOpen.value = false
  router.push('/')
}
</script>

<template>
  <header class="md2-appbar">
    <div class="md2-toolbar mx-auto w-full max-w-5xl">

      <!-- Brand Signature
           这里刻意用 .md2-state（宽度自适应）而不是 .md2-icon-btn：
           icon-btn 固定 40px 且 overflow:hidden，会把 76px 宽的字标裁掉。 -->
      <router-link
        to="/"
        class="md2-state -ml-2 inline-flex items-center rounded px-2 py-1.5"
        aria-label="返回首页"
        @click="mobileMenuOpen = false"
      >
        <BrandWordmark size="sm" tone="on-primary" />
      </router-link>

      <!-- Desktop Nav -->
      <!-- 页面里有两个 <nav>（这里和下面的移动抽屉），都没有名称时
           读屏用户只会听到两个一模一样的「导航」地标，分不清哪个是主导航。 -->
      <nav class="ml-4 hidden items-center gap-0.5 md:flex" aria-label="主导航">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="md2-nav-item"
          :aria-current="isActive(link.to) ? 'page' : undefined"
        >
          {{ link.label }}
        </router-link>
      </nav>

      <div class="flex-1 md:hidden" />

      <!-- Right Auth Area -->
      <div class="flex items-center">
        <router-link
          v-if="!isAuthenticated"
          to="/login"
          class="md2-nav-item"
          :aria-current="isActive('/login') ? 'page' : undefined"
        >
          登录
        </router-link>

        <div v-else class="relative">
          <button
            type="button"
            class="md2-icon-btn"
            :aria-expanded="userDropdownOpen"
            aria-haspopup="menu"
            aria-label="账户菜单"
            @click="userDropdownOpen = !userDropdownOpen"
          >
            <!-- 这个圆是「账户菜单」按钮唯一的识别标记，所以它必须能从 app bar 上
                 分离出来，否则按钮等于没有可见的边界（WCAG 1.4.11 要 3:1）。

                 原来的注释记的是「叠白 5.9:1 / 叠深 3.95:1 不达标」，那组数字
                 是在浅蓝 app bar 上量的。app bar 换成黄之后它悄悄失效了：叠白
                 只剩 1.67:1（深色档 1.42:1）。

                 而且这不是调一下叠白比例能救的 —— 解算器扫过 18%~100% 全部
                 配比，纯白叠到黄底也只有 1.67:1，没有任何一个白色比例能过 3:1。
                 黄色太亮，靠近它的浅色都不足以拉开距离。

                 所以边界改由一圈 1px 描边承担：on-appbar #3e2f00 压亮黄 7.79:1、
                 压暗黄 9.17:1，余量充足；底色仍保留 18% 叠白，纯粹是让圆
                 看起来是个「芯片」而不是一个空洞的圈。 -->
            <span
              class="flex h-8 w-8 items-center justify-center rounded-full md2-caption font-semibold uppercase leading-none"
              :style="{
                background: 'color-mix(in srgb, #ffffff 18%, transparent)',
                boxShadow: 'inset 0 0 0 1px var(--md2-on-appbar)',
              }"
            >
              {{ (username || '?').slice(0, 2) }}
            </span>
          </button>

          <!-- Dropdown Backdrop -->
          <div
            v-if="userDropdownOpen"
            class="fixed inset-0 z-40"
            @click="userDropdownOpen = false"
          />
          <div
            v-if="userDropdownOpen"
            class="md2-card absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden py-1 text-on-surface"
            role="menu"
            @click="userDropdownOpen = false"
          >
            <div class="px-4 py-3">
              <div class="md2-body2 font-medium">{{ username }}</div>
              <div class="md2-caption text-ink-secondary">{{ role }}</div>
            </div>
            <div class="md2-divider" />
            <router-link to="/settings" class="md2-list-item md2-body1" role="menuitem">
              偏好设置
            </router-link>
            <router-link to="/ai" class="md2-list-item md2-body1" role="menuitem">
              AI 助手
            </router-link>
            <div class="md2-divider" />
            <button
              type="button"
              class="md2-list-item w-full md2-body1 text-error"
              role="menuitem"
              @click="handleLogout"
            >
              退出登录
            </button>
          </div>
        </div>

        <!-- Mobile Menu Toggle -->
        <button
          type="button"
          class="md2-icon-btn md:hidden"
          :aria-expanded="mobileMenuOpen"
          aria-label="切换菜单"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg v-if="!mobileMenuOpen" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
      </div>

    </div>

    <!-- Mobile Drawer (MD2 list) -->
    <div
          v-if="mobileMenuOpen"
          class="border-t md:hidden"
          :style="{ borderColor: 'color-mix(in srgb, var(--md2-on-appbar) 18%, transparent)' }"
        >
      <nav class="bg-surface py-2 text-on-surface" aria-label="移动端导航">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="md2-list-item md2-body1"
          :class="isActive(link.to) ? 'bg-primary-container text-on-primary-container font-medium' : ''"
          @click="mobileMenuOpen = false"
        >
          {{ link.label }}
        </router-link>

        <div class="md2-divider mx-4 my-2" />

        <template v-if="isAuthenticated">
          <div class="px-4 py-2 md2-caption text-ink-secondary">{{ username }} · {{ role }}</div>
          <button
            type="button"
            class="md2-list-item w-full md2-body1 text-error"
            @click="handleLogout"
          >
            退出登录
          </button>
        </template>
        <router-link
          v-else
          to="/login"
          class="mx-4 my-2 flex items-center justify-center md2-btn md2-btn--contained h-11"
          @click="mobileMenuOpen = false"
        >
          登录
        </router-link>
      </nav>
    </div>
  </header>
</template>
