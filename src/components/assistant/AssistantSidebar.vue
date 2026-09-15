<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'
import ConversationList from './ConversationList.vue'
import BrandWordmark from '@/components/BrandWordmark.vue'

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

function handleLogout() {
  logout()
  router.push('/')
}
</script>

<template>
  <!-- Mobile Backdrop -->
  <div
    v-if="open"
    class="fixed inset-0 z-30 bg-black/20 backdrop-blur-xs md:hidden"
    @click="emit('close')"
  />

  <aside
    class="flex h-full w-full flex-col border-r border-[#E5E5E5]/70 bg-[#FAFAFA] text-neutral-800"
    :class="[
      'md:static md:z-0 md:translate-x-0',
      open
        ? 'fixed left-0 top-0 z-40 w-[270px] max-w-[85%] translate-x-0 shadow-xl transition-transform duration-200 ease-out'
        : 'fixed left-0 top-0 z-40 w-[270px] max-w-[85%] -translate-x-full shadow-xl transition-transform duration-200 ease-in md:hidden',
    ]"
  >
    <!-- Top Header: Wordmark & Back to Space -->
    <div class="flex items-center justify-between px-4 pt-4 pb-3">
      <router-link to="/" class="flex items-center gap-1.5 hover:opacity-80 transition-opacity">
        <BrandWordmark size="xs" />
      </router-link>

      <div class="flex items-center gap-1">
        <router-link
          to="/"
          class="flex items-center gap-1 text-[11px] font-mono text-neutral-500 hover:text-neutral-900 px-2 py-0.5 rounded border border-[#E5E5E5] bg-white transition-colors"
          title="返回主页"
        >
          <span>Home</span>
          <span>↗</span>
        </router-link>

        <button
          type="button"
          class="flex h-7 w-7 items-center justify-center rounded text-neutral-500 hover:text-neutral-900 md:hidden cursor-pointer"
          title="关闭菜单"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- "New Chat" Button -->
    <div class="px-3 py-2">
      <button
        type="button"
        class="flex h-9 w-full items-center justify-center gap-1.5 rounded border border-[#E5E5E5] bg-white hover:border-neutral-900 hover:text-neutral-950 px-3 text-xs font-mono text-neutral-700 shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-all cursor-pointer"
        @click="emit('new-chat')"
      >
        <span class="text-sm font-normal leading-none">+</span>
        <span>New Conversation</span>
      </button>
    </div>

    <!-- Search Input -->
    <div class="px-3 pb-2">
      <input
        :value="searchQuery"
        type="text"
        placeholder="搜索历史会话..."
        class="w-full rounded border border-[#E5E5E5] bg-white px-2.5 py-1.5 text-xs text-neutral-800 placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none transition-colors font-sans"
        @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <!-- Section Title -->
    <div class="px-4 pt-3 pb-1 text-[10px] font-mono uppercase tracking-widest text-neutral-400">
      Conversations
    </div>

    <!-- Conversation List -->
    <div class="dsw-scroll min-h-0 flex-1 overflow-y-auto px-2 pb-3">
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

    <!-- Bottom User Bar -->
    <div class="border-t border-[#E5E5E5]/70 bg-white p-3 text-xs">
      <div class="flex items-center justify-between rounded px-1.5 py-1">
        <div class="flex items-center gap-2 min-w-0">
          <div class="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-neutral-900 font-mono text-[10px] text-white">
            {{ initial }}
          </div>
          <div class="flex flex-col min-w-0">
            <span class="truncate font-mono text-xs text-neutral-900">{{ username }}</span>
            <span class="text-[10px] font-mono text-neutral-400">snhgn.me node</span>
          </div>
        </div>

        <div class="flex items-center gap-1 font-mono text-[11px]">
          <router-link
            to="/settings"
            class="text-neutral-400 hover:text-neutral-900 p-1 rounded hover:bg-neutral-50 transition-colors"
            title="偏好设置"
          >
            Settings
          </router-link>
          <span class="text-neutral-300">·</span>
          <button
            type="button"
            class="text-neutral-400 hover:text-red-600 p-1 rounded hover:bg-neutral-50 transition-colors cursor-pointer"
            title="退出登录"
            @click="handleLogout"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>