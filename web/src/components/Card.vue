<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
}>()
</script>

<template>
  <div class="border-b border-neutral-200/80 pb-6 mb-6 last:border-0 last:pb-0 last:mb-0">
    <div v-if="title || subtitle" class="mb-3">
      <h3 v-if="title" class="text-sm font-semibold text-neutral-900">{{ title }}</h3>
      <p v-if="subtitle" class="text-xs text-neutral-500 mt-0.5">{{ subtitle }}</p>
    </div>
    <slot />
  </div>
</template>