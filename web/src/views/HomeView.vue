<script setup lang="ts">
import { computed } from 'vue'
import { useAuth } from '@/stores/auth'
import { projectList } from '@/data/projects'
import BrandWordmark from '@/components/BrandWordmark.vue'

const { isAdmin, isUser, isAuthenticated } = useAuth()

const digitalRooms = computed(() => {
  const sid = (typeof localStorage !== 'undefined' ? localStorage.getItem('bjfu-student-id') : '') || ''
  const schedulePath = sid.trim() ? `/schedule?user=${encodeURIComponent(sid.trim())}` : '/schedule'

  return [
    {
      title: 'Projects & Hardware',
      desc: '嵌入式底层驱动、RoboMaster 机器人控制、机器视觉伺服与软硬件协同',
      to: '/projects',
      meta: 'Engineering',
      accent: 'blue',
    },
    {
      title: 'AI Workspace',
      desc: '私有化双引擎协作工作台，支持偏好记忆沉淀与多维知识库 RAG',
      to: isAuthenticated.value ? '/ai' : '/login',
      meta: 'Workspace',
      accent: 'red',
    },
    {
      title: 'Schedule & Calendar',
      desc: '北京林业大学教务数据同步、实时节次时刻分析与学期校历视图',
      to: schedulePath,
      meta: 'Tool',
      accent: 'green',
    },
    {
      title: 'Server & Infrastructure',
      desc: 'Ubuntu 宿主节点拓扑、Cloudflare 零信任通道与自动化定时任务中心',
      to: isAdmin.value ? '/server' : (isUser.value ? '/scripts' : '/login'),
      meta: 'System',
      accent: 'yellow',
    },
  ]
})
</script>

<template>
  <div class="py-10 sm:py-16">

    <!-- Hero -->
    <section class="py-10 text-center sm:py-16">

      <div class="mb-4 flex justify-center">
        <BrandWordmark size="hero" />
      </div>

      <p class="md2-body1 mt-3 text-ink-secondary">
        Stay curious, keep building.
      </p>

      <p class="mx-auto mt-8 max-w-lg text-ink-secondary md2-body1">
        一个由个人长期维护的独立数字空间与工程工坊。<br>
        专注于嵌入式底层、机器视觉、AI 协作系统与私有化基础设施。
      </p>

      <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
        <router-link
          :to="digitalRooms[2].to"
          class="md2-btn md2-btn--contained h-11 px-6"
        >
          查看课表
        </router-link>
        <router-link
          to="/projects"
          class="md2-btn md2-btn--outlined h-11 px-6"
        >
          浏览项目
        </router-link>
      </div>

    </section>

    <!-- Digital Rooms (MD2 card grid) -->
    <section class="mt-12 sm:mt-16">
      <div class="mb-5 flex items-center justify-between">
        <h2 class="md2-section-title">Digital Rooms</h2>
        <span class="md2-caption text-ink-secondary">{{ digitalRooms.length }} Spaces</span>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <router-link
          v-for="room in digitalRooms"
          :key="room.title"
          :to="room.to"
          :data-accent="room.accent"
          class="group md2-card md2-state md2-interactive md2-accent-top flex flex-col p-5 no-underline"
        >
          <div class="flex items-center gap-2">
            <h3 class="md2-h6 flex-1 text-on-surface">{{ room.title }}</h3>
            <span class="md2-chip md2-chip--accent h-6 px-2 md2-caption uppercase tracking-wider">
              {{ room.meta }}
            </span>
          </div>

          <p class="mt-2 flex-1 text-ink-secondary md2-body2">{{ room.desc }}</p>

          <!-- 走 --accent-ink（该色的可读版），不是 --accent-bar：
               bar 是品牌原色，当文字色不过 4.5:1 -->
          <div class="md2-accent-ink mt-4 flex items-center gap-1 md2-label">
            <span>进入</span>
            <span class="transition-transform duration-200 group-hover:translate-x-1">→</span>
          </div>
        </router-link>
      </div>
    </section>

    <!-- Selected Works -->
    <section class="mt-12 sm:mt-16">
      <div class="mb-5 flex items-center justify-between">
        <h2 class="md2-section-title">Selected Works</h2>
        <router-link
          to="/projects"
          class="md2-btn md2-btn--sentence h-8 min-w-0 px-2 text-ink-secondary"
        >
          全部项目 ({{ projectList.length }})
        </router-link>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <article
          v-for="p in projectList"
          :key="p.title"
          :data-accent="p.accent"
          class="md2-card md2-accent-top flex flex-col p-5"
        >
          <div class="flex items-start justify-between gap-2">
            <h3 class="md2-h6 text-on-surface">{{ p.title }}</h3>
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
    </section>

  </div>
</template>
