<script setup lang="ts">
import { computed } from 'vue'
import { useAuth } from '@/stores/auth'
import { projectList } from '@/data/projects'
import BrandWordmark from '@/components/BrandWordmark.vue'

const { isAdmin, isUser, isAuthenticated } = useAuth()

const digitalRooms = computed(() => [
  {
    title: 'Projects & Hardware',
    desc: '嵌入式底层驱动、RoboMaster 机器人控制、机器视觉伺服与软硬件协同',
    to: '/projects',
    meta: 'Engineering',
  },
  {
    title: 'AI Workspace',
    desc: '私有化双引擎协作工作台，支持偏好记忆沉淀与多维知识库 RAG',
    to: isAuthenticated.value ? '/ai' : '/login',
    meta: 'Workspace',
  },
  {
    title: 'Schedule & Calendar',
    desc: '北京林业大学教务数据同步、实时节次时刻分析与学期校历视图',
    to: '/schedule',
    meta: 'Tool',
  },
  {
    title: 'Server & Infrastructure',
    desc: 'Ubuntu 宿主节点拓扑、Cloudflare 零信任通道与自动化定时任务中心',
    to: isAdmin.value ? '/server' : (isUser.value ? '/scripts' : '/login'),
    meta: 'System',
  },
])
</script>

<template>
  <div class="py-16 sm:py-24">
    
    <!-- Hero Section (Vast, Quiet, Breathable) -->
    <section class="py-16 sm:py-24 text-center">
      
      <!-- Signature Wordmark -->
      <div class="mb-4">
        <BrandWordmark size="hero" />
      </div>

      <!-- Slogan (Subtle, secondary brand whisper) -->
      <p class="font-sans text-xs sm:text-sm font-normal tracking-[0.08em] text-neutral-500 mt-3">
        Stay curious, keep building.
      </p>

      <!-- Breathable Intro Narrative -->
      <p class="mx-auto max-w-lg text-xs sm:text-sm leading-relaxed text-neutral-500 font-sans mt-10">
        一个由个人长期维护的独立数字空间与工程工坊。<br>
        专注于嵌入式底层、机器视觉、AI 协作系统与私有化基础设施。
      </p>

    </section>

    <!-- Digital Rooms & Workspaces (Quiet Architectural Layout) -->
    <section class="pt-16 pb-12 border-t border-[#E5E5E5]/60">
      <div class="mb-8 flex items-center justify-between">
        <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400">
          Digital Rooms
        </h2>
        <span class="font-mono text-[11px] text-neutral-400">4 Spaces</span>
      </div>

      <div class="divide-y divide-[#E5E5E5]/60">
        <router-link
          v-for="room in digitalRooms"
          :key="room.title"
          :to="room.to"
          class="group flex flex-col sm:flex-row sm:items-baseline justify-between py-6 first:pt-0 transition-colors"
        >
          <div class="sm:max-w-xl">
            <div class="flex items-center gap-2.5">
              <h3 class="text-sm font-medium text-neutral-900 group-hover:text-neutral-600 transition-colors">
                {{ room.title }}
              </h3>
              <span class="font-mono text-[10px] text-neutral-400 border border-[#E5E5E5] rounded px-1.5 py-0.5 bg-white">
                {{ room.meta }}
              </span>
            </div>
            <p class="text-xs leading-relaxed text-neutral-500 mt-1.5 font-sans">
              {{ room.desc }}
            </p>
          </div>

          <div class="mt-3 sm:mt-0 font-mono text-xs text-neutral-400 group-hover:text-neutral-900 transition-colors flex items-center gap-1 shrink-0">
            <span>进入</span>
            <span class="transition-transform duration-200 group-hover:translate-x-1">→</span>
          </div>
        </router-link>
      </div>
    </section>

    <!-- Featured Engineering Works (Typographic Editorial Stream) -->
    <section class="pt-16 border-t border-[#E5E5E5]/60">
      <div class="mb-8 flex items-center justify-between">
        <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400">
          Selected Works
        </h2>
        <router-link
          to="/projects"
          class="font-mono text-xs text-neutral-400 hover:text-neutral-950 transition-colors flex items-center gap-1"
        >
          <span>全部项目 ({{ projectList.length }})</span>
          <span>→</span>
        </router-link>
      </div>

      <div class="divide-y divide-[#E5E5E5]/60">
        <article
          v-for="p in projectList"
          :key="p.title"
          class="py-7 first:pt-0 group"
        >
          <div class="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1.5">
            <div class="flex items-center gap-2.5">
              <h3 class="text-sm font-medium text-neutral-900 group-hover:text-neutral-600 transition-colors">
                {{ p.title }}
              </h3>
              <span v-if="p.tag" class="font-mono text-[10px] text-neutral-400 border border-[#E5E5E5] rounded px-1.5 py-0.5 bg-white">
                {{ p.tag }}
              </span>
            </div>
            <span class="font-mono text-xs text-neutral-400">
              {{ p.period }}
            </span>
          </div>

          <p class="mt-2 text-xs leading-relaxed text-neutral-500 font-sans max-w-2xl">
            {{ p.summary }}
          </p>

          <div class="mt-3 flex flex-wrap gap-1.5 font-mono text-[11px]">
            <span
              v-for="t in p.stack"
              :key="t"
              class="rounded border border-[#E5E5E5] bg-white px-2 py-0.5 text-neutral-600"
            >
              {{ t }}
            </span>
          </div>
        </article>
      </div>
    </section>

  </div>
</template>