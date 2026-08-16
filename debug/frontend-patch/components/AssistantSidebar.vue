<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'
import ConversationList from './ConversationList.vue'

interface Session {
  session_id: string
  msg_count: number
  last_at: string
  title: string
  summary?: string
  keywords?: string[]
}

defineProps<{
  sessions: Session[]
  currentSessionId: string | null
  loading?: boolean
  open?: boolean
  searchQuery?: string
}>()

const emit = defineEmits<{
  (e: 'new-chat'): void
  (e: 'select', sessionId: string): void
  (e: 'close'): void
  (e: 'update:searchQuery', v: string): void
  (e: 'rename', sessionId: string, title: string): void
  (e: 'delete', sessionId: string): void
}>()

const { username, logout } = useAuth()
const router = useRouter()

const initial = (() => {
  const s = username.value || 'U'
  return s.charAt(0).toUpperCase()
})()

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <!-- 遮罩：手机端 -->
  <div
    v-if="open"
    class="fixed inset-0 z-30 bg-black/30 backdrop-blur-xs md:hidden"
    @click="emit('close')"
  />

  <aside
    class="flex h-full w-full flex-col border-r border-black/[.06] bg-dsw-surface"
    :class="[
      'md:static md:z-0 md:translate-x-0 md:bg-dsw-surface',
      open
        ? 'fixed left-0 top-0 z-40 w-[280px] max-w-[85%] translate-x-0 shadow-xl transition-transform duration-200 ease-out'
        : 'fixed left-0 top-0 z-40 w-[280px] max-w-[85%] -translate-x-full shadow-xl transition-transform duration-200 ease-in md:hidden',
    ]"
  >
    <!-- 品牌区 -->
    <div class="flex items-center gap-2.5 px-4 pb-2 pt-4">
      <router-link to="/" class="flex items-center gap-2.5 group" title="返回站点首页">
        <div class="brand-mark h-8 w-8 flex-none" aria-hidden="true" />
        <div class="flex min-w-0 flex-col leading-tight">
          <span class="text-[15px] font-bold text-dsw-ink group-hover:text-black">Assistant</span>
          <span class="text-[10px] text-dsw-ink-4">snhgn.me AI Node</span>
        </div>
      </router-link>
      <!-- 手机端关闭 -->
      <button
        type="button"
        class="ml-auto flex h-8 w-8 flex-none items-center justify-center rounded-lg text-dsw-ink-3 transition-colors hover:bg-black/[.06] md:hidden"
        aria-label="关闭"
        @click="emit('close')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
          <path d="M18 6 6 18" />
          <path d="m6 6 12 12" />
        </svg>
      </button>
    </div>

    <!-- 搜索 -->
    <div class="px-3 pb-2">
      <div class="flex h-8 items-center gap-2 rounded-lg border border-black/10 bg-white px-2.5 transition-colors focus-within:border-black/30">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5 flex-none text-dsw-ink-4">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          :value="searchQuery"
          type="text"
          placeholder="搜索历史对话…"
          class="min-w-0 flex-1 bg-transparent text-[13px] text-dsw-ink outline-none placeholder:text-dsw-ink-4"
          @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>

    <!-- New Chat -->
    <div class="px-3 pb-2">
      <button
        type="button"
        class="flex h-[38px] w-full items-center justify-center gap-2 rounded-xl border border-black/10 bg-white text-sm font-semibold text-dsw-ink shadow-2xs transition-all hover:bg-neutral-50 active:scale-[0.99]"
        @click="emit('new-chat')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 text-dsw-ink-2">
          <path d="M12 5v14" />
          <path d="M5 12h14" />
        </svg>
        <span>新建会话</span>
      </button>
    </div>

    <!-- 会话列表 -->
    <div class="dsw-scroll min-h-0 flex-1 overflow-y-auto px-3 pb-3">
      <ConversationList
        :sessions="sessions"
        :current-session-id="currentSessionId"
        :loading="loading"
        :search-query="searchQuery"
        @select="emit('select', $event)"
        @rename="(sid: string, title: string) => emit('rename', sid, title)"
        @delete="emit('delete', $event)"
      />
    </div>

    <!-- 底部：用户卡片 + 快捷首页入口 -->
    <div class="border-t border-black/[.06] bg-white/70 p-3 backdrop-blur-xs">
      <div class="flex items-center gap-2 rounded-xl p-1.5 transition-colors hover:bg-black/[.04]">
        <div class="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-neutral-950 font-mono text-xs font-bold text-white shadow-2xs">
          {{ initial }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate font-mono text-xs font-bold text-neutral-800">{{ username }}</p>
          <p class="truncate text-[10px] text-neutral-400">已登录账号</p>
        </div>
        <router-link
          to="/"
          class="flex h-7 w-7 flex-none items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-100 hover:text-neutral-900 transition-colors"
          title="返回网站首页"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        </router-link>
        <button
          type="button"
          class="flex h-7 w-7 flex-none items-center justify-center rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-600 transition-colors"
          aria-label="退出登录"
          title="退出登录"
          @click="handleLogout"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" x2="9" y1="12" y2="12" />
          </svg>
        </button>
      </div>
    </div>
  </aside>
</template>
