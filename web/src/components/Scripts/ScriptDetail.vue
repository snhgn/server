<script setup lang="ts">
import type { ScriptListItem, ScriptSummary } from '@/data/scripts'
import { TYPE_LABELS } from '@/data/scripts'
import ScriptStatus from './ScriptStatus.vue'

defineProps<{
  script: ScriptListItem
  summary?: ScriptSummary | null
  summaryLoading?: boolean
  busy?: boolean
}>()
defineEmits<{
  close: []
  run: [script: ScriptListItem]
  stop: [script: ScriptListItem]
  edit: [script: ScriptListItem]
  del: [script: ScriptListItem]
  history: [script: ScriptListItem]
  logs: [script: ScriptListItem]
}>()

function fmt(iso: string | null | undefined): string {
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
      
      <!-- Drawer Header -->
      <div class="flex items-start justify-between border-b border-neutral-200/80 px-6 py-5">
        <div class="min-w-0 pr-4">
          <div class="flex items-center gap-2">
            <h2 class="truncate text-base font-bold text-neutral-900">{{ script.name }}</h2>
            <ScriptStatus :status="script.status" />
          </div>
          <p class="mt-1 text-xs text-neutral-500 leading-relaxed">
            {{ script.description || '无任务描述' }}
          </p>
        </div>
        <button
          type="button"
          class="text-neutral-400 hover:text-neutral-900 font-mono text-sm"
          @click="$emit('close')"
        >
          ✕
        </button>
      </div>

      <!-- Actions Bar -->
      <div class="flex items-center gap-2 border-b border-neutral-100 bg-neutral-50 px-6 py-2.5 font-mono text-xs">
        <button
          type="button"
          :disabled="busy"
          class="bg-neutral-950 text-white px-2.5 py-1 rounded font-medium hover:bg-neutral-800 disabled:opacity-40"
          @click="$emit('run', script)"
        >
          ▶ Run
        </button>
        <button
          type="button"
          class="border border-neutral-200 bg-white px-2.5 py-1 rounded text-neutral-700 hover:bg-neutral-100"
          @click="$emit('stop', script)"
        >
          Stop
        </button>
        <button
          type="button"
          class="border border-neutral-200 bg-white px-2.5 py-1 rounded text-neutral-700 hover:bg-neutral-100"
          @click="$emit('edit', script)"
        >
          Edit
        </button>
        <button
          type="button"
          class="border border-neutral-200 bg-white px-2.5 py-1 rounded text-neutral-700 hover:bg-neutral-100"
          @click="$emit('logs', script)"
        >
          Logs
        </button>
        <button
          type="button"
          class="border border-neutral-200 bg-white px-2.5 py-1 rounded text-neutral-700 hover:bg-neutral-100"
          @click="$emit('history', script)"
        >
          History
        </button>
      </div>

      <!-- Drawer Body -->
      <div class="flex-1 space-y-6 overflow-y-auto p-6 font-mono text-xs">
        
        <!-- Summary Stats -->
        <div>
          <h3 class="font-sans font-semibold text-xs text-neutral-900 mb-2">执行统计</h3>
          <div v-if="summaryLoading" class="text-neutral-400">Loading metrics…</div>
          <div v-else-if="summary" class="grid grid-cols-3 gap-2 text-center">
            <div class="border border-neutral-200 p-2.5 rounded">
              <span class="text-[10px] text-neutral-400 block font-sans">总次数</span>
              <span class="font-bold text-neutral-900 text-sm mt-0.5 block">{{ summary.total_runs }}</span>
            </div>
            <div class="border border-neutral-200 p-2.5 rounded">
              <span class="text-[10px] text-neutral-400 block font-sans">成功率</span>
              <span class="font-bold text-emerald-700 text-sm mt-0.5 block">
                {{ summary.total_runs ? Math.round((summary.success / summary.total_runs) * 100) : 0 }}%
              </span>
            </div>
            <div class="border border-neutral-200 p-2.5 rounded">
              <span class="text-[10px] text-neutral-400 block font-sans">平均耗时</span>
              <span class="font-bold text-neutral-900 text-sm mt-0.5 block">{{ fmtDuration(summary.avg_duration_ms) }}</span>
            </div>
          </div>
        </div>

        <!-- Details -->
        <div>
          <h3 class="font-sans font-semibold text-xs text-neutral-900 mb-2">配置详情</h3>
          <div class="divide-y divide-neutral-100 border border-neutral-200 rounded p-3 space-y-2">
            <div class="flex justify-between">
              <span class="text-neutral-400">Type</span>
              <span class="text-neutral-800">{{ TYPE_LABELS[script.type] }}</span>
            </div>
            <div class="flex justify-between pt-2">
              <span class="text-neutral-400">Cron</span>
              <span class="text-neutral-800">{{ script.cron || 'Manual Trigger' }}</span>
            </div>
            <div class="flex justify-between pt-2">
              <span class="text-neutral-400">Visibility</span>
              <span class="text-neutral-800">{{ script.visibility }}</span>
            </div>
            <div class="flex justify-between pt-2">
              <span class="text-neutral-400">Next Scheduled</span>
              <span class="text-neutral-800">{{ fmt(script.next_run) }}</span>
            </div>
            <div class="pt-2">
              <span class="text-neutral-400 block mb-1">Command</span>
              <pre class="bg-neutral-900 text-neutral-200 p-2 rounded text-[11px] overflow-x-auto">{{ script.command || '—' }}</pre>
            </div>
          </div>
        </div>

      </div>

    </div>
  </div>
</template>