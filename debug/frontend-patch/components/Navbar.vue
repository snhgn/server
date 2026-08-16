<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'

const { isAuthenticated, isAdmin, isUser, username, role, authReady, logout } = useAuth()
const route = useRoute()
const router = useRouter()
const mobileMenuOpen = ref(false)
const userDropdownOpen = ref(false)

// 动态生成导航链接
const links = computed(() => {
  const items: { to: string; label: string; icon?: string }[] = [
    { to: '/', label: '首页' },
    { to: '/projects', label: '项目' },
    { to: '/about', label: '关于' },
  ]

  // User 级别（user 或 admin 可见）
  if (isUser.value) {
    items.push(
      { to: '/ai', label: 'AI 助手' },
      { to: '/schedule', label: '课表' },
      { to: '/scripts', label: '脚本' },
    )
  }

  // Admin 级别
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

function handleLogout() {
  logout()
  userDropdownOpen.value = false
  mobileMenuOpen.value = false
  router.push('/')
}

function closeDropdowns() {
  userDropdownOpen.value = false
}
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-black/[0.06] bg-white/80 backdrop-blur-md transition-all">
    <div class="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">

      <!-- Brand Logo -->
      <router-link
        to="/"
        class="group flex items-center gap-2.5 font-medium transition-transform active:scale-95"
        @click="mobileMenuOpen = false"
      >
        <div class="brand-mark h-7 w-7 flex-none" aria-hidden="true" />
        <span class="font-mono text-sm font-semibold tracking-tight text-neutral-900 group-hover:text-black">
          snhgn<span class="text-neutral-400">.me</span>
        </span>
      </router-link>

      <!-- Desktop Nav Links -->
      <nav class="hidden md:flex items-center gap-1">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="relative rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors"
          :class="
            route.path === link.to
              ? 'bg-neutral-100/90 text-neutral-950 font-semibold'
              : 'text-neutral-600 hover:bg-neutral-100/60 hover:text-neutral-900'
          "
        >
          {{ link.label }}
        </router-link>
      </nav>

      <!-- Right Actions (Auth / User) -->
      <div class="flex items-center gap-2">
        <!-- Guest Login Button（authReady 未完成时不显示，避免恢复登录状态时闪烁） -->
        <router-link
          v-if="authReady && !isAuthenticated"
          to="/login"
          class="hidden sm:inline-flex items-center justify-center rounded-lg bg-neutral-950 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-neutral-800 hover:shadow active:scale-95"
        >
          登录
        </router-link>

        <!-- User Profile Dropdown -->
        <div v-else-if="isAuthenticated" class="relative">
          <button
            type="button"
            class="flex items-center gap-2 rounded-full border border-neutral-200/80 bg-neutral-50/80 py-1 pl-1.5 pr-2.5 text-xs font-medium text-neutral-700 transition-all hover:bg-neutral-100 active:scale-95"
            @click="userDropdownOpen = !userDropdownOpen"
          >
            <div class="flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-tr from-indigo-500 to-violet-500 font-mono text-[10px] font-bold text-white shadow-xs">
              {{ (username || 'U').charAt(0).toUpperCase() }}
            </div>
            <span class="max-w-[80px] truncate font-mono">{{ username }}</span>
            <span
              class="rounded px-1 text-[10px] font-medium"
              :class="isAdmin ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'"
            >
              {{ role || 'user' }}
            </span>
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-neutral-400" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>

          <!-- Dropdown Popover -->
          <div
            v-if="userDropdownOpen"
            class="fixed inset-0 z-40"
            @click="closeDropdowns"
          />
          <div
            v-if="userDropdownOpen"
            class="absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border border-neutral-200/80 bg-white p-1.5 shadow-xl transition-all"
            @click="closeDropdowns"
          >
            <div class="border-b border-neutral-100 px-3 py-2 text-xs">
              <p class="font-medium text-neutral-900">{{ username }}</p>
              <p class="font-mono text-[11px] text-neutral-400">{{ role }} account</p>
            </div>
            <div class="py-1">
              <router-link
                to="/settings"
                class="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-100"
              >
                <span>⚙️</span> 偏好设置
              </router-link>
              <router-link
                to="/ai"
                class="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-100"
              >
                <span>✨</span> AI 助手
              </router-link>
            </div>
            <div class="border-t border-neutral-100 pt-1">
              <button
                type="button"
                class="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                @click="handleLogout"
              >
                <span>🚪</span> 退出登录
              </button>
            </div>
          </div>
        </div>

        <!-- Mobile Hamburger Button -->
        <button
          type="button"
          class="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-200 text-neutral-600 hover:bg-neutral-100 md:hidden"
          aria-label="菜单"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg v-if="!mobileMenuOpen" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile Drawer Menu -->
    <div
      v-if="mobileMenuOpen"
      class="border-b border-neutral-200/80 bg-white/95 px-4 py-3 shadow-lg backdrop-blur md:hidden"
    >
      <nav class="flex flex-col gap-1">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="rounded-lg px-3 py-2 text-sm font-medium transition-colors"
          :class="
            route.path === link.to
              ? 'bg-neutral-100 font-semibold text-neutral-950'
              : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
          "
          @click="mobileMenuOpen = false"
        >
          {{ link.label }}
        </router-link>

        <div class="mt-2 border-t border-neutral-100 pt-2">
          <router-link
            v-if="authReady && !isAuthenticated"
            to="/login"
            class="flex w-full items-center justify-center rounded-lg bg-neutral-950 px-4 py-2 text-sm font-semibold text-white"
            @click="mobileMenuOpen = false"
          >
            登录
          </router-link>
          <button
            v-else-if="isAuthenticated"
            type="button"
            class="flex w-full items-center justify-center rounded-lg border border-neutral-200 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
            @click="handleLogout"
          >
            退出登录 ({{ username }})
          </button>
        </div>
      </nav>
    </div>
  </header>
</template>
