<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'
import BrandWordmark from '@/components/BrandWordmark.vue'

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

interface Props {
  messages: Message[]
  isSending?: boolean
  error?: string | null
  memoryCount: number | null
  memoryEnabled: boolean
  lastSourcesCount: number
  lastProvider: string | null
  providerFallback: boolean
  sidebarOpen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSending: false,
  sidebarOpen: false,
})

const emit = defineEmits<{
  (e: 'scroll-bottom'): void
  (e: 'quick-entry', text: string): void
  (e: 'add-to-knowledge', file: FileMeta): void
  (e: 'toggle-sidebar'): void
}>()

const scrollEl = ref<HTMLElement | null>(null)

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  }
}

watch(() => scrollEl.value?.scrollHeight, scrollBottom)
watch(() => props.messages.length, scrollBottom)

defineExpose({ scrollBottom })

const quickEntries = [
  {
    title: '代码与系统架构审查',
    desc: '分析软硬件通信协议、模块解耦与实时性能瓶颈',
    prompt: '请帮我评估并重构以下系统架构的设计方案：\n\n',
  },
  {
    title: '嵌入式与算法选型探讨',
    desc: 'STM32、FreeRTOS、CAN 总线拓扑与级联 PID 算法',
    prompt: '针对多传感器融合与机器人闭环控制，应该如何设计驱动与状态机架构？',
  },
  {
    title: '专业知识库与文献提炼',
    desc: '从校园通知、课程资料与工程技术文档中检索关键结论',
    prompt: '请结合当前 RAG 知识库，总结核心要点与执行建议：\n\n',
  },
  {
    title: '前沿技术与工程演进探索',
    desc: '机器视觉伺服、LLM 智能体集成与私有化基础设施优化',
    prompt: '探讨私有化部署场景下，模型微调与向量检索协同的最佳实践。',
  },
]

function onQuick(entry: { prompt: string }) {
  emit('quick-entry', entry.prompt)
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col bg-white">

    <!-- Top Workspace Header -->
    <header class="flex-shrink-0 bg-white/95 px-4 py-3 flex items-center justify-between border-b border-[#E5E5E5]/70 backdrop-blur-xs">
      
      <!-- Left: Sidebar Toggle & Brand -->
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded border border-[#E5E5E5] text-neutral-600 hover:text-neutral-950 hover:bg-neutral-50 transition-colors cursor-pointer"
          :title="sidebarOpen ? '收起会话列表' : '展开会话列表'"
          @click="emit('toggle-sidebar')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <router-link to="/" class="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <BrandWordmark size="xs" />
          <span class="font-mono text-[10px] text-neutral-400 border border-[#E5E5E5] rounded px-1.5 py-0.5 bg-[#FAFAFA]">
            Workspace
          </span>
        </router-link>
      </div>

      <!-- Right: Telemetry Chips & Home Link -->
      <div class="flex items-center gap-2 text-xs font-mono text-neutral-500">
        <span
          class="hidden sm:inline-flex items-center gap-1.5 rounded border border-[#E5E5E5] bg-[#FAFAFA] px-2 py-0.5 text-[10px]"
          :title="memoryEnabled ? '长期偏好记忆已启用' : '记忆未启用'"
        >
          <span class="h-1.5 w-1.5 rounded-full" :class="memoryEnabled ? 'bg-neutral-900 dark:bg-emerald-400' : 'bg-neutral-300 dark:bg-neutral-600'" />
          <span>{{ memoryCount !== null ? `Memory: ${memoryCount}` : 'Memory' }}</span>
        </span>

        <span
          class="hidden sm:inline-flex items-center gap-1.5 rounded border border-[#E5E5E5] bg-[#FAFAFA] px-2 py-0.5 text-[10px]"
          title="RAG 知识库检索状态"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-neutral-900 dark:bg-emerald-400" />
          <span>{{ lastSourcesCount > 0 ? `RAG: ${lastSourcesCount}` : 'RAG Ready' }}</span>
        </span>

        <router-link
          to="/"
          class="font-mono text-xs text-neutral-400 hover:text-neutral-950 transition-colors ml-1 px-1 py-0.5"
        >
          Exit ↗
        </router-link>
      </div>

    </header>

    <!-- Scrollable Messages Viewport -->
    <div ref="scrollEl" class="dsw-scroll min-h-0 flex-1 overflow-y-auto bg-[#FAFAFA]/40">
      <div class="mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 py-8 sm:px-6">

        <!-- Quiet Workspace Greeting Screen (When no messages) -->
        <div v-if="messages.length === 0" class="flex flex-1 flex-col justify-center py-12 sm:py-16">
          
          <!-- Hero Title -->
          <div class="mb-10 text-left">
            <h1 class="text-2xl sm:text-3xl font-light tracking-tight text-neutral-900 font-sans">
              AI Workspace
            </h1>
            <p class="font-mono text-xs text-neutral-400 mt-2">
              Stay curious, keep building.
            </p>
            <p class="text-xs sm:text-sm text-neutral-500 font-sans leading-relaxed mt-4 max-w-xl">
              私有化双模型协作环境。支持长期偏好记忆沉淀、校园与专业工程资料 RAG 检索及代码/流式推理。
            </p>
          </div>

          <!-- Prompt Starters Grid -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              v-for="entry in quickEntries"
              :key="entry.title"
              type="button"
              class="group flex flex-col justify-between rounded-lg border border-[#E5E5E5] bg-white hover:border-neutral-900 p-4 text-left transition-all cursor-pointer min-h-[90px] shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
              @click="onQuick(entry)"
            >
              <div>
                <h3 class="text-xs font-medium text-neutral-900 group-hover:text-neutral-950 font-sans">
                  {{ entry.title }}
                </h3>
                <p class="text-[11px] text-neutral-500 font-sans mt-1 leading-relaxed">
                  {{ entry.desc }}
                </p>
              </div>
              <div class="mt-3 font-mono text-[10px] text-neutral-400 group-hover:text-neutral-900 transition-colors flex items-center gap-1">
                <span>Start</span>
                <span class="transition-transform group-hover:translate-x-0.5">→</span>
              </div>
            </button>
          </div>

        </div>

        <!-- Chat Stream Messages -->
        <div v-else class="space-y-6">
          <MessageBubble
            v-for="(msg, idx) in messages"
            :key="idx"
            :role="msg.role"
            :text="msg.text"
            :sources="msg.sources"
            :provider="msg.provider"
            :files="msg.files"
            :streaming="msg.streaming"
            :status-steps="msg.statusSteps"
            @add-to-knowledge="emit('add-to-knowledge', $event)"
          />

          <!-- Global Error Banner -->
          <div v-if="error" class="rounded border border-red-200 bg-red-50/80 p-3 text-xs text-red-600 font-mono">
            Error: {{ error }}
          </div>
        </div>

      </div>
    </div>

  </div>
</template>