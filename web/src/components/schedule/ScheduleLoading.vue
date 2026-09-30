<script setup lang="ts">
/**
 * 课表同步缓冲界面。
 *
 * 为什么需要它
 * ------------
 * 课表抓取要走强智教务（取验证码 + 识别 + 登录 + 解析），冷启动常见 1~3 秒，
 * 会话池未命中时更久。原来的占位只有一个居中 spinner，信息量为零：用户不知道
 * 在做什么、还要多久，也无从判断是"正常等待"还是"卡住了"。
 *
 * 诚实优先
 * --------
 * HTTP 请求没有中间态，**真实百分比无法获知**，后端抓取细节前端也看不到。
 * 所以这里只表达两件能证实的事：确实在动、确实还没结束。
 * 刻意不做"阶段进度条"：读缓存是同步的（在首帧前就完了），剩下只有一段等待，
 * 画成多阶段轨道只是装饰，反而在暗示并不存在的进度信息。
 *
 * 三种模式
 * --------
 * - `boot`   首次进入且无本地缓存：整页展示（wordmark + 骨架屏）
 * - `submit` 已有课表时手动同步：课表留在下面，只在顶上冒一个提示卡
 * - `inline` 表单按钮下方：极简，一条短文字 + 细进度条
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import BrandWordmark from '@/components/BrandWordmark.vue'

export type Phase = 'idle' | 'remote' | 'done' | 'error'

const props = withDefaults(
  defineProps<{
    mode?: 'boot' | 'submit' | 'inline'
    phase?: Phase
    /** 骨架屏出现前的等待（ms）。快于此的请求静默完成，不闪一下 */
    delay?: number
    /** 超过该时长仍未完成，改为安抚文案（ms） */
    slowAfter?: number
  }>(),
  {
    mode: 'boot',
    phase: 'remote',
    delay: 200,
    slowAfter: 6000,
  }
)

const PHASE_TEXT: Record<Phase, string> = {
  idle: '准备中',
  remote: '正在连接教务系统',
  done: '完成',
  error: '同步失败',
}

const isBusy = (p: Phase) => p === 'remote'

// ---- 短请求不闪骨架 ----
// 会话池命中时只要几十毫秒。此时闪一下骨架屏是噪音，"什么都没发生"反而更好。
const delayed = computed(() => props.mode !== 'inline')
const pastDelay = ref(!delayed.value)
const shown = computed(() => !delayed.value || pastDelay.value)

const elapsed = ref(0)
let delayTimer: ReturnType<typeof setTimeout> | null = null
let tickTimer: ReturnType<typeof setInterval> | null = null

watch(
  () => props.phase,
  (p) => {
    if (delayTimer) {
      clearTimeout(delayTimer)
      delayTimer = null
    }
    if (!isBusy(p)) {
      pastDelay.value = !delayed.value
      return
    }
    // 每次进入等待都重新计时：慢文案和"防闪"都以本轮请求为基准
    elapsed.value = 0
    pastDelay.value = !delayed.value
    if (delayed.value && !pastDelay.value) {
      delayTimer = setTimeout(() => (pastDelay.value = true), props.delay)
    }
    if (tickTimer) clearInterval(tickTimer)
    tickTimer = setInterval(() => (elapsed.value += 100), 100)
  },
  { immediate: true }
)

onUnmounted(() => {
  if (delayTimer) clearTimeout(delayTimer)
  if (tickTimer) clearInterval(tickTimer)
})

const currentText = computed(() => PHASE_TEXT[props.phase] || PHASE_TEXT.idle)
const isSlow = computed(() => elapsed.value >= props.slowAfter)
</script>

<template>
  <!-- inline：表单按钮下方，一条短文字 + 细进度条 -->
  <div
    v-if="mode === 'inline'"
    class="flex items-center justify-center gap-2 font-mono text-[11px] text-neutral-400"
    role="status"
    aria-live="polite"
  >
    <span class="relative h-px w-16 overflow-hidden bg-neutral-200 dark:bg-neutral-800">
      <span
        class="absolute inset-y-0 left-0 bg-neutral-400 transition-[width] duration-500 ease-out dark:bg-neutral-500"
        :style="{ width: isSlow ? '85%' : '45%' }"
      />
    </span>
    <span>{{ currentText }}</span>
  </div>

  <!-- submit：课表留在下面，只在顶上冒一个提示卡（不遮挡、不打断浏览） -->
  <div
    v-else-if="mode === 'submit'"
    v-show="shown"
    class="flex items-center gap-2.5 rounded-md border border-neutral-200 bg-white/95 px-3.5 py-2 shadow-sm backdrop-blur-sm dark:border-neutral-700 dark:bg-[#1a1d21]/95"
    role="status"
    aria-live="polite"
  >
    <span class="relative h-px w-14 overflow-hidden bg-neutral-200 dark:bg-neutral-800">
      <span
        class="absolute inset-y-0 left-0 bg-neutral-600 dark:bg-neutral-400"
        :style="{ width: isSlow ? '85%' : '40%' }"
      />
    </span>
    <span class="font-sans text-[11px] text-neutral-700 dark:text-neutral-300">{{ currentText }}</span>
  </div>

  <!-- boot：首次进入且无缓存，整页展示 -->
  <div
    v-else
    v-show="shown"
    class="mx-auto flex w-full max-w-2xl flex-col items-center px-4 py-16"
    role="status"
    aria-live="polite"
  >
    <BrandWordmark size="md" class="opacity-60" />

    <p class="mt-7 font-sans text-sm text-neutral-700 dark:text-neutral-300">{{ currentText }}</p>

    <!-- 骨架屏：先给"课表长什么样"一个预期，行列与真实表格对齐 -->
    <div class="mt-8 w-full space-y-1.5" aria-hidden="true">
      <div class="flex gap-1.5">
        <span class="h-2 w-10 animate-pulse rounded-sm bg-neutral-200 dark:bg-neutral-800" />
        <span class="h-2 w-14 animate-pulse rounded-sm bg-neutral-100 dark:bg-neutral-800/60" />
      </div>
      <div v-for="row in 4" :key="row" class="flex gap-1.5">
        <span
          v-for="col in 6"
          :key="col"
          class="h-7 flex-1 animate-pulse rounded-sm bg-neutral-100 dark:bg-neutral-800/60"
          :style="{ animationDelay: `${(row - 1) * 6 + col} * 24}ms` }"
        />
      </div>
    </div>

    <p v-if="isSlow" class="mt-6 font-sans text-[11px] text-neutral-400">
      教务系统响应较慢，通常在几秒内完成
    </p>
  </div>
</template>

<style scoped>
/* 尊重系统级动效偏好：关掉骨架屏的逐格淡入 */
@media (prefers-reduced-motion: reduce) {
  .animate-pulse {
    animation: none !important;
  }
}
</style>
