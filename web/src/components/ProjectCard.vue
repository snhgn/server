<script setup lang="ts">
import type { Project } from '@/data/projects'

defineProps<{
  project: Project
}>()
</script>

<template>
  <article class="md2-card flex flex-col p-5">
    <div class="flex items-start justify-between gap-2">
      <h3 class="md2-h6 text-on-surface">{{ project.title }}</h3>
      <span class="md2-caption shrink-0 text-ink-secondary">{{ project.period }}</span>
    </div>
    <p class="mt-2 flex-1 text-ink-secondary md2-body2">
      {{ project.summary }}
    </p>
    <div class="mt-4 flex flex-wrap gap-1.5">
      <span
        v-for="tech in project.stack"
        :key="tech"
        class="md2-chip h-6 px-2 md2-caption"
      >
        {{ tech }}
      </span>
    </div>
  </article>
</template>
