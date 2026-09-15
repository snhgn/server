<script setup lang="ts">
import type { StatusItem } from '@/data/status'

defineProps<{
  item: StatusItem
}>()
</script>

<template>
  <div class="flex items-center justify-between py-2 border-b border-neutral-100 last:border-0 font-mono text-xs">
    <div class="flex items-center gap-2">
      <span
        class="status-dot"
        :class="{
          'bg-emerald-500': item.state === 'online',
          'bg-blue-500': item.state === 'ready',
          'bg-amber-500': item.state === 'active',
          'bg-neutral-300': item.state === 'idle',
        }"
      />
      <span class="text-neutral-500 font-sans">{{ item.label }}</span>
    </div>
    <span class="font-medium text-neutral-800">{{ item.value }}</span>
  </div>
</template>