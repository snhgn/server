<script setup lang="ts">
import { projectList } from '@/data/projects'
</script>

<template>
  <div class="py-14 sm:py-20">
    
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-12">
      <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
        Engineering & Systems
      </div>
      <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
        Projects & Hardware
      </h1>
      <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans leading-relaxed">
        嵌入式底层驱动、机器人控制算法、机器视觉伺服与自建数字基础设施
      </p>
    </header>

    <div class="divide-y divide-[#E5E5E5]/60">
      <article
        v-for="p in projectList"
        :key="p.title"
        class="py-10 first:pt-0 group"
      >
        <div class="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1.5">
          <div class="flex items-center gap-2.5">
            <h2 class="text-base font-medium text-neutral-900 group-hover:text-neutral-600 transition-colors">
              {{ p.title }}
            </h2>
            <span
              v-if="p.tag"
              class="font-mono text-[10px] text-neutral-400 border border-[#E5E5E5] rounded px-1.5 py-0.5 bg-white"
            >
              {{ p.tag }}
            </span>
          </div>
          <span class="font-mono text-xs text-neutral-400">
            {{ p.period }}
          </span>
        </div>
        
        <p class="mt-3 text-xs sm:text-sm leading-relaxed text-neutral-600 font-sans max-w-3xl">
          {{ p.summary }}
        </p>

        <div class="mt-4 flex flex-wrap gap-1.5 font-mono text-xs">
          <span
            v-for="t in p.stack"
            :key="t"
            class="rounded border border-[#E5E5E5] bg-white px-2 py-0.5 text-neutral-600 text-[11px]"
          >
            {{ t }}
          </span>
        </div>
      </article>
    </div>

  </div>
</template>