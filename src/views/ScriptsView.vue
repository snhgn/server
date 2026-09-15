<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchScripts } from '@/api/scripts'
import type { ScriptListItem } from '@/data/scripts'
import ScriptCard from '@/components/Scripts/ScriptCard.vue'

const scripts = ref<ScriptListItem[]>([])
const loading = ref(true)
const error = ref('')

const counts = {
  running: () => scripts.value.filter((s) => s.status === 'running').length,
  waiting: () => scripts.value.filter((s) => s.status === 'waiting').length,
  failed: () => scripts.value.filter((s) => s.status === 'failed').length,
}

onMounted(async () => {
  try {
    const res = await fetchScripts()
    scripts.value = res.scripts
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="py-14 sm:py-20">
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div>
        <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
          Task Scheduler
        </div>
        <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
          Automation Scripts
        </h1>
        <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans">
          服务器后台周期任务、自动化脚本与执行记录监视
        </p>
      </div>

      <!-- Telemetry Strip -->
      <div class="flex items-center gap-4 font-mono text-xs text-neutral-500">
        <div>Running: <strong class="text-neutral-900 font-medium">{{ counts.running() }}</strong></div>
        <div>Waiting: <strong class="text-neutral-900 font-medium">{{ counts.waiting() }}</strong></div>
        <div>Failed: <strong class="text-red-600 font-medium">{{ counts.failed() }}</strong></div>
      </div>
    </header>

    <div v-if="error" class="text-xs text-red-600 font-mono mb-6">
      {{ error }}
    </div>

    <div v-if="loading" class="py-16 text-center text-xs font-mono text-neutral-400">
      Loading automation tasks...
    </div>

    <div v-else-if="!scripts.length" class="py-16 text-center text-xs font-mono text-neutral-400">
      No active tasks available.
    </div>

    <div v-else class="divide-y divide-[#E5E5E5]/60 border-t border-b border-[#E5E5E5]/60">
      <ScriptCard v-for="s in scripts" :key="s.id" :script="s" />
    </div>
  </div>
</template>