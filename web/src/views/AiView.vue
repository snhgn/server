<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { api, apiStreamPost, ApiError } from '@/api'
import AssistantSidebar from '@/components/assistant/AssistantSidebar.vue'
import ChatWindow from '@/components/assistant/ChatWindow.vue'
import ChatInput from '@/components/assistant/ChatInput.vue'

interface Source {
  content: string
  category?: string
}
interface FileMeta {
  id: string
  filename: string
  file_type: 'image' | 'text' | 'code' | 'unknown'
  file_size: number
  size_label?: string
  status?: string
}
interface Message {
  role: 'user' | 'assistant'
  text: string
  sources?: Source[]
  provider?: string
  files?: FileMeta[]
  statusSteps?: string[]
  streaming?: boolean
}
interface Session {
  session_id: string
  msg_count: number
  last_at: string
  title: string
  summary?: string
  keywords?: string[]
}

const STATUS_LABELS: Record<string, string> = {
  analyzing: '正在解析上下文与意图',
  retrieving_memory: '正在检索用户偏好记忆',
  retrieving_knowledge: '正在检索 RAG 专业知识库',
  reading_files: '正在读取附加文件与代码',
  generating: '正在生成响应',
}

const messages = ref<Message[]>([])
const input = ref('')
const isSending = ref(false)
const error = ref<string | null>(null)

const sessions = ref<Session[]>([])
const sessionsLoading = ref(false)
const currentSessionId = ref<string | null>(null)

const useMemory = ref(false)
const useRag = ref(false)

const providerPref = ref('auto')
const availableProviders = ref<string[]>([])

async function updateProviderPref(p: string) {
  providerPref.value = p
  try {
    await api.put('/api/ai/settings', {
      memory_enabled: memoryEnabled.value,
      ai_provider: p,
    })
  } catch {
    // ignore
  }
}

const memoryCount = ref<number | null>(null)
const memoryEnabled = ref(false)
const lastProvider = ref<string | null>(null)
const lastSourcesCount = ref(0)
const providerFallback = ref(false)

const sidebarOpen = ref(false)
const searchQuery = ref('')

async function renameSession(sid: string, title: string) {
  const t = title.trim()
  if (!t) return
  try {
    await api.patch(`/api/ai/conversations/${sid}`, { title: t })
  } catch {
    // ignore
  }
  const s = sessions.value.find((x) => x.session_id === sid)
  if (s) s.title = t
}

async function deleteSession(sid: string) {
  try {
    await api.delete(`/api/ai/conversations/${sid}`)
  } catch {
    // ignore
  }
  if (currentSessionId.value === sid) newChat()
  loadSessions()
}

const pendingFiles = ref<FileMeta[]>([])
const uploading = ref(false)
const uploadError = ref<string | null>(null)

const knowledgeModal = ref<{
  open: boolean
  fileId: string | null
  filename: string | null
  loading: boolean
  result: { success: boolean; chunks: number; message: string } | null
}>({ open: false, fileId: null, filename: null, loading: false, result: null })

let abortController: AbortController | null = null
const chatWindowRef = ref<InstanceType<typeof ChatWindow> | null>(null)

async function loadStatus() {
  try {
    const [memRes, setRes] = await Promise.all([
      api.get<{ count: number }>('/api/ai/memory'),
      api.get<{ memory_enabled: boolean; ai_provider?: string | null; available_providers?: string[] }>(
        '/api/ai/settings',
      ),
    ])
    memoryCount.value = (memRes as any).count ?? null
    memoryEnabled.value = !!setRes.memory_enabled
    const pref = (setRes as any).ai_provider
    providerPref.value = pref && pref !== 'auto' ? pref : 'auto'
    availableProviders.value = ((setRes as any).available_providers as string[]) || []
  } catch {
    // ignore
  }
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const res = await api.get<{ sessions: Session[]; count: number }>(
      '/api/ai/conversations',
    )
    sessions.value = (res as any).sessions || []
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

async function selectSession(sid: string) {
  if (isSending.value) return
  sidebarOpen.value = false
  currentSessionId.value = sid
  messages.value = []
  error.value = null
  try {
    const res = await api.get<any>(`/api/ai/conversations/${sid}`)
    const history: any[] = (res as any).messages || []
    for (const m of history) {
      messages.value.push({ role: 'user', text: m.message })
      messages.value.push({
        role: 'assistant',
        text: m.response,
        provider: 'history',
      })
    }
    chatWindowRef.value?.scrollBottom()
  } catch {
    error.value = '加载会话历史失败'
  }
}

function newChat() {
  if (isSending.value) return
  sidebarOpen.value = false
  currentSessionId.value = null
  messages.value = []
  error.value = null
  lastSourcesCount.value = 0
  pendingFiles.value = []
}

async function handleFileUpload(file: File) {
  uploadError.value = null
  const allowedExt = [
    '.jpg', '.jpeg', '.png', '.webp',
    '.md', '.markdown', '.txt', '.pdf', '.docx',
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.c', '.cpp', '.h',
    '.go', '.rs', '.rb', '.php', '.sh', '.bash', '.zsh', '.vue',
    '.css', '.scss', '.html', '.xml', '.yaml', '.yml', '.json', '.toml',
    '.sql', '.kt', '.swift', '.r', '.lua', '.pl',
  ]
  const lowerName = file.name.toLowerCase()
  const ok = allowedExt.some((ext) => lowerName.endsWith(ext))
  if (!ok) {
    uploadError.value = `暂不支持的文件类型：${file.name}`
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    uploadError.value = `文件大小超出 20MB 限制：${file.name}`
    return
  }

  uploading.value = true
  try {
    const res = await api.upload<{ success: boolean; file: FileMeta }>(
      '/api/ai/files/upload',
      file,
    )
    if ((res as any)?.success && (res as any).file) {
      pendingFiles.value.push((res as any).file)
    } else {
      uploadError.value = '文件上传失败'
    }
  } catch (e) {
    uploadError.value = e instanceof ApiError ? e.message : '文件上传失败'
  } finally {
    uploading.value = false
  }
}

function removePendingFile(fileId: string) {
  pendingFiles.value = pendingFiles.value.filter((f) => f.id !== fileId)
  api.delete(`/api/ai/files/${fileId}`).catch(() => {
    // ignore
  })
}

function openKnowledgeModal(file: FileMeta) {
  knowledgeModal.value = {
    open: true,
    fileId: file.id,
    filename: file.filename,
    loading: false,
    result: null,
  }
}

async function confirmAddToKnowledge() {
  if (!knowledgeModal.value.fileId) return
  knowledgeModal.value.loading = true
  knowledgeModal.value.result = null
  try {
    const res = await api.post<{ success: boolean; chunks: number }>(
      `/api/ai/files/${knowledgeModal.value.fileId}/add-to-knowledge`,
    )
    knowledgeModal.value.result = {
      success: true,
      chunks: (res as any).chunks || 0,
      message: `已加入知识库，切分片段 ${(res as any).chunks || 0} 个`,
    }
    const fid = knowledgeModal.value.fileId
    pendingFiles.value = pendingFiles.value.filter((f) => f.id !== fid)
  } catch (e) {
    knowledgeModal.value.result = {
      success: false,
      chunks: 0,
      message: e instanceof ApiError ? e.message : '加入知识库失败',
    }
  } finally {
    knowledgeModal.value.loading = false
  }
}

function closeKnowledgeModal() {
  knowledgeModal.value.open = false
  knowledgeModal.value.result = null
}

async function send() {
  const text = input.value.trim()
  if (!text || isSending.value) return
  input.value = ''
  isSending.value = true
  error.value = null
  providerFallback.value = false

  const fileIds = pendingFiles.value.map((f) => f.id)
  const userFiles = [...pendingFiles.value]
  messages.value.push({ role: 'user', text, files: userFiles.length ? userFiles : undefined })
  pendingFiles.value = []
  chatWindowRef.value?.scrollBottom()

  const aiMsg = reactive<Message>({
    role: 'assistant',
    text: '',
    streaming: true,
    statusSteps: [],
  })
  messages.value.push(aiMsg)

  abortController = new AbortController()
  try {
    await apiStreamPost(
      '/api/ai/chat/stream',
      {
        message: text,
        use_memory: useMemory.value,
        use_rag: useRag.value,
        session_id: currentSessionId.value,
        file_ids: fileIds.length ? fileIds : undefined,
        provider: providerPref.value === 'auto' ? undefined : providerPref.value,
      },
      {
        onStatus: (data: any) => {
          const state = data?.state
          if (!state) return
          const label = STATUS_LABELS[state] || state
          if (!aiMsg.statusSteps!.includes(label)) {
            aiMsg.statusSteps!.push(label)
          }
          if (data.session_id && !currentSessionId.value) {
            currentSessionId.value = data.session_id
          }
        },
        onToken: (t: string) => {
          aiMsg.text += t
          chatWindowRef.value?.scrollBottom()
        },
        onComplete: (data: any) => {
          aiMsg.streaming = false
          aiMsg.statusSteps = []
          if (data?.provider) {
            aiMsg.provider = data.provider
            lastProvider.value = data.provider
          }
          if (data?.sources && data.sources.length) {
            aiMsg.sources = data.sources
            lastSourcesCount.value = data.sources.length
          } else {
            lastSourcesCount.value = 0
          }
          if (data?.files && data.files.length) {
            aiMsg.files = data.files
          }
          loadStatus()
          if (data?.session_id) {
            setTimeout(loadSessions, 1500)
            setTimeout(loadSessions, 4000)
          } else {
            loadSessions()
          }
        },
        onError: (data: any) => {
          aiMsg.streaming = false
          aiMsg.statusSteps = []
          const msg = (data && (data.message || data.detail)) || 'AI 响应中断'
          aiMsg.text = aiMsg.text || `[Error: ${msg}]`
          error.value = msg
        },
      },
      abortController.signal,
    )
  } catch (e) {
    aiMsg.streaming = false
    aiMsg.statusSteps = []
    const msg = e instanceof ApiError ? e.message : '连接错误'
    aiMsg.text = aiMsg.text || `[Error: ${msg}]`
    error.value = msg
  } finally {
    isSending.value = false
    abortController = null
    chatWindowRef.value?.scrollBottom()
  }
}

function stopStreaming() {
  if (abortController) {
    abortController.abort()
    abortController = null
    isSending.value = false
  }
}

function useQuickEntry(text: string) {
  input.value = text
}

onMounted(() => {
  loadStatus()
  loadSessions()
})

onBeforeUnmount(() => {
  if (abortController) abortController.abort()
})
</script>

<template>
  <div class="fixed inset-0 z-0 flex flex-col bg-white">

    <div class="flex min-h-0 flex-1 overflow-hidden">
      <!-- Desktop Collapsible Sidebar -->
      <div
        class="hidden md:block transition-all duration-200 ease-in-out flex-shrink-0"
        :class="sidebarOpen ? 'w-[260px]' : 'w-0 overflow-hidden border-r-0'"
      >
        <div class="w-[260px] h-full">
          <AssistantSidebar
            :sessions="sessions"
            :current-session-id="currentSessionId"
            :loading="sessionsLoading"
            :open="sidebarOpen"
            :search-query="searchQuery"
            @new-chat="newChat"
            @select="selectSession"
            @close="sidebarOpen = false"
            @update:search-query="searchQuery = $event"
            @rename="renameSession"
            @delete="deleteSession"
          />
        </div>
      </div>

      <!-- Mobile Sidebar Drawer -->
      <div class="md:hidden">
        <AssistantSidebar
          :sessions="sessions"
          :current-session-id="currentSessionId"
          :loading="sessionsLoading"
          :open="sidebarOpen"
          :search-query="searchQuery"
          @new-chat="newChat"
          @select="selectSession"
          @close="sidebarOpen = false"
          @update:search-query="searchQuery = $event"
          @rename="renameSession"
          @delete="deleteSession"
        />
      </div>

      <!-- Main Workspace Chat Window -->
      <main class="flex min-w-0 flex-1 flex-col">
        <ChatWindow
          ref="chatWindowRef"
          :messages="messages"
          :is-sending="isSending"
          :error="error"
          :memory-count="memoryCount"
          :memory-enabled="memoryEnabled"
          :last-sources-count="lastSourcesCount"
          :last-provider="lastProvider"
          :provider-fallback="providerFallback"
          :sidebar-open="sidebarOpen"
          @toggle-sidebar="sidebarOpen = !sidebarOpen"
          @quick-entry="useQuickEntry"
          @add-to-knowledge="openKnowledgeModal"
        />
        <ChatInput
          v-model="input"
          v-model:use-memory="useMemory"
          v-model:use-rag="useRag"
          v-model:provider-pref="providerPref"
          :available-providers="availableProviders"
          :disabled="isSending"
          :is-sending="isSending"
          :memory-enabled="memoryEnabled"
          :last-provider="lastProvider"
          :is-fallback="providerFallback"
          :pending-files="pendingFiles"
          :uploading="uploading"
          :upload-error="uploadError"
          :hero="messages.length === 0 && !isSending"
          @send="send"
          @stop="stopStreaming"
          @upload="handleFileUpload"
          @remove-file="removePendingFile"
          @add-to-knowledge="openKnowledgeModal"
          @update:provider-pref="updateProviderPref"
        />
      </main>
    </div>

    <!-- Add To Knowledge Modal -->
    <div
      v-if="knowledgeModal.open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-xs px-4"
      @click.self="closeKnowledgeModal"
    >
      <div class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl border border-[#E5E5E5]">
        <h3 class="mb-1 text-sm font-medium text-neutral-900 font-sans">加入 RAG 知识库</h3>
        <p class="mb-3 text-xs text-neutral-500 font-mono">
          文件：<span class="text-neutral-900">{{ knowledgeModal.filename }}</span>
        </p>
        <p class="mb-4 text-xs leading-relaxed text-neutral-500 font-sans">
          确认后将提取文档文本并切分为向量片段存入 Chroma，在后续对话中由 RAG 引擎实时检索。
        </p>

        <div
          v-if="knowledgeModal.result"
          class="mb-4 rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-xs font-mono text-neutral-800"
        >
          {{ knowledgeModal.result.message }}
        </div>

        <div class="flex justify-end gap-2 text-xs font-mono">
          <button
            type="button"
            class="rounded border border-[#E5E5E5] bg-white px-3 py-1.5 text-neutral-600 hover:text-neutral-900 transition-colors cursor-pointer"
            @click="closeKnowledgeModal"
          >
            {{ knowledgeModal.result ? 'Close' : 'Cancel' }}
          </button>
          <button
            v-if="!knowledgeModal.result"
            type="button"
            :disabled="knowledgeModal.loading"
            class="rounded bg-neutral-900 px-3.5 py-1.5 text-white hover:bg-neutral-800 disabled:opacity-40 transition-colors cursor-pointer"
            @click="confirmAddToKnowledge"
          >
            {{ knowledgeModal.loading ? 'Indexing...' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>