<script setup lang="ts">
import type { ScriptRunRecord } from '@/data/scripts'

defineProps<{
  runs: ScriptRunRecord[]
  loading?: boolean
}>()
defineEmits<{ close: [] }>()

function fmt(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
    : '—'
}
function fmtDuration(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex justify-end bg-black/20 backdrop-blur-xs" @click.self="$emit('close')">
    <div class="flex h-full w-full max-w-md flex-col bg-white shadow-xl border-l border-neutral-200">
      <div class="flex items-center justify-between border-b border-neutral-200/80 px-6 py-4">
        <h2 class="text-sm font-bold text-neutral-900">Execution History</h2>
        <button
          type="button"
          class="text-neutral-400 hover:text-neutral-900 font-mono text-sm"
          @click="$emit('close')"
        >
          ✕
        </button>
      </div>
      <div class="flex-1 overflow-y-auto p-6 font-mono text-xs">
        <p v-if="loading" class="text-neutral-400">Loading history…</p>
        <p v-else-if="!runs.length" class="text-neutral-400">No runs recorded.</p>
        <div v-else class="divide-y divide-neutral-100 border border-neutral-200 rounded">
          <div v-for="r in runs" :key="r.id" class="p-3 flex items-center justify-between">
            <div>
              <div class="flex items-center gap-2">
                <span
                  class="font-bold text-[11px]"
                  :class="{
                    'text-emerald-700': r.status === 'success',
                    'text-red-600': r.status === 'failed',
                    'text-blue-600': r.status === 'running',
                  }"
                >
                  {{ r.status }}
                </span>
                <span class="text-neutral-400 text-[10px]">[{{ r.trigger }}]</span>
              </div>
              <p class="text-[11px] text-neutral-500 mt-0.5">{{ fmt(r.start_time) }}</p>
            </div>
            <span class="text-neutral-700 font-semibold">{{ fmtDuration(r.duration_ms) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>