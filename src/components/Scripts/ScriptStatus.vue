<script setup lang="ts">
import type { ScriptStatus } from '@/data/scripts'

defineProps<{ status: ScriptStatus }>()

const dot: Record<ScriptStatus, string> = {
  running: 'bg-emerald-500',
  waiting: 'bg-blue-500',
  failed: 'bg-red-500',
  disabled: 'bg-neutral-300',
}
const label: Record<ScriptStatus, string> = {
  running: 'Running',
  waiting: 'Waiting',
  failed: 'Failed',
  disabled: 'Disabled',
}
</script>

<template>
  <span class="inline-flex items-center gap-1.5 font-mono text-[11px] text-neutral-700">
    <span class="status-dot" :class="dot[status]" />
    <span>{{ label[status] }}</span>
  </span>
</template>