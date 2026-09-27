<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchAdminScripts,
  fetchAdminScriptSummary,
  createScript,
  updateScript,
  deleteScript,
  runScript,
  stopScript,
} from '@/api/scripts'
import type { ScriptListItem, ScriptSummary } from '@/data/scripts'
import { TYPE_LABELS } from '@/data/scripts'
import ScriptStatus from '@/components/Scripts/ScriptStatus.vue'
import AdminScriptForm from '@/components/Scripts/AdminScriptForm.vue'
import ScriptDetail from '@/components/Scripts/ScriptDetail.vue'
import RunHistory from '@/components/Scripts/RunHistory.vue'
import LogViewer from '@/components/Scripts/LogViewer.vue'

const scripts = ref<ScriptListItem[]>([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const busyId = ref<number | null>(null)

const showForm = ref(false)
const editing = ref<ScriptListItem | null>(null)
const logScriptId = ref<number | null>(null)

const detailScript = ref<ScriptListItem | null>(null)
const detailSummary = ref<ScriptSummary | null>(null)
const detailSummaryLoading = ref(false)

const historyScript = ref<ScriptListItem | null>(null)
const historyRuns = ref<any[]>([])
const historyLoading = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetchAdminScripts()
    scripts.value = res.scripts
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

const filteredScripts = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return scripts.value
  return scripts.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q) ||
      s.type.toLowerCase().includes(q),
  )
})

function openCreate() {
  editing.value = null
  showForm.value = true
}

function openEdit(s: ScriptListItem) {
  editing.value = s
  showForm.value = true
}

async function openDetail(s: ScriptListItem) {
  detailScript.value = s
  detailSummary.value = null
  detailSummaryLoading.value = true
  try {
    const res = await fetchAdminScriptSummary(s.id)
    detailSummary.value = res
  } catch {
    //
  } finally {
    detailSummaryLoading.value = false
  }
}

function closeDetail() {
  detailScript.value = null
}

async function onSubmit(payload: Record<string, any>) {
  try {
    if (editing.value) {
      await updateScript(editing.value.id, payload)
    } else {
      await createScript(payload as any)
    }
    showForm.value = false
    await load()
  } catch (e: any) {
    alert(e.message)
  }
}

async function onRun(s: ScriptListItem) {
  busyId.value = s.id
  try {
    await runScript(s.id)
    setTimeout(load, 1500)
  } catch (e: any) {
    alert(e.message)
  } finally {
    busyId.value = null
  }
}

function onDetailEdit(s: ScriptListItem) {
  closeDetail()
  openEdit(s)
}

async function onDetailStop(s: ScriptListItem) {
  closeDetail()
  await onStop(s)
}

async function onDetailDelete(s: ScriptListItem) {
  closeDetail()
  await onDelete(s)
}

function onDetailHistory(s: ScriptListItem) {
  closeDetail()
  openHistory(s)
}

function onDetailLogs(s: ScriptListItem) {
  closeDetail()
  logScriptId.value = s.id
}

async function onStop(s: ScriptListItem) {
  if (!confirm(`确定停止任务 "${s.name}" 吗？`)) return
  try {
    await stopScript(s.id)
    await load()
  } catch (e: any) {
    alert(e.message)
  }
}

async function onDelete(s: ScriptListItem) {
  if (!confirm(`确定删除任务 "${s.name}" 吗？此操作无法撤销。`)) return
  try {
    await deleteScript(s.id)
    await load()
  } catch (e: any) {
    alert(e.message)
  }
}

async function openHistory(s: ScriptListItem) {
  historyScript.value = s
  historyRuns.value = []
  historyLoading.value = true
  try {
    const res = await fetchAdminScriptSummary(s.id)
    historyRuns.value = res.recent_runs
  } catch (e: any) {
    alert(e.message)
  } finally {
    historyLoading.value = false
  }
}

function fmt(iso: string | null | undefined): string {
  return iso
    ? new Date(iso).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
    : '—'
}
</script>

<template>
  <div class="py-12 sm:py-16">
    <header class="border-b border-[#E5E5E5]/70 pb-8 mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div>
        <div class="flex items-center gap-2 font-mono text-xs text-neutral-400 mb-2">
          <span class="h-1 w-1 rounded-full bg-[#7C96A8]" />
          <span>TASK MANAGEMENT</span>
        </div>
        <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
          Script Controller
        </h1>
        <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans">
          服务器后台调度任务管理、手动运行与日志审计
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          class="font-mono text-xs px-3.5 py-1.5 bg-neutral-900 text-white rounded font-normal hover:bg-neutral-800 transition-colors cursor-pointer"
          @click="openCreate"
        >
          + New Task
        </button>
      </div>
    </header>

    <!-- Toolbar -->
    <div class="mb-6 flex items-center justify-between gap-4 font-mono text-xs">
      <input
        v-model="search"
        type="text"
        placeholder="Filter tasks…"
        class="rounded-md border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-neutral-900 focus:border-[#7C96A8] focus:outline-none w-full sm:max-w-xs transition-colors"
      />
      <span class="text-neutral-400 shrink-0">
        {{ filteredScripts.length }} tasks
      </span>
    </div>

    <div v-if="error" class="text-xs text-red-600 font-mono mb-6">
      ⚠️ {{ error }}
    </div>

    <!-- Table -->
    <div class="border border-[#E5E5E5] bg-white rounded-lg overflow-hidden">
      <table class="w-full text-left font-mono text-xs">
        <thead class="border-b border-[#E5E5E5] bg-[#FAFAFA] text-[11px] text-neutral-500">
          <tr>
            <th class="px-4 py-2.5 font-medium font-sans">任务名称</th>
            <th class="px-4 py-2.5 font-medium">类型</th>
            <th class="px-4 py-2.5 font-medium">状态</th>
            <th class="px-4 py-2.5 font-medium">上次运行</th>
            <th class="px-4 py-2.5 font-medium">下次计划</th>
            <th class="px-4 py-2.5 font-medium text-right font-sans">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#E5E5E5]/70">
          <tr
            v-for="s in filteredScripts"
            :key="s.id"
            class="hover:bg-[#FAFAFA]/70 transition-colors"
          >
            <td class="px-4 py-3 font-sans">
              <button
                type="button"
                class="font-medium text-neutral-900 hover:text-[#7C96A8] text-left cursor-pointer transition-colors"
                @click="openDetail(s)"
              >
                {{ s.name }}
              </button>
              <p class="text-xs text-neutral-400 truncate max-w-xs mt-0.5 font-sans">{{ s.description || '—' }}</p>
            </td>
            <td class="px-4 py-3 text-neutral-600">{{ TYPE_LABELS[s.type] }}</td>
            <td class="px-4 py-3">
              <ScriptStatus :status="s.status" />
            </td>
            <td class="px-4 py-3 text-neutral-500">{{ fmt(s.last_run?.start_time) }}</td>
            <td class="px-4 py-3 text-neutral-500">{{ fmt(s.next_run) }}</td>
            <td class="px-4 py-3 text-right">
              <div class="flex items-center justify-end gap-2 font-mono text-[11px]">
                <button
                  type="button"
                  :disabled="busyId === s.id"
                  class="text-neutral-900 hover:text-[#7C96A8] disabled:opacity-40 cursor-pointer"
                  @click="onRun(s)"
                >
                  Run
                </button>
                <button
                  type="button"
                  class="text-neutral-500 hover:text-neutral-900 cursor-pointer"
                  @click="openEdit(s)"
                >
                  Edit
                </button>
                <button
                  type="button"
                  class="text-neutral-500 hover:text-neutral-900 cursor-pointer"
                  @click="logScriptId = s.id"
                >
                  Logs
                </button>
                <button
                  type="button"
                  class="text-red-600 hover:underline cursor-pointer"
                  @click="onDelete(s)"
                >
                  Del
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="!filteredScripts.length">
            <td colspan="6" class="px-4 py-8 text-center text-neutral-400 font-sans">
              {{ loading ? '加载任务列表中…' : '未找到相关任务' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modals / Drawers -->
    <AdminScriptForm v-if="showForm" :script="editing" @close="showForm = false" @submit="onSubmit" />
    
    <ScriptDetail
      v-if="detailScript"
      :script="detailScript"
      :summary="detailSummary"
      :summary-loading="detailSummaryLoading"
      :busy="busyId === detailScript.id"
      @close="closeDetail"
      @run="onRun"
      @stop="onDetailStop"
      @edit="onDetailEdit"
      @del="onDetailDelete"
      @history="onDetailHistory"
      @logs="onDetailLogs"
    />

    <RunHistory
      v-if="historyScript"
      :runs="historyRuns"
      :loading="historyLoading"
      @close="historyScript = null"
    />

    <LogViewer v-if="logScriptId !== null" :script-id="logScriptId" @close="logScriptId = null" />
  </div>
</template>
