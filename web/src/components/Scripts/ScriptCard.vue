<script setup lang="ts">
import type { ScriptListItem } from '@/data/scripts'
import { TYPE_LABELS } from '@/data/scripts'
import ScriptStatus from './ScriptStatus.vue'

defineProps<{ script: ScriptListItem }>()

function fmt(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
}
</script>

<template>
  <div class="py-4 border-b border-neutral-200/70 last:border-0">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <span class="font-mono text-[10px] text-neutral-500 bg-neutral-100 px-1.5 py-0.2 rounded">
            {{ TYPE_LABELS[script.type] }}
          </span>
          <h3 class="text-sm font-semibold text-neutral-900 truncate">
            {{ script.name }}
          </h3>
        </div>
        <p class="mt-1 text-xs text-neutral-500 leading-relaxed">
          {{ script.description || '无任务描述' }}
        </p>
      </div>
      <ScriptStatus :status="script.status" class="shrink-0" />
    </div>

    <div class="mt-3 flex items-center gap-6 font-mono text-[11px] text-neutral-400">
      <div>上次运行: <span class="text-neutral-700">{{ fmt(script.last_run?.start_time) }}</span></div>
      <div>下次计划: <span class="text-neutral-700">{{ fmt(script.next_run) }}</span></div>
    </div>
  </div>
</template>