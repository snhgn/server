<script setup lang="ts">
import { projectList } from '@/data/projects'
</script>

<template>
  <div class="py-10 sm:py-14">

    <header class="mb-8">
      <div class="md2-overline">Engineering &amp; Systems</div>
      <h1 class="md2-h2 mt-1 text-on-surface">Projects &amp; Hardware</h1>
      <p class="mt-2 text-ink-secondary md2-body1">
        嵌入式底层驱动、机器人控制算法、机器视觉伺服与自建数字基础设施
      </p>
      <!-- 三个项目只占红/黄/蓝三色，补一条四色细线把绿带上 -->
      <div class="md2-accent-quad-rule mt-6" aria-hidden="true"></div>
    </header>

    <div class="grid gap-4 sm:grid-cols-2">
      <article
        v-for="p in projectList"
        :key="p.title"
        :data-accent="p.accent"
        class="md2-card md2-accent-top flex flex-col p-5"
      >
        <div class="flex items-start justify-between gap-2">
          <h2 class="md2-h6 text-on-surface">{{ p.title }}</h2>
          <span
            v-if="p.tag"
            class="md2-chip md2-chip--accent h-6 shrink-0 px-2 md2-caption uppercase tracking-wider"
          >
            {{ p.tag }}
          </span>
        </div>

        <p class="mt-2 flex-1 text-ink-secondary md2-body2">{{ p.summary }}</p>

        <div class="mt-4 flex flex-wrap gap-1.5">
          <span v-for="t in p.stack" :key="t" class="md2-chip h-6 px-2 md2-caption">
            {{ t }}
          </span>
        </div>

        <div class="mt-3 font-mono text-[11px] text-ink-secondary">{{ p.period }}</div>
      </article>
    </div>

  </div>
</template>
