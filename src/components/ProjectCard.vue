<script setup lang="ts">
import type { Project } from '@/data/projects'

defineProps<{
  project: Project
}>()
</script>

<template>
  <article class="group py-5 border-b border-neutral-200/70 last:border-0 transition-colors">
    <div class="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1">
      <h3 class="text-sm font-semibold text-neutral-900 group-hover:text-black">
        {{ project.title }}
      </h3>
      <span class="font-mono text-xs text-neutral-400">
        {{ project.period }}
      </span>
    </div>
    <p class="mt-2 text-xs leading-relaxed text-neutral-600">
      {{ project.summary }}
    </p>
    <div class="mt-3 flex flex-wrap gap-1.5 font-mono text-[11px] text-neutral-500">
      <span
        v-for="tech in project.stack"
        :key="tech"
        class="rounded bg-neutral-100 px-1.5 py-0.5 text-neutral-600"
      >
        {{ tech }}
      </span>
    </div>
  </article>
</template>