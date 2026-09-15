<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { ScriptListItem, ScriptType, ScriptVisibility } from '@/data/scripts'
import { generateScriptCode, reviewScriptCode } from '@/api/scripts'

const props = defineProps<{
  script?: ScriptListItem | null
}>()
const emit = defineEmits<{ close: []; submit: [payload: Record<string, any>] }>()

const form = reactive({
  name: '',
  description: '',
  type: 'automation' as ScriptType,
  command: '',
  visibility: 'public' as ScriptVisibility,
  cron: '',
  enabled: true,
})

// ---- AI 生成 / 审查（仅新建模式）----
const prompt = ref('')
const generating = ref(false)
const reviewing = ref(false)
const generatedCode = ref('')
const generator = ref('')
const review = ref<{
  verdict: 'pass' | 'warn' | 'fail'
  issues: string[]
  summary: string
  reviewer: string
} | null>(null)

const VERDICT_STYLE: Record<string, { label: string; cls: string }> = {
  pass: { label: '审查通过', cls: 'bg-green-50 text-green-700 border-green-200' },
  warn: { label: '有警告', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  fail: { label: '审查不通过', cls: 'bg-red-50 text-red-700 border-red-200' },
}

watch(
  () => props.script,
  (s) => {
    form.name = s?.name ?? ''
    form.description = s?.description ?? ''
    form.type = (s?.type as ScriptType) ?? 'automation'
    form.command = s?.command ?? ''
    form.visibility = (s?.visibility as ScriptVisibility) ?? 'public'
    form.cron = s?.cron ?? ''
    form.enabled = s?.enabled ?? true
    // 重置 AI 流程状态
    prompt.value = ''
    generatedCode.value = ''
    generator.value = ''
    review.value = null
    generating.value = false
    reviewing.value = false
  },
  { immediate: true },
)

async function generate() {
  if (!form.name.trim()) {
    alert('请先填写任务名称（AI 需要它理解脚本用途）')
    return
  }
  if (prompt.value.trim().length < 10) {
    alert('请填写需求提示词（至少 10 个字，越具体生成效果越好）')
    return
  }
  generating.value = true
  review.value = null
  try {
    const res = await generateScriptCode({ name: form.name.trim(), prompt: prompt.value.trim() })
    generatedCode.value = res.code
    generator.value = res.generator
    if (!res.syntax_ok) {
      alert(`AI 生成的代码存在语法错误（${res.syntax_error}），可点击「重新生成」重试`)
      return
    }
    // 生成成功 → 自动交给另一个 AI 审查
    await reviewCode()
  } catch (e: any) {
    alert(`生成失败：${e.message}`)
  } finally {
    generating.value = false
  }
}

async function reviewCode() {
  if (!generatedCode.value.trim()) return
  reviewing.value = true
  try {
    review.value = await reviewScriptCode({
      code: generatedCode.value,
      name: form.name,
      description: form.description,
    })
  } catch (e: any) {
    alert(`审查失败：${e.message}`)
  } finally {
    reviewing.value = false
  }
}

function submit() {
  if (props.script) {
    // 编辑模式：保持原执行命令编辑
    if (!form.name.trim() || !form.command.trim()) {
      alert('任务名称与执行命令为必填项')
      return
    }
    emit('submit', { ...form, cron: form.cron.trim() || null })
    return
  }
  // 新建模式：AI 生成代码
  if (!form.name.trim()) {
    alert('任务名称为必填项')
    return
  }
  if (!generatedCode.value.trim()) {
    alert('请先填写需求提示词并点击「AI 生成代码」')
    return
  }
  if (review.value?.verdict === 'fail') {
    if (!confirm('AI 审查未通过，仍要创建该任务吗？建议先按审查意见修改代码。')) return
  }
  emit('submit', {
    name: form.name,
    description: form.description,
    type: form.type,
    code: generatedCode.value,
    visibility: form.visibility,
    cron: form.cron.trim() || null,
    enabled: form.enabled,
  })
}
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-xs p-4"
    @click.self="$emit('close')"
  >
    <div
      class="w-full rounded-md border border-neutral-200 bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto"
      :class="script ? 'max-w-md' : 'max-w-2xl'"
    >
      <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
        <h2 class="text-sm font-bold text-neutral-900">
          {{ script ? '编辑任务配置' : '新建调度任务（AI 编写）' }}
        </h2>
        <button
          type="button"
          class="text-neutral-400 hover:text-neutral-900 font-mono text-sm"
          @click="$emit('close')"
        >
          ✕
        </button>
      </div>

      <form class="mt-4 space-y-3.5 text-xs font-sans" @submit.prevent="submit">
        <div>
          <label class="block font-medium text-neutral-700 mb-1">任务名称 *</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="例如：bjfu_course_sync"
            class="w-full rounded border border-neutral-200 px-3 py-1.5 text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none"
            required
          />
        </div>

        <div>
          <label class="block font-medium text-neutral-700 mb-1">任务描述</label>
          <input
            v-model="form.description"
            type="text"
            placeholder="功能说明"
            class="w-full rounded border border-neutral-200 px-3 py-1.5 text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none"
          />
        </div>

        <!-- 新建：需求提示词 → AI 生成 → AI 审查 -->
        <template v-if="!script">
          <div>
            <label class="block font-medium text-neutral-700 mb-1">需求提示词 *</label>
            <textarea
              v-model="prompt"
              rows="3"
              placeholder="用自然语言描述这个脚本要做什么。例如：每天定时访问教务系统首页，若返回 200 且包含『登录』字样则输出 NORMAL，否则输出 ABNORMAL 并以退出码 1 结束。"
              class="w-full rounded border border-neutral-200 px-3 py-2 text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none"
            />
            <div class="mt-2 flex items-center gap-2">
              <button
                type="button"
                :disabled="generating || reviewing"
                class="rounded bg-neutral-950 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-neutral-800 disabled:opacity-50"
                @click="generate"
              >
                {{ generating ? 'AI 编写中…（约 30-90 秒）' : generatedCode ? '重新生成' : 'AI 生成代码' }}
              </button>
              <span v-if="generatedCode && !generating" class="text-neutral-400 font-mono text-[11px]">
                由 {{ generator || 'AI' }} 生成
              </span>
            </div>
          </div>

          <div v-if="generatedCode">
            <label class="block font-medium text-neutral-700 mb-1">
              脚本代码 *（可直接修改，创建时以服务器落盘文件方式运行）
            </label>
            <textarea
              v-model="generatedCode"
              rows="14"
              spellcheck="false"
              class="w-full rounded border border-neutral-700 bg-neutral-950 p-2.5 font-mono text-[11px] leading-relaxed text-neutral-200 focus:border-neutral-500 focus:outline-none"
            />

            <!-- AI 审查结果 -->
            <div class="mt-2 rounded border p-2.5" :class="review ? VERDICT_STYLE[review.verdict].cls : 'border-neutral-200 bg-neutral-50 text-neutral-500'">
              <template v-if="reviewing">
                <span class="font-medium">另一个 AI 正在审查代码…</span>
              </template>
              <template v-else-if="review">
                <div class="flex items-center justify-between">
                  <span class="font-semibold">
                    {{ VERDICT_STYLE[review.verdict].label }}
                    <span class="ml-1 font-mono font-normal opacity-60">by {{ review.reviewer }}</span>
                  </span>
                  <button
                    type="button"
                    class="underline hover:opacity-70"
                    @click="reviewCode"
                  >
                    重新审查
                  </button>
                </div>
                <p v-if="review.summary" class="mt-1">{{ review.summary }}</p>
                <ul v-if="review.issues.length" class="mt-1 list-disc pl-4 space-y-0.5">
                  <li v-for="(issue, i) in review.issues" :key="i">{{ issue }}</li>
                </ul>
              </template>
              <template v-else>
                <span>生成后可由另一个 AI 交叉审查代码安全性与正确性</span>
              </template>
            </div>
          </div>
        </template>

        <!-- 编辑：保留原执行命令 -->
        <div v-else>
          <label class="block font-medium text-neutral-700 mb-1">执行命令 *</label>
          <textarea
            v-model="form.command"
            rows="3"
            placeholder="python /opt/scripts/task.py"
            class="w-full rounded border border-neutral-200 bg-neutral-950 p-2.5 font-mono text-xs text-neutral-200 focus:border-neutral-700 focus:outline-none"
            required
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block font-medium text-neutral-700 mb-1">任务类型</label>
            <select
              v-model="form.type"
              class="w-full rounded border border-neutral-200 px-2 py-1.5 text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none"
            >
              <option value="automation">通用自动化</option>
              <option value="crawler">爬虫任务</option>
              <option value="ai_task">AI 处理</option>
              <option value="service">后台服务</option>
            </select>
          </div>

          <div>
            <label class="block font-medium text-neutral-700 mb-1">可见性</label>
            <select
              v-model="form.visibility"
              class="w-full rounded border border-neutral-200 px-2 py-1.5 text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none"
            >
              <option value="public">Public (公开)</option>
              <option value="private">Private (私有)</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block font-medium text-neutral-700 mb-1">Cron 表达式 (可选)</label>
          <input
            v-model="form.cron"
            type="text"
            placeholder="0 3 * * *"
            class="w-full rounded border border-neutral-200 px-3 py-1.5 font-mono text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none"
          />
        </div>

        <div class="flex items-center justify-between py-1">
          <span class="text-neutral-700 font-medium">启用自动调度</span>
          <button
            type="button"
            class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors cursor-pointer"
            :class="form.enabled ? 'bg-neutral-950' : 'bg-neutral-200'"
            @click="form.enabled = !form.enabled"
          >
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
              :class="form.enabled ? 'translate-x-4.5' : 'translate-x-0.5'"
            />
          </button>
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-neutral-100 pt-3">
          <button
            type="button"
            class="rounded border border-neutral-200 px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50"
            @click="$emit('close')"
          >
            取消
          </button>
          <button
            type="submit"
            :disabled="generating || reviewing"
            class="rounded bg-neutral-950 px-4 py-1.5 text-xs font-semibold text-white hover:bg-neutral-800 disabled:opacity-50"
          >
            {{ script ? '保存' : '创建' }}
          </button>
        </div>

      </form>
    </div>
  </div>
</template>
