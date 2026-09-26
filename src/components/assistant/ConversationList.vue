<script setup lang="ts">
import { computed, ref } from 'vue'

interface Session {
  session_id: string
  msg_count: number
  last_at: string
  title: string
  summary?: string
  keywords?: string[]
}

interface Props {
  sessions: Session[]
  currentSessionId: string | null
  loading?: boolean
  searchQuery?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  searchQuery: '',
})

const emit = defineEmits<{
  (e: 'select', sessionId: string): void
  (e: 'rename', sessionId: string, title: string): void
  (e: 'delete', sessionId: string): void
}>()

const dayStart = (t: number) => {
  const d = new Date(t)
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
}

interface Group {
  label: string
  items: Session[]
}

const groups = computed<Group[]>(() => {
  const q = props.searchQuery.trim().toLowerCase()
  const list = props.sessions.filter((s) => {
    if (!q) return true
    const hay = `${s.title} ${s.summary || ''} ${(s.keywords || []).join(' ')}`.toLowerCase()
    return hay.includes(q)
  })
  const today = dayStart(Date.now())
  const buckets = new Map<string, Session[]>()
  for (const s of list) {
    const t = new Date(s.last_at || Date.now()).getTime()
    const d = dayStart(t)
    let label: string
    if (d === today) label = 'Today'
    else if (d === today - 86400000) label = 'Yesterday'
    else if (Date.now() - t < 7 * 86400000) label = 'Previous 7 Days'
    else label = 'Earlier'
    const arr = buckets.get(label) || []
    arr.push(s)
    buckets.set(label, arr)
  }
  const order = ['Today', 'Yesterday', 'Previous 7 Days', 'Earlier']
  return order
    .filter((k) => buckets.has(k))
    .map((k) => ({ label: k, items: buckets.get(k)! }))
})

// Rename Logic
const renamingId = ref<string | null>(null)
const renameDraft = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

function startRename(s: Session) {
  renamingId.value = s.session_id
  renameDraft.value = s.title || ''
  requestAnimationFrame(() => renameInputRef.value?.focus())
}
function commitRename() {
  const sid = renamingId.value
  renamingId.value = null
  const title = renameDraft.value.trim()
  if (sid && title) emit('rename', sid, title)
}
function cancelRename() {
  renamingId.value = null
}

// Delete Logic
const confirmingDeleteId = ref<string | null>(null)
let confirmTimer: ReturnType<typeof setTimeout> | null = null

function askDelete(sid: string) {
  confirmingDeleteId.value = sid
  if (confirmTimer) clearTimeout(confirmTimer)
  confirmTimer = setTimeout(() => {
    confirmingDeleteId.value = null
  }, 2800)
}
function confirmDelete(sid: string) {
  confirmingDeleteId.value = null
  if (confirmTimer) clearTimeout(confirmTimer)
  emit('delete', sid)
}
</script>

<template>
  <div v-if="loading" class="px-2 py-8 text-center text-xs text-neutral-400 font-mono">
    Loading history...
  </div>

  <div v-else-if="groups.length === 0" class="px-2 py-8 text-center">
    <p class="text-xs text-neutral-400 font-sans">
      {{ searchQuery ? '未找到相关会话' : '暂无历史会话' }}
    </p>
  </div>

  <div v-else class="space-y-4">
    <section v-for="g in groups" :key="g.label">
      <p class="mb-1 px-2.5 text-[10px] font-mono font-medium tracking-widest text-neutral-400 uppercase">
        {{ g.label }}
      </p>
      <ul class="space-y-1">
        <li v-for="s in g.items" :key="s.session_id">
          <div
            class="group relative flex cursor-pointer items-center justify-between rounded px-2.5 py-1.5 text-xs transition-colors"
            :class="
              s.session_id === currentSessionId
                ? 'bg-white border border-[#E5E5E5] text-neutral-950 font-medium shadow-[0_1px_2px_rgba(0,0,0,0.02)] dark:bg-[#20252c] dark:border-[#383f4a] dark:text-white'
                : 'text-neutral-600 hover:bg-white/60 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#1a1e24] dark:hover:text-white'
            "
            @click="renamingId !== s.session_id && emit('select', s.session_id)"
          >
            <!-- Rename Input -->
            <input
              v-if="renamingId === s.session_id"
              ref="renameInputRef"
              v-model="renameDraft"
              class="min-w-0 flex-1 rounded bg-white px-1.5 py-0.5 text-xs text-neutral-900 border border-neutral-900 outline-none font-sans dark:bg-[#16191c] dark:text-white dark:border-neutral-500"
              @keydown.enter.prevent="commitRename"
              @keydown.esc="cancelRename"
              @blur="commitRename"
              @click.stop
            />

            <!-- Title & Actions -->
            <template v-else>
              <span class="truncate flex-1 font-sans text-xs mr-2">
                {{ s.title || '新对话' }}
              </span>

              <!-- Hover Menu -->
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  class="rounded px-1 text-[10px] font-mono text-neutral-400 hover:text-neutral-900 cursor-pointer"
                  title="重命名"
                  @click.stop="startRename(s)"
                >
                  Edit
                </button>

                <template v-if="confirmingDeleteId === s.session_id">
                  <button
                    type="button"
                    class="rounded px-1 text-[10px] font-mono text-red-600 font-semibold cursor-pointer"
                    @click.stop="confirmDelete(s.session_id)"
                  >
                    Confirm?
                  </button>
                </template>
                <button
                  v-else
                  type="button"
                  class="rounded px-1 text-[10px] font-mono text-neutral-400 hover:text-red-600 cursor-pointer"
                  title="删除会话"
                  @click.stop="askDelete(s.session_id)"
                >
                  Del
                </button>
              </div>
            </template>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>