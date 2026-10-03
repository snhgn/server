<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
}>()
</script>

<template>
  <section class="md2-card p-5 sm:p-6">
    <div v-if="title || subtitle" class="mb-4">
      <h3 v-if="title" class="md2-section-title">{{ title }}</h3>
      <p v-if="subtitle" class="md2-caption mt-1 text-ink-secondary">{{ subtitle }}</p>
    </div>
    <slot />
  </section>
</template>
