<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'
import BrandWordmark from '@/components/BrandWordmark.vue'

const route = useRoute()

interface Course {
  name: string
  teacher: string
  room: string
  weeks: string
  day: number
  period: string
  start: number
  end: number
}
interface ScheduleData {
  semester: string
  updated_time: string
  courses: Course[]
}

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const TERM_START = '2026-09-07'
const TERM_END = '2027-01-15'
const TERM_LABEL = '2026年秋季学期'

const periodSlots = [
  { start: 1, end: 2, label: '1-2', from: 480, to: 575 },
  { start: 3, end: 4, label: '3-4', from: 590, to: 685 },
  { start: 5, end: 5, label: '5', from: 685, to: 735 },
  { start: 6, end: 7, label: '6-7', from: 810, to: 905 },
  { start: 8, end: 9, label: '8-9', from: 920, to: 1015 },
  { start: 10, end: 11, label: '10-11', from: 1110, to: 1205 },
  { start: 12, end: 12, label: '12', from: 1210, to: 1255 },
]

const TOTAL_WEEKS =
  Math.floor(
    (new Date(`${TERM_END}T00:00:00`).getTime() - new Date(`${TERM_START}T00:00:00`).getTime()) /
      86400000 /
      7
  ) + 1

function blockOf(period: number): number {
  for (let i = 0; i < periodSlots.length; i++) {
    const b = periodSlots[i]
    if (period >= b.start && period <= b.end) return i + 1
  }
  return 1
}

function parseWeeks(weeks: string): number[] | null {
  const list: number[] = []
  const m = weeks.match(/\d+(?:-\d+)?/g)
  if (!m) return null
  for (const part of m) {
    if (part.includes('-')) {
      const [a, b] = part.split('-').map(Number)
      for (let i = a; i <= b; i++) list.push(i)
    } else {
      list.push(Number(part))
    }
  }
  if (!list.length) return null
  return [...new Set(list)].sort((a, b) => a - b)
}

function weekCount(weeks: string): string {
  if (!weeks) return ''
  const m = weeks.match(/(\d+)-(\d+)/)
  if (m) return `${m[1]}-${m[2]}周`
  const s = weeks.match(/\d+/)
  if (s) return `${s[0]}周`
  return weeks
}

type TermStatus = 'before' | 'during' | 'after'
interface TermState {
  status: TermStatus
  days: number
}

function termState(): TermState {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const start = new Date(`${TERM_START}T00:00:00`).getTime()
  const end = new Date(`${TERM_END}T00:00:00`).getTime()
  if (today < start) return { status: 'before', days: Math.round((start - today) / 86400000) }
  if (today > end) return { status: 'after', days: Math.round((today - end) / 86400000) }
  return { status: 'during', days: 0 }
}

function systemWeek(): number {
  const w = Math.floor((Date.now() - new Date(`${TERM_START}T00:00:00`).getTime()) / 86400000 / 7) + 1
  return Math.min(TOTAL_WEEKS, Math.max(1, w))
}

function semesterLabel(semester: string): string {
  const m = semester.match(/(\d{4})-(\d{4})-(\d)/)
  if (m) {
    const [, a, b, term] = m
    const season = term === '1' ? '秋季' : term === '2' ? '春季' : term === '3' ? '夏季' : ''
    const year = term === '1' ? a : b
    return `${year}年${season}学期`
  }
  return semester
}

function getDateLabel(week: number, dayIdx: number): string {
  const [y, m, d] = TERM_START.split('-').map(Number)
  const date = new Date(y, m - 1, d + (week - 1) * 7 + dayIdx)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

const studentId = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const showForm = ref(true)
const switching = ref(false)
const schedule = ref<ScheduleData | null>(null)
const detail = ref<Course | null>(null)
const viewer = ref<'calendar' | 'time' | null>(null)

function closeImgViewer() {
  viewer.value = null
}

// 每次重新打开默认跳转到当天对应的当前真实周次
const currentWeek = ref(systemWeek())
const gridContainer = ref<HTMLElement | null>(null)

function scrollToToday() {
  nextTick(() => {
    const el = document.querySelector('.today-col-header') as HTMLElement
    const container = gridContainer.value
    if (el && container) {
      // 留出左侧固定“节次”列的宽度 (~42px)
      const left = el.offsetLeft - container.offsetLeft - 44
      container.scrollTo({ left: Math.max(0, left), behavior: 'smooth' })
    }
  })
}

function goToToday() {
  const todayWeek = systemWeek()
  if (currentWeek.value !== todayWeek) {
    switching.value = true
    currentWeek.value = todayWeek
    setTimeout(() => {
      switching.value = false
      scrollToToday()
    }, 160)
  } else {
    scrollToToday()
  }
}

function changeWeek(delta: number) {
  const next = Math.min(TOTAL_WEEKS, Math.max(1, currentWeek.value + delta))
  if (next === currentWeek.value) return
  switching.value = true
  setTimeout(() => {
    currentWeek.value = next
    requestAnimationFrame(() => {
      switching.value = false
    })
  }, 160)
}

onMounted(async () => {
  document.body.classList.add('schedule-page')

  // 1. 若 URL 中明确指定了学号或用户 ID（如分享链接 ?student_id=xxx 或 ?user_id=xxx）
  const qSid = (route.query.student_id || route.query.sid) as string | undefined
  const qUid = (route.query.user_id || route.query.uid) as string | undefined
  if (qSid && qSid.trim()) {
    try {
      schedule.value = await api.get<ScheduleData>(`/api/schedule/query?student_id=${encodeURIComponent(qSid.trim())}`)
      studentId.value = qSid.trim()
      showForm.value = false
      scrollToToday()
      return
    } catch {
      // 指定学号无课表时回退常规流程
    }
  } else if (qUid && qUid.trim()) {
    try {
      schedule.value = await api.get<ScheduleData>(`/api/schedule/view/${encodeURIComponent(qUid.trim())}`)
      showForm.value = false
      scrollToToday()
      return
    } catch {
      // 指定用户无课表时回退常规流程
    }
  }

  // 2. 优先尝试拉取当前登录用户 / 访客 Session 缓存的课表
  try {
    schedule.value = await api.get<ScheduleData>('/api/schedule/current')
    showForm.value = false
    scrollToToday()
    return
  } catch {
    // 3. 未登录状态下，优先尝试读取本设备此前保存过的学号
    const sid = localStorage.getItem('bjfu-student-id')
    if (sid) {
      try {
        schedule.value = await api.get<ScheduleData>(`/api/schedule/query?student_id=${encodeURIComponent(sid)}`)
        studentId.value = sid
        showForm.value = false
        scrollToToday()
        return
      } catch {
        // Fallthrough
      }
    }
    // 4. 新用户/访客且无本地学号：展示登录输入表单，严禁自动加载任何其他用户的课表！
    showForm.value = true
  }
})
onUnmounted(() => {
  document.body.classList.remove('schedule-page')
})

async function loadDemoSchedule() {
  loading.value = true
  error.value = ''
  try {
    schedule.value = await api.get<ScheduleData>('/api/schedule/view/1')
    showForm.value = false
    scrollToToday()
  } catch {
    error.value = '暂无示例课表数据'
  } finally {
    loading.value = false
  }
}

async function fetchSchedule(force = false) {
  if (!studentId.value.trim() || !password.value) {
    error.value = '请输入学号和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    schedule.value = await api.post<ScheduleData>('/api/schedule/get', {
      student_id: studentId.value.trim(),
      password: password.value,
      force,
    })
    localStorage.setItem('bjfu-student-id', studentId.value.trim())
    showForm.value = false
    scrollToToday()
  } catch (err: any) {
    error.value = err.message || '获取失败，请重试'
  } finally {
    loading.value = false
  }
}

async function refresh() {
  if (!studentId.value.trim() || !password.value) {
    showForm.value = true
    return
  }
  switching.value = true
  try {
    await fetchSchedule(true)
  } finally {
    setTimeout(() => (switching.value = false), 200)
  }
}

const weekCourses = computed<Course[]>(() => {
  const week = currentWeek.value
  return (schedule.value?.courses ?? []).filter((c) => {
    const list = parseWeeks(c.weeks)
    return list === null || list.includes(week)
  })
})

interface TodayState {
  type: 'ongoing' | 'next' | 'none'
  course: Course | null
  label: string
}

const nowDay = computed(() => {
  const d = new Date().getDay()
  return d === 0 ? 7 : d
})

function isToday(idx: number): boolean {
  return currentWeek.value === systemWeek() && idx + 1 === nowDay.value
}

const termStatus = computed<TermState>(() => termState())

const termTip = computed(() => {
  const t = termStatus.value
  if (t.status === 'before') return `假期中 · 距 ${TERM_LABEL} 开学还有 ${t.days} 天`
  if (t.status === 'after') return `${TERM_LABEL} 课程已结束`
  return ''
})

const todayState = computed<TodayState>(() => {
  const now = new Date()
  const today = now.getDay() === 0 ? 7 : now.getDay()
  const mins = now.getHours() * 60 + now.getMinutes()

  // 严格以实际当前真实周数判断，不受页面选中的浏览周数影响
  const realWeek = systemWeek()
  const todayCourses = (schedule.value?.courses ?? [])
    .filter((c) => {
      const list = parseWeeks(c.weeks)
      const matchesWeek = list === null || list.includes(realWeek)
      return matchesWeek && c.day === today
    })
    .sort((a, b) => blockOf(a.start) - blockOf(b.start))

  const ongoing = todayCourses.find((c) => {
    const b = periodSlots[blockOf(c.start) - 1]
    return mins >= b.from && mins < b.to
  })
  if (ongoing) return { type: 'ongoing', course: ongoing, label: '正在进行' }

  const next = todayCourses.find((c) => {
    const b = periodSlots[blockOf(c.start) - 1]
    return mins < b.from
  })
  if (next) {
    const b = periodSlots[blockOf(next.start) - 1]
    const h = Math.floor(b.from / 60)
    const mm = b.from % 60
    return { type: 'next', course: next, label: `下一节 ${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}` }
  }
  return { type: 'none', course: null, label: '今日暂无课程' }
})

interface PlacedCourse extends Course {
  key: string
  stackIndex: number
}
const placedCourses = computed<PlacedCourse[]>(() => {
  const groups = new Map<string, number>()
  return weekCourses.value.map((c, i) => {
    const key = `${c.day}-${blockOf(c.start)}`
    const idx = groups.get(key) ?? 0
    groups.set(key, idx + 1)
    return {
      ...c,
      key: `${c.day}-${c.start}-${c.name}-${i}`,
      stackIndex: idx,
    }
  })
})

function weekdayName(day: number): string {
  return weekdays[day - 1] ?? ''
}
</script>

<template>
  <div class="py-4 sm:py-12">
    <!-- Top Header -->
    <header class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-4 border-b border-[#E5E5E5]/70 pb-3 sm:pb-6 mb-3 sm:mb-8">
      <div>
        <div class="flex items-center gap-2 font-mono text-[11px] sm:text-xs text-neutral-400 uppercase tracking-widest mb-0.5 sm:mb-1.5">
          <BrandWordmark size="xs" :animated-dot="false" />
          <span class="text-neutral-300">·</span>
          <span>Timetable</span>
          <span v-if="schedule" class="text-neutral-300">·</span>
          <span v-if="schedule" class="text-neutral-600 font-sans font-normal">{{ semesterLabel(schedule.semester) }}</span>
        </div>
        <h1 class="text-xl sm:text-2xl font-light tracking-tight text-neutral-900 font-sans">
          智能课表
        </h1>
      </div>

      <div class="flex items-center gap-2 sm:gap-2.5 flex-wrap">
        <!-- Week Navigation -->
        <nav v-if="schedule && !showForm" class="flex items-center rounded border border-[#E5E5E5] bg-white font-mono text-xs shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          <button
            class="px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-950 disabled:opacity-30 cursor-pointer"
            :disabled="currentWeek <= 1"
            @click="changeWeek(-1)"
          >
            ←
          </button>
          <span class="px-2 font-medium text-neutral-900 border-x border-[#E5E5E5]/80 text-[11px] sm:text-xs">第 {{ currentWeek }} 周</span>
          <button
            class="px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-950 disabled:opacity-30 cursor-pointer"
            :disabled="currentWeek >= TOTAL_WEEKS"
            @click="changeWeek(1)"
          >
            →
          </button>
        </nav>

        <!-- Actions -->
        <div class="flex items-center gap-1.5 font-mono text-xs">
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] bg-white px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-900 hover:border-neutral-400 transition-colors cursor-pointer text-[11px] sm:text-xs font-medium"
            :class="{ 'bg-neutral-100 text-neutral-900 border-neutral-300 font-semibold': currentWeek === systemWeek() }"
            title="快速跳转到当天"
            @click="goToToday"
          >
            Today
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] bg-white px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-900 hover:border-neutral-400 transition-colors cursor-pointer text-[11px] sm:text-xs"
            title="校历与作息时间表"
            @click="viewer = 'calendar'"
          >
            Calendar
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] bg-white px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-900 hover:border-neutral-400 disabled:opacity-50 transition-colors cursor-pointer text-[11px] sm:text-xs"
            title="刷新课表"
            :disabled="loading"
            @click="refresh"
          >
            Sync
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] bg-white px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-900 hover:border-neutral-400 transition-colors cursor-pointer text-[11px] sm:text-xs"
            title="更换学号或重新同步"
            @click="showForm = true"
          >
            切换学号
          </button>
        </div>
      </div>
    </header>

    <!-- First Visit / Sync Form -->
    <section v-if="showForm" class="max-w-md mx-auto rounded-lg border border-[#E5E5E5] bg-white p-6 sm:p-8 shadow-[0_1px_3px_rgba(0,0,0,0.02)] my-4 sm:my-8">
      <div class="flex items-center justify-between mb-1">
        <h2 class="text-base font-medium text-neutral-900 font-sans">同步教务课表</h2>
        <button
          v-if="schedule"
          type="button"
          class="text-xs font-mono text-neutral-400 hover:text-neutral-900 transition-colors cursor-pointer"
          @click="showForm = false"
        >
          ✕ 返回课表
        </button>
      </div>
      <p class="text-xs text-neutral-500 font-sans leading-relaxed mb-6">
        输入教务学号与密码同步个人课表。密码仅在本次会话内存中使用，不落盘存储。
      </p>
      <form class="space-y-4 font-mono text-xs" @submit.prevent="fetchSchedule()">
        <div>
          <label class="block uppercase tracking-widest text-neutral-400 text-[10px] mb-1">Student ID</label>
          <input
            v-model="studentId"
            type="text"
            placeholder="学号"
            class="w-full rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-neutral-900 focus:border-neutral-900 focus:bg-white focus:outline-none"
          />
        </div>
        <div>
          <label class="block uppercase tracking-widest text-neutral-400 text-[10px] mb-1">Password</label>
          <input
            v-model="password"
            type="password"
            placeholder="密码"
            class="w-full rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-neutral-900 focus:border-neutral-900 focus:bg-white focus:outline-none"
          />
        </div>
        <p v-if="error" class="text-red-600 text-xs">{{ error }}</p>
        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded bg-neutral-900 py-2.5 text-white hover:bg-neutral-800 disabled:opacity-50 transition-colors cursor-pointer"
        >
          {{ loading ? 'Synchronizing...' : 'Sync Timetable' }}
        </button>
      </form>

      <!-- 体验示例课表入口（用户主动点击，绝不默认加载） -->
      <div class="mt-6 pt-4 border-t border-neutral-100 flex items-center justify-between text-xs font-mono text-neutral-400">
        <span>没有教务账号？</span>
        <button
          type="button"
          class="text-neutral-700 hover:text-neutral-950 underline transition-colors cursor-pointer"
          @click="loadDemoSchedule"
        >
          查看示例课表 →
        </button>
      </div>
    </section>

    <!-- Main Timetable Content -->
    <template v-else-if="schedule">
      
      <!-- Today's Status Banner -->
      <div class="mb-3 sm:mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-2 rounded border border-[#E5E5E5] bg-white px-2.5 py-1.5 sm:p-3 font-mono text-[11px] sm:text-xs shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
        <div class="flex items-center gap-2 sm:gap-2.5">
          <span class="h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-neutral-900 shrink-0" />
          <span class="font-medium text-neutral-900 shrink-0">{{ todayState.label }}:</span>
          <span v-if="todayState.course" class="text-neutral-700 font-sans font-medium truncate">
            {{ todayState.course.name }} ({{ todayState.course.room }})
          </span>
          <span v-else class="text-neutral-400 font-sans">
            今日暂无安排课程
          </span>
        </div>
        <div v-if="termTip" class="text-neutral-400 text-[10px] sm:text-[11px]">
          {{ termTip }}
        </div>
      </div>

      <!-- Timetable Grid -->
      <div ref="gridContainer" class="overflow-x-auto rounded-lg border border-[#E5E5E5] bg-white p-0.5 sm:p-2 shadow-[0_1px_3px_rgba(0,0,0,0.02)] scroll-smooth">
        <div class="grid grid-cols-[40px_repeat(7,1fr)] sm:grid-cols-[56px_repeat(7,1fr)] gap-0.5 sm:gap-1.5 min-w-[580px] sm:min-w-[800px]">
          
          <!-- Column Headers: Weekdays & Dates -->
          <div class="sticky left-0 z-20 bg-white p-1 sm:p-2 flex flex-col items-center justify-center font-mono text-[9px] sm:text-[11px] text-neutral-400 border-r border-[#E5E5E5]/50">
            <span class="leading-tight">节次</span>
          </div>
          <div
            v-for="(day, idx) in weekdays"
            :key="day"
            class="flex flex-col items-center justify-center p-1 sm:p-2 text-center font-mono rounded transition-colors"
            :class="isToday(idx) ? 'today-col-header bg-neutral-900 text-white shadow-sm' : 'text-neutral-700 bg-[#FAFAFA]'"
          >
            <span class="text-[10px] sm:text-xs font-medium leading-tight">{{ day }}</span>
            <span
              class="text-[8px] sm:text-[10px] mt-0.5 font-normal leading-tight tracking-tight scale-90 sm:scale-100 origin-center"
              :class="isToday(idx) ? 'text-neutral-300' : 'text-neutral-400'"
            >
              {{ getDateLabel(currentWeek, idx) }}
            </span>
          </div>

          <!-- Period Rows -->
          <template v-for="(slot, sIdx) in periodSlots" :key="slot.label">
            <!-- Period Label Column -->
            <div class="sticky left-0 z-10 flex flex-col items-center justify-center p-0.5 sm:p-2 rounded-l bg-[#FAFAFA] font-mono text-[9px] sm:text-[11px] text-neutral-500 border border-neutral-100 border-r-[#E5E5E5]/50 shadow-[2px_0_4px_-2px_rgba(0,0,0,0.03)]">
              <span class="font-semibold text-neutral-700 text-[9px] sm:text-[11px]">{{ slot.label }}</span>
              <span class="text-[7.5px] sm:text-[9px] text-neutral-400 mt-0.5 whitespace-nowrap scale-90 sm:scale-100 origin-center">
                {{ String(Math.floor(slot.from/60)).padStart(2,'0') }}:{{ String(slot.from%60).padStart(2,'0') }}
              </span>
            </div>

            <!-- 7 Days Grid Cells for this Period Slot -->
            <div
              v-for="d in 7"
              :key="`${sIdx}-${d}`"
              class="relative rounded border border-neutral-100 min-h-[50px] sm:min-h-[72px] bg-white p-0.5 sm:p-1"
            >
              <!-- Placed course in this cell -->
              <template v-for="c in placedCourses" :key="c.key">
                <div
                  v-if="c.day === d && blockOf(c.start) === sIdx + 1"
                  class="rounded border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 p-1 sm:p-1.5 transition-all cursor-pointer h-full flex flex-col justify-between overflow-hidden"
                  @click="detail = c"
                >
                  <div>
                    <div class="font-medium text-neutral-900 font-sans line-clamp-2 leading-tight sm:leading-snug text-[9.5px] sm:text-xs">
                      {{ c.name }}
                    </div>
                  </div>
                  <div class="font-mono text-[8px] sm:text-[10px] text-neutral-500 mt-0.5 sm:mt-1 flex items-center justify-between gap-0.5">
                    <span class="truncate">{{ c.room || '待定' }}</span>
                    <span class="text-neutral-400 shrink-0 hidden sm:inline">{{ weekCount(c.weeks) }}</span>
                  </div>
                </div>
              </template>
            </div>
          </template>

        </div>
      </div>

    </template>

    <!-- Course Detail Modal -->
    <div
      v-if="detail"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-xs p-4"
      @click.self="detail = null"
    >
      <div class="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl border border-[#E5E5E5]">
        <div class="flex items-center justify-between mb-4 border-b border-neutral-100 pb-3">
          <h3 class="text-sm font-medium text-neutral-900 font-sans">课程详情</h3>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="detail = null">✕</button>
        </div>
        <div class="space-y-3 font-mono text-xs">
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">Course Name</span>
            <span class="text-neutral-900 font-sans font-medium text-sm">{{ detail.name }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">Teacher</span>
            <span class="text-neutral-700 font-sans">{{ detail.teacher || '—' }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">Location</span>
            <span class="text-neutral-700">{{ detail.room || '—' }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">Time & Day</span>
            <span class="text-neutral-700">{{ weekdayName(detail.day) }} · {{ detail.period }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">Weeks</span>
            <span class="text-neutral-700">{{ weekCount(detail.weeks) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Calendar / Time Viewer Modal -->
    <div
      v-if="viewer"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      @click.self="closeImgViewer"
    >
      <div class="w-full max-w-3xl rounded-lg bg-white p-5 shadow-2xl border border-[#E5E5E5]">
        <div class="flex items-center justify-between mb-4">
          <div class="flex gap-2 font-mono text-xs">
            <button
              class="px-3 py-1 rounded transition-colors cursor-pointer"
              :class="viewer === 'calendar' ? 'bg-neutral-900 text-white' : 'border border-[#E5E5E5] text-neutral-600 hover:text-neutral-900'"
              @click="viewer = 'calendar'"
            >
              School Calendar
            </button>
            <button
              class="px-3 py-1 rounded transition-colors cursor-pointer"
              :class="viewer === 'time' ? 'bg-neutral-900 text-white' : 'border border-[#E5E5E5] text-neutral-600 hover:text-neutral-900'"
              @click="viewer = 'time'"
            >
              Period Schedule
            </button>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="closeImgViewer">✕</button>
        </div>

        <div class="overflow-auto max-h-[75vh] rounded border border-neutral-100 flex items-center justify-center bg-[#FAFAFA] p-2">
          <img
            v-if="viewer === 'calendar'"
            src="/images/calendar.jpg"
            alt="校历"
            class="max-h-[70vh] object-contain rounded"
          />
          <img
            v-else
            src="/images/school-time.jpg"
            alt="作息时间表"
            class="max-h-[70vh] object-contain rounded"
          />
        </div>
      </div>
    </div>

  </div>
</template>
