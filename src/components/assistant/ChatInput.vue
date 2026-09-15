<script setup lang="ts">
import { ref, computed } from 'vue'

interface FileMeta {
  id: string
  filename: string
  file_type: 'image' | 'text' | 'code' | 'unknown'
  file_size: number
  size_label?: string
  status?: string
}

interface Props {
  modelValue: string
  disabled?: boolean
  isSending?: boolean
  useMemory: boolean
  useRag: boolean
  memoryEnabled: boolean
  lastProvider?: string | null
  isFallback?: boolean
  pendingFiles?: FileMeta[]
  uploading?: boolean
  uploadError?: string | null
  providerPref?: string // 'auto' | 'glm' | 'gemini'
  availableProviders?: string[]
  hero?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  isSending: false,
  pendingFiles: () => [],
  uploading: false,
  uploadError: null,
  providerPref: 'auto',
  availableProviders: () => [],
  hero: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'send'): void
  (e: 'stop'): void
  (e: 'update:useMemory', v: boolean): void
  (e: 'update:useRag', v: boolean): void
  (e: 'upload', file: File): void
  (e: 'remove-file', fileId: string): void
  (e: 'add-to-knowledge', file: FileMeta): void
  (e: 'update:providerPref', v: string): void
}>()

const providerOptions = computed<{ value: string; label: string }[]>(() => {
  const opts = [{ value: 'auto', label: 'Auto (自动推荐)' }]
  if (props.availableProviders.includes('gemini')) {
    opts.push({ value: 'gemini', label: 'Gemini 3.7 Flash' })
  }
  if (props.availableProviders.includes('glm')) {
    opts.push({ value: 'glm', label: 'GLM-4 Flash' })
  }
  for (const p of props.availableProviders) {
    if (p !== 'gemini' && p !== 'glm') {
      opts.push({ value: p, label: `Model: ${p}` })
    }
  }
  return opts
})

const providerLabel = computed(
  () => providerOptions.value.find((o) => o.value === props.providerPref)?.label || 'Auto',
)

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isDragOver = ref(false)
const modelMenuOpen = ref(false)

const canSend = computed(
  () => props.modelValue.trim().length > 0 && !props.disabled && !props.isSending,
)

function onEnter(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (canSend.value) emit('send')
  }
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

function onInput() {
  emit('update:modelValue', textareaRef.value?.value || '')
  autoResize()
}

function triggerFilePicker() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files[0]) {
    emit('upload', target.files[0])
    target.value = ''
  }
}

function onDrop(e: DragEvent) {
  isDragOver.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files[0]) {
    emit('upload', e.dataTransfer.files[0])
  }
}

function selectProvider(p: string) {
  emit('update:providerPref', p)
  modelMenuOpen.value = false
}
</script>

<template>
  <div class="flex-shrink-0 bg-transparent px-4 pb-4 pt-1 sm:px-6">
    <div class="mx-auto w-full max-w-3xl">

      <!-- Hidden file input -->
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        accept=".txt,.md,.py,.c,.cpp,.h,.hpp,.js,.ts,.vue,.json,.csv,.pdf,.docx,.jpg,.jpeg,.png,.webp,.gif"
        @change="onFileChange"
      />

      <!-- Professional Composer Box -->
      <div
        class="relative rounded-xl bg-white border border-[#E5E5E5] p-3 transition-all duration-150 focus-within:border-neutral-900 focus-within:shadow-[0_1px_4px_rgba(0,0,0,0.03)]"
        :class="{ 'border-neutral-900 bg-neutral-50/50': isDragOver }"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="onDrop"
      >
        <!-- Attached Files Chips -->
        <div v-if="pendingFiles && pendingFiles.length > 0" class="mb-2 flex flex-wrap gap-1.5 px-1">
          <div
            v-for="file in pendingFiles"
            :key="file.id"
            class="flex items-center gap-1.5 rounded border border-[#E5E5E5] bg-[#FAFAFA] px-2.5 py-1 text-xs text-neutral-700 font-mono"
          >
            <span class="max-w-[150px] truncate text-[11px] text-neutral-900">{{ file.filename }}</span>
            <span class="text-[10px] text-neutral-400">({{ file.size_label }})</span>

            <button
              v-if="file.file_type !== 'image'"
              type="button"
              class="text-[10px] text-neutral-600 hover:text-neutral-950 ml-1 cursor-pointer font-sans"
              title="加入 RAG 知识库"
              @click="emit('add-to-knowledge', file)"
            >
              +入库
            </button>

            <button
              type="button"
              class="ml-1 text-neutral-400 hover:text-neutral-900 cursor-pointer"
              title="移除附件"
              @click="emit('remove-file', file.id)"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- Upload Error Notice -->
        <p v-if="uploadError" class="mb-2 px-1 text-xs text-red-600 font-mono">
          {{ uploadError }}
        </p>

        <!-- Main Input Textarea -->
        <textarea
          ref="textareaRef"
          :value="modelValue"
          :disabled="disabled"
          rows="1"
          placeholder="向 snhgn. AI Workspace 发起提问、推理或探讨..."
          class="w-full resize-none bg-transparent px-1 py-1 text-xs sm:text-sm leading-relaxed text-neutral-900 placeholder:text-neutral-400 focus:outline-none font-sans"
          style="max-height: 180px"
          @input="onInput"
          @keydown="onEnter"
        />

        <!-- Action & Toggles Bar -->
        <div class="mt-2.5 flex items-center justify-between gap-2 pt-2 border-t border-neutral-100/80">
          
          <!-- Left: Feature Toggles & Model Selector -->
          <div class="flex items-center gap-1.5 flex-wrap">
            
            <!-- Attach File Button -->
            <button
              type="button"
              :disabled="uploading"
              class="flex h-7 w-7 items-center justify-center rounded border border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400 hover:text-neutral-900 transition-colors cursor-pointer disabled:opacity-50"
              title="上传文档或图片"
              @click="triggerFilePicker"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M12 4v16m8-8H4" />
              </svg>
            </button>

            <!-- Memory Toggle Button -->
            <button
              type="button"
              class="flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[11px] transition-colors cursor-pointer"
              :class="
                useMemory
                  ? 'border-neutral-900 bg-neutral-900 text-white font-medium'
                  : 'border-[#E5E5E5] bg-white text-neutral-500 hover:border-neutral-300 hover:text-neutral-900'
              "
              :title="memoryEnabled ? '切换长期偏好记忆' : '需先在设置中启用记忆'"
              @click="emit('update:useMemory', !useMemory)"
            >
              <span
                class="h-1.5 w-1.5 rounded-full"
                :class="useMemory ? 'bg-white' : 'bg-neutral-300'"
              />
              <span>Memory</span>
            </button>

            <!-- RAG Knowledge Toggle Button -->
            <button
              type="button"
              class="flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[11px] transition-colors cursor-pointer"
              :class="
                useRag
                  ? 'border-neutral-900 bg-neutral-900 text-white font-medium'
                  : 'border-[#E5E5E5] bg-white text-neutral-500 hover:border-neutral-300 hover:text-neutral-900'
              "
              title="切换校园与专业资料 RAG 检索"
              @click="emit('update:useRag', !useRag)"
            >
              <span
                class="h-1.5 w-1.5 rounded-full"
                :class="useRag ? 'bg-white' : 'bg-neutral-300'"
              />
              <span>Knowledge RAG</span>
            </button>

            <!-- Model Switcher Popover -->
            <div class="relative">
              <button
                type="button"
                class="flex items-center gap-1 rounded border border-[#E5E5E5] bg-white px-2 py-1 font-mono text-[11px] text-neutral-600 hover:border-neutral-300 hover:text-neutral-900 transition-colors cursor-pointer"
                @click="modelMenuOpen = !modelMenuOpen"
              >
                <span>{{ providerLabel }}</span>
                <span class="text-[9px] text-neutral-400">▾</span>
              </button>

              <div
                v-if="modelMenuOpen"
                class="fixed inset-0 z-40"
                @click="modelMenuOpen = false"
              />
              <div
                v-if="modelMenuOpen"
                class="absolute bottom-full left-0 z-50 mb-1.5 w-48 rounded-md border border-[#E5E5E5] bg-white p-1 shadow-lg text-xs font-mono"
                @click="modelMenuOpen = false"
              >
                <button
                  v-for="opt in providerOptions"
                  :key="opt.value"
                  type="button"
                  class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-neutral-700 hover:bg-neutral-50 cursor-pointer transition-colors"
                  :class="{ 'font-semibold text-neutral-950 bg-neutral-50': providerPref === opt.value }"
                  @click="selectProvider(opt.value)"
                >
                  <span>{{ opt.label }}</span>
                  <span v-if="providerPref === opt.value" class="text-neutral-900">✓</span>
                </button>
              </div>
            </div>

          </div>

          <!-- Right: Send / Stop Button -->
          <div class="flex items-center gap-2">
            <button
              v-if="isSending"
              type="button"
              class="flex h-7 items-center gap-1 rounded bg-neutral-900 px-2.5 font-mono text-[11px] text-white hover:bg-neutral-800 transition-colors cursor-pointer"
              @click="emit('stop')"
            >
              <span class="h-2 w-2 rounded-xs bg-white" />
              <span>Stop</span>
            </button>

            <button
              v-else
              type="button"
              :disabled="!canSend"
              class="flex h-7 w-7 items-center justify-center rounded bg-neutral-900 text-white hover:bg-neutral-800 disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
              title="发送 (Enter)"
              @click="emit('send')"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            </button>
          </div>

        </div>

      </div>

      <div class="mt-2 flex items-center justify-between px-1 font-mono text-[10px] text-neutral-400">
        <span>Shift + Enter 换行 · Enter 发送</span>
        <span v-if="lastProvider">Engine: {{ lastProvider }}</span>
      </div>

    </div>
  </div>
</template>