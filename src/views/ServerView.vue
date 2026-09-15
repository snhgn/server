<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api'

const status = ref<any>(null)
const loading = ref(true)
const errorMsg = ref('')
const showRaw = ref(false)

async function loadStatus() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await api.get('/api/status')
    status.value = res
  } catch (e: any) {
    errorMsg.value = e.message || '获取服务器状态失败'
  } finally {
    loading.value = false
  }
}

function formatBytes(bytes: number, decimals = 1) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
}

function formatUptime(seconds: number) {
  if (!seconds) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

onMounted(loadStatus)
</script>

<template>
  <div class="py-14 sm:py-20">
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div>
        <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
          Infrastructure Telemetry
        </div>
        <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
          Server & Node Monitor
        </h1>
        <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans">
          Ubuntu 22.04 LTS 硬件资源与 Docker 容器拓扑实时监控
        </p>
      </div>

      <div class="flex items-center gap-2 font-mono text-xs">
        <button
          type="button"
          class="px-2.5 py-1 text-neutral-500 hover:text-neutral-950 border border-[#E5E5E5] rounded bg-white hover:bg-[#FAFAFA] transition-colors cursor-pointer"
          @click="showRaw = !showRaw"
        >
          {{ showRaw ? 'Hide JSON' : 'Raw JSON' }}
        </button>
        <button
          type="button"
          :disabled="loading"
          class="px-3 py-1 bg-neutral-900 text-white rounded font-normal hover:bg-neutral-800 disabled:opacity-50 transition-colors cursor-pointer"
          @click="loadStatus"
        >
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>
    </header>

    <div v-if="errorMsg" class="text-xs text-red-600 font-mono mb-6">
      {{ errorMsg }}
    </div>

    <div v-if="loading && !status" class="py-16 text-center text-xs font-mono text-neutral-400">
      Loading telemetry data...
    </div>

    <div v-else-if="status" class="space-y-12">
      
      <!-- Node Meta Bar -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 pb-6 border-b border-[#E5E5E5]/60 font-mono text-xs">
        <div>
          <span class="text-neutral-400 block text-[10px] uppercase">Hostname</span>
          <span class="font-medium text-neutral-900 mt-1 block">{{ status.hostname }}</span>
        </div>
        <div>
          <span class="text-neutral-400 block text-[10px] uppercase">Uptime</span>
          <span class="font-medium text-neutral-900 mt-1 block">{{ formatUptime(status.uptime_seconds) }}</span>
        </div>
        <div>
          <span class="text-neutral-400 block text-[10px] uppercase">Containers</span>
          <span class="font-medium text-neutral-900 mt-1 block">{{ (status.containers || []).length }} Active</span>
        </div>
        <div>
          <span class="text-neutral-400 block text-[10px] uppercase">OS Platform</span>
          <span class="font-medium text-neutral-900 mt-1 block">Linux x86_64</span>
        </div>
      </div>

      <!-- Resource Utilization Meters -->
      <section>
        <div class="mb-4 font-mono text-xs uppercase tracking-widest text-neutral-400">
          Hardware Utilization
        </div>

        <div class="space-y-3 font-mono text-xs">
          <!-- CPU -->
          <div class="p-4 border border-[#E5E5E5] bg-white rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
            <div class="flex items-center justify-between mb-2">
              <span class="font-sans text-xs font-medium text-neutral-900">CPU Usage</span>
              <span class="text-neutral-500">{{ status.cpu?.cores }} Cores · {{ status.cpu?.percent }}%</span>
            </div>
            <div class="h-1.5 w-full bg-[#F4F5F6] rounded-full overflow-hidden">
              <div
                class="h-full bg-neutral-900 transition-all duration-300"
                :style="{ width: `${status.cpu?.percent || 0}%` }"
              />
            </div>
          </div>

          <!-- Memory -->
          <div class="p-4 border border-[#E5E5E5] bg-white rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
            <div class="flex items-center justify-between mb-2">
              <span class="font-sans text-xs font-medium text-neutral-900">RAM (Virtual Memory)</span>
              <span class="text-neutral-500">
                {{ formatBytes(status.memory?.used) }} / {{ formatBytes(status.memory?.total) }} ({{ status.memory?.percent }}%)
              </span>
            </div>
            <div class="h-1.5 w-full bg-[#F4F5F6] rounded-full overflow-hidden">
              <div
                class="h-full bg-neutral-900 transition-all duration-300"
                :style="{ width: `${status.memory?.percent || 0}%` }"
              />
            </div>
          </div>

          <!-- Disk -->
          <div class="p-4 border border-[#E5E5E5] bg-white rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
            <div class="flex items-center justify-between mb-2">
              <span class="font-sans text-xs font-medium text-neutral-900">Disk Root (/)</span>
              <span class="text-neutral-500">
                {{ formatBytes(status.disk?.used) }} / {{ formatBytes(status.disk?.total) }} ({{ status.disk?.percent }}%)
              </span>
            </div>
            <div class="h-1.5 w-full bg-[#F4F5F6] rounded-full overflow-hidden">
              <div
                class="h-full bg-neutral-900 transition-all duration-300"
                :style="{ width: `${status.disk?.percent || 0}%` }"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Docker Container Topology -->
      <section>
        <div class="mb-4 font-mono text-xs uppercase tracking-widest text-neutral-400">
          Docker Container Status
        </div>

        <div class="border border-[#E5E5E5] bg-white rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          <table class="w-full text-left font-mono text-xs">
            <thead class="border-b border-[#E5E5E5] bg-[#FAFAFA] text-[10px] uppercase text-neutral-400">
              <tr>
                <th class="px-4 py-2.5 font-medium">Container</th>
                <th class="px-4 py-2.5 font-medium">Image</th>
                <th class="px-4 py-2.5 font-medium">Status</th>
                <th class="px-4 py-2.5 font-medium">Port Bindings</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#E5E5E5]/70">
              <tr v-for="c in status.containers" :key="c.name" class="hover:bg-[#FAFAFA]/70 transition-colors">
                <td class="px-4 py-3 font-medium text-neutral-900">
                  <div class="flex items-center gap-2">
                    <span class="h-1.5 w-1.5 rounded-full bg-neutral-900" />
                    <span>{{ c.name }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 text-neutral-600 truncate max-w-xs">{{ c.image }}</td>
                <td class="px-4 py-3 text-neutral-700">{{ c.status }}</td>
                <td class="px-4 py-3 text-neutral-500">
                  {{ (c.ports || []).join(', ') || '—' }}
                </td>
              </tr>
              <tr v-if="!status.containers?.length">
                <td colspan="4" class="px-4 py-8 text-center text-neutral-400 font-sans">
                  无运行中的容器
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Raw JSON View -->
      <section v-if="showRaw">
        <div class="font-mono text-xs uppercase tracking-widest text-neutral-400 mb-2">
          Raw Gateway JSON
        </div>
        <pre class="p-4 bg-neutral-900 text-neutral-300 font-mono text-xs rounded-lg overflow-x-auto">{{ JSON.stringify(status, null, 2) }}</pre>
      </section>

    </div>
  </div>
</template>