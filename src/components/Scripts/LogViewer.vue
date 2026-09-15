<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { analyzeScriptError, fetchScriptLogs } from '@/api/scripts'
import type { ScriptLogResult } from '@/data/scripts'

const props = defineProps<{ scriptId: number }>()
defineEmits<{ close: [] }>()

const log = ref<ScriptLogResult | null>(null)
const loading = ref(false)
const analyzing = ref(false)
const analysis = ref('')
const copied = ref(false)

async function load() {
  loading.value = true
  try {
    log.value = await fetchScriptLogs(props.scriptId)
  } catch (e: any) {
    analysis.value = `加载日志失败：${e.message}`
  } finally {
    loading.value = false
  }
}

async function analyze() {
  analyzing.value = true
  analysis.value = ''
  try {
    const res = await analyzeScriptError(props.scriptId)
    analysis.value = res.analysis
  } catch (e: any) {
    analysis.value = `分析失败：${e.message}`
  } finally {
    analyzing.value = false
  }
}

function copyLogs() {
  const content = (log.value?.lines || []).join('\n')
  navigator.clipboard.writeText(content)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

onMounted(load)
</script>

<template>
  <div class="fixed inset-0 z-50 flex justify-end bg-black/20 backdrop-blur-xs" @click.self="$emit('close')">
    <div class="flex h-full w-full max-w-2xl flex-col bg-white shadow-xl border-l border-neutral-200">
      
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-neutral-200/80 px-6 py-4">
        <div>
          <h2 class="text-sm font-bold text-neutral-900">Task Terminal Logs</h2>
          <p class="font-mono text-xs text-neutral-400">Script ID: {{ scriptId }}</p>
        </div>
        <button
          type="button"
          class="text-neutral-400 hover:text-neutral-900 font-mono text-sm"
          @click="$emit('close')"
        >
          ✕
        </button>
      </div>

      <!-- Toolbar -->
      <div class="flex items-center justify-between border-b border-neutral-100 bg-neutral-50 px-6 py-2 font-mono text-xs">
        <button
          type="button"
          :disabled="analyzing"
          class="text-neutral-900 font-medium hover:underline disabled:opacity-50"
          @click="analyze"
        >
          {{ analyzing ? 'AI Analyzing…' : 'AI Error Diagnosis' }}
        </button>

        <button
          type="button"
          class="text-neutral-600 hover:text-neutral-900"
          @click="copyLogs"
        >
          {{ copied ? 'Copied ✓' : 'Copy Output' }}
        </button>
      </div>

      <!-- AI Diagnosis Panel -->
      <div
        v-if="analysis"
        class="border-b border-neutral-200 bg-neutral-50 p-4 text-xs text-neutral-800"
      >
        <p class="font-bold text-neutral-900 mb-1">AI 诊断意见：</p>
        <div class="whitespace-pre-wrap leading-relaxed">{{ analysis }}</div>
      </div>

      <!-- Terminal Output -->
      <div class="flex-1 overflow-y-auto bg-neutral-950 p-4 font-mono text-xs text-neutral-200">
        <p v-if="loading" class="text-neutral-500">Loading output…</p>
        <div v-else-if="log?.lines?.length" class="space-y-0.5">
          <div
            v-for="(line, idx) in log.lines"
            :key="idx"
            class="leading-relaxed"
            :class="line.includes('ERROR') || line.includes('Failed') ? 'text-red-400' : 'text-neutral-300'"
          >
            <span class="text-neutral-600 select-none mr-3 text-[10px]">{{ idx + 1 }}</span>{{ line }}
          </div>
        </div>
        <p v-else class="text-neutral-500">No output recorded.</p>
      </div>

    </div>
  </div>
</template>