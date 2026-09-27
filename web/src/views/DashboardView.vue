<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const { username, role } = useAuth()
const stats = ref<any>(null)
const loading = ref(true)

async function loadDashboard() {
  loading.value = true
  try {
    const res = await api.get('/api/status')
    stats.value = res
  } catch {
    //
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <div class="py-14 sm:py-20">
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div>
        <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
          Administration Console
        </div>
        <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
          System Dashboard
        </h1>
        <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans">
          全局节点运行概览与管理空间入口
        </p>
      </div>

      <div class="flex items-center gap-2 font-mono text-xs text-neutral-500">
        <span>Logged in as: <strong class="text-neutral-900 font-medium">{{ username }}</strong> ({{ role }})</span>
      </div>
    </header>

    <div class="grid gap-5 sm:grid-cols-3">
      <!-- Admin Rooms -->
      <router-link
        to="/admin/scripts"
        class="group flex flex-col justify-between rounded-lg border border-[#E5E5E5] bg-white p-6 transition-all hover:border-neutral-900 shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
      >
        <div>
          <div class="font-mono text-[10px] uppercase tracking-widest text-neutral-400 mb-2">
            01 / Automation
          </div>
          <h3 class="text-sm font-medium text-neutral-900 font-sans">
            脚本自动化管理
          </h3>
          <p class="mt-2 text-xs leading-relaxed text-neutral-500 font-sans">
            调度任务配置、AI 代码生成、多模型交叉审查与执行日志审计。
          </p>
        </div>
        <div class="mt-6 flex items-center justify-between border-t border-neutral-100 pt-3 font-mono text-xs text-neutral-400 group-hover:text-neutral-900">
          <span>Manage Scripts</span>
          <span>→</span>
        </div>
      </router-link>

      <router-link
        to="/knowledge"
        class="group flex flex-col justify-between rounded-lg border border-[#E5E5E5] bg-white p-6 transition-all hover:border-neutral-900 shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
      >
        <div>
          <div class="font-mono text-[10px] uppercase tracking-widest text-neutral-400 mb-2">
            02 / Memory & RAG
          </div>
          <h3 class="text-sm font-medium text-neutral-900 font-sans">
            AI 知识库与记忆
          </h3>
          <p class="mt-2 text-xs leading-relaxed text-neutral-500 font-sans">
            对话沉淀记忆检索、用户偏好审查与向量知识库切片管理。
          </p>
        </div>
        <div class="mt-6 flex items-center justify-between border-t border-neutral-100 pt-3 font-mono text-xs text-neutral-400 group-hover:text-neutral-900">
          <span>Inspect Knowledge</span>
          <span>→</span>
        </div>
      </router-link>

      <router-link
        to="/server"
        class="group flex flex-col justify-between rounded-lg border border-[#E5E5E5] bg-white p-6 transition-all hover:border-neutral-900 shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
      >
        <div>
          <div class="font-mono text-[10px] uppercase tracking-widest text-neutral-400 mb-2">
            03 / Infrastructure
          </div>
          <h3 class="text-sm font-medium text-neutral-900 font-sans">
            服务器与容器监控
          </h3>
          <p class="mt-2 text-xs leading-relaxed text-neutral-500 font-sans">
            CPU/内存/磁盘利用率与核心 Docker 容器实时健康状态拓扑。
          </p>
        </div>
        <div class="mt-6 flex items-center justify-between border-t border-neutral-100 pt-3 font-mono text-xs text-neutral-400 group-hover:text-neutral-900">
          <span>Open Telemetry</span>
          <span>→</span>
        </div>
      </router-link>
    </div>
  </div>
</template>