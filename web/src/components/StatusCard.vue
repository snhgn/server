<script setup lang="ts">
import type { StatusItem } from '@/data/status'

defineProps<{
  item: StatusItem
}>()
</script>

<template>
  <div class="md2-list-item justify-between">
    <div class="flex items-center gap-3">
      <span
        class="status-dot"
        :class="{
          'bg-emerald-500': item.state === 'online',
          'bg-blue-500': item.state === 'ready',
          'bg-amber-500': item.state === 'active',
          'bg-neutral-400': item.state === 'idle',
        }"
      />
      <span class="md2-list-item__title">{{ item.label }}</span>
    </div>
    <span class="md2-list-item__sub font-mono">{{ item.value }}</span>
  </div>
</template>
