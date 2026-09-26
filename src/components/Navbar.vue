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

function handleLogout() {
  logout()
  userDropdownOpen.value = false
  mobileMenuOpen.value = false
  router.push('/')
}
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-[#E5E5E5]/60 bg-[#FAFAFA]/85 backdrop-blur-md transition-colors">
    <div class="mx-auto flex h-13 w-full max-w-4xl items-center justify-between px-4 sm:px-6">
      
      <!-- Brand Signature Link -->
      <router-link
        to="/"
        class="group flex items-center gap-2 py-1 transition-opacity hover:opacity-80"
        @click="mobileMenuOpen = false"
      >
        <BrandWordmark size="sm" />
      </router-link>

      <!-- Desktop Nav -->
      <nav class="hidden md:flex items-center gap-1">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="relative px-2.5 py-1.5 text-xs font-normal transition-colors"
          :class="route.path === link.to ? 'text-neutral-900 font-medium' : 'text-neutral-500 hover:text-neutral-900'"
        >
          {{ link.label }}
          <span
            v-if="route.path === link.to"
            class="absolute bottom-[-11px] left-2.5 right-2.5 h-[1.5px] rounded-full bg-neutral-900"
          />
        </router-link>
      </nav>

      <!-- Right Auth Area -->
      <div class="flex items-center gap-2">
        <router-link
          v-if="!isAuthenticated"
          to="/login"
          class="text-xs font-normal text-neutral-500 hover:text-neutral-950 transition-colors px-2 py-1"
        >
          登录
        </router-link>

        <div v-else class="relative">
          <button
            type="button"
            class="flex items-center gap-1.5 rounded border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs font-normal text-neutral-700 hover:border-neutral-400 hover:text-neutral-950 transition-all cursor-pointer shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
            @click="userDropdownOpen = !userDropdownOpen"
          >
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-neutral-900" />
            <span class="font-mono text-[11px] text-neutral-800">{{ username }}</span>
            <span class="text-[10px] text-neutral-400 font-mono">({{ role }})</span>
          </button>

          <!-- Dropdown Backdrop -->
          <div
            v-if="userDropdownOpen"
            class="fixed inset-0 z-40"
            @click="userDropdownOpen = false"
          />
          <div
            v-if="userDropdownOpen"
            class="absolute right-0 top-full z-50 mt-1.5 w-40 rounded-md border border-[#E5E5E5] bg-white p-1 shadow-lg text-xs"
            @click="userDropdownOpen = false"
          >
            <div class="border-b border-neutral-100 px-2.5 py-1.5 font-mono text-[11px] text-neutral-400">
              {{ username }} · {{ role }}
            </div>
            <div class="py-1">
              <router-link
                to="/settings"
                class="flex w-full items-center px-2.5 py-1.5 text-neutral-700 hover:bg-neutral-50 rounded transition-colors"
              >
                偏好设置
              </router-link>
              <router-link
                to="/ai"
                class="flex w-full items-center px-2.5 py-1.5 text-neutral-700 hover:bg-neutral-50 rounded transition-colors"
              >
                AI 助手
              </router-link>
            </div>
            <div class="border-t border-neutral-100 pt-1">
              <button
                type="button"
                class="flex w-full items-center px-2.5 py-1.5 text-red-600 hover:bg-red-50 rounded font-normal cursor-pointer transition-colors"
                @click="handleLogout"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>

        <!-- Mobile Menu Toggle -->
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded border border-[#E5E5E5] text-neutral-600 hover:bg-white md:hidden cursor-pointer"
          aria-label="切换菜单"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg v-if="!mobileMenuOpen" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 fill-none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 fill-none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

    </div>

    <!-- Mobile Drawer -->
    <div
      v-if="mobileMenuOpen"
      class="border-b border-[#E5E5E5] bg-[#FAFAFA] px-4 py-3 md:hidden"
    >
      <nav class="flex flex-col gap-1 text-xs">
        <router-link
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="rounded px-2.5 py-1.5 font-normal transition-colors"
          :class="route.path === link.to ? 'bg-white font-medium text-neutral-900 border border-[#E5E5E5]' : 'text-neutral-600 hover:bg-white/60'"
          @click="mobileMenuOpen = false"
        >
          {{ link.label }}
        </router-link>
        <div class="mt-2 border-t border-neutral-200/60 pt-2">
          <button
            v-if="isAuthenticated"
            type="button"
            class="flex w-full items-center justify-between rounded px-2.5 py-1.5 text-red-600 hover:bg-red-50 cursor-pointer"
            @click="handleLogout"
          >
            <span>退出登录</span>
            <span class="font-mono text-[10px] text-neutral-400">({{ username }})</span>
          </button>
          <router-link
            v-else
            to="/login"
            class="block text-center rounded bg-neutral-900 py-1.5 text-white font-normal hover:bg-neutral-800"
            @click="mobileMenuOpen = false"
          >
            登录
          </router-link>
        </div>
      </nav>
    </div>
  </header>
</template>