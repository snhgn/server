<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import BrandWordmark from '@/components/BrandWordmark.vue'
import ToolboxModal from '@/components/schedule/ToolboxModal.vue'

const route = useRoute()
const router = useRouter()

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

const savedSid = localStorage.getItem('bjfu-student-id') || ''
const savedPwd = localStorage.getItem('bjfu-student-pwd') || ''
const remember = localStorage.getItem('bjfu-remember-credentials') === 'true'
const hasSavedCredentials = remember && !!savedSid.trim() && !!savedPwd

// 尝试从本地持久化缓存立即读取已有课表（实现 0ms 秒开呈现）
function loadCachedSchedule(): ScheduleData | null {
  if (!savedSid.trim()) return null
  try {
    const raw = localStorage.getItem(`bjfu-schedule-cache-${savedSid.trim()}`) || localStorage.getItem('bjfu-schedule-cache')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed && Array.isArray(parsed.courses)) return parsed
    }
  } catch {}
  return null
}

const studentId = ref(savedSid)
const password = ref(savedPwd)
const rememberCredentials = ref(remember)
const syncingLatest = ref(false)
const loading = ref(false)
const error = ref('')
const switching = ref(false)
const detail = ref<Course | null>(null)
const viewer = ref<'calendar' | 'time' | null>(null)
const showToolbox = ref(false)

// 个性化背景设置
const bgConfig = ref({
  url: localStorage.getItem('bjfu-bg-url') || '',
  opacity: (Number(localStorage.getItem('bjfu-bg-opacity')) || 20) / 100,
  blur: Number(localStorage.getItem('bjfu-bg-blur')) || 0,
})

function onUpdateBg(bg: { url: string; opacity: number; blur: number }) {
  bgConfig.value = bg
}

function handleScheduleLogout() {
  localStorage.removeItem('bjfu-remember-credentials')
  localStorage.removeItem('bjfu-student-pwd')
  if (studentId.value) {
    localStorage.removeItem(`bjfu-schedule-cache-${studentId.value.trim()}`)
  }
  localStorage.removeItem('bjfu-schedule-cache')
  schedule.value = null
  password.value = ''
  showForm.value = true
  showToolbox.value = false
  router.replace({ query: {} }).catch(() => {})
}

function syncUrlWithUser(sid: string) {
  if (sid && route.query.user !== sid) {
    router.replace({
      query: { ...route.query, user: sid }
    }).catch(() => {})
  }
}

// 课表初始数据：若已保存账号密码，优先从本地持久化缓存同步读取
const schedule = ref<ScheduleData | null>(hasSavedCredentials ? loadCachedSchedule() : null)

// 核心流转控制：
// 1. 勾选了保存密码的用户：首屏直接呈现课表，绝不展示登录页，直接进入课表并在后台静默拉取
// 2. 新用户或未勾选保存密码的用户：展示登录表单
const showForm = ref(!hasSavedCredentials)

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

const showWeekPicker = ref(false)
const edgePullDirection = ref<'prev' | 'next' | null>(null)
const edgePullDistance = ref(0)
const PULL_THRESHOLD = 40

let touchStartX = 0
let touchStartY = 0
let edgePullStartX = 0
let isTouching = false

function onTouchStart(e: TouchEvent) {
  if (!gridContainer.value || e.touches.length !== 1) return
  isTouching = true
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
  edgePullStartX = e.touches[0].clientX
  edgePullDirection.value = null
  edgePullDistance.value = 0
}

function onTouchMove(e: TouchEvent) {
  if (!isTouching || !gridContainer.value || e.touches.length !== 1) return
  const currentX = e.touches[0].clientX
  const currentY = e.touches[0].clientY
  const dx = currentX - touchStartX
  const dy = currentY - touchStartY

  // 必须主要是水平滑动手势
  if (Math.abs(dx) <= Math.abs(dy) || Math.abs(dx) < 10) {
    if (edgePullDirection.value) {
      edgePullDirection.value = null
      edgePullDistance.value = 0
    }
    return
  }

  const container = gridContainer.value
  const currentScrollLeft = container.scrollLeft
  const maxLeft = Math.max(0, container.scrollWidth - container.clientWidth)
  const isAtLeftEdge = currentScrollLeft <= 2
  const isAtRightEdge = currentScrollLeft >= maxLeft - 2

  // 处于最左端向右拖动 -> 切换到上一周
  if (isAtLeftEdge && dx > 0) {
    if (!edgePullDirection.value) {
      edgePullStartX = currentX
    }
    const pullDx = Math.max(0, currentX - edgePullStartX)
    edgePullDirection.value = 'prev'
    edgePullDistance.value = Math.min(80, pullDx * 0.45)
  }
  // 处于最右端向左拖动 -> 切换到下一周
  else if (isAtRightEdge && dx < 0) {
    if (!edgePullDirection.value) {
      edgePullStartX = currentX
    }
    const pullDx = Math.max(0, edgePullStartX - currentX)
    edgePullDirection.value = 'next'
    edgePullDistance.value = Math.min(80, pullDx * 0.45)
  } else {
    edgePullDirection.value = null
    edgePullDistance.value = 0
    edgePullStartX = currentX
  }
}

function onTouchEnd() {
  if (!isTouching) return
  isTouching = false

  const dir = edgePullDirection.value
  const dist = edgePullDistance.value

  edgePullDirection.value = null
  edgePullDistance.value = 0

  if (dist >= PULL_THRESHOLD) {
    if (dir === 'prev' && currentWeek.value > 1) {
      switchToAdjacentWeek(currentWeek.value - 1, 'end')
    } else if (dir === 'next' && currentWeek.value < TOTAL_WEEKS) {
      switchToAdjacentWeek(currentWeek.value + 1, 'start')
    }
  }
}

function onTouchCancel() {
  isTouching = false
  edgePullDirection.value = null
  edgePullDistance.value = 0
}

let wheelAccumX = 0
let wheelDebounceTimer: ReturnType<typeof setTimeout> | null = null

function onGridWheel(e: WheelEvent) {
  if (!gridContainer.value) return
  if (Math.abs(e.deltaX) < 10 || Math.abs(e.deltaX) <= Math.abs(e.deltaY)) return

  const container = gridContainer.value
  const maxLeft = Math.max(0, container.scrollWidth - container.clientWidth)
  const isAtLeft = container.scrollLeft <= 2
  const isAtRight = container.scrollLeft >= maxLeft - 2

  if (isAtLeft && e.deltaX < -25) {
    wheelAccumX += Math.abs(e.deltaX)
    if (wheelAccumX > 100) {
      wheelAccumX = 0
      if (currentWeek.value > 1) {
        switchToAdjacentWeek(currentWeek.value - 1, 'end')
      }
    }
  } else if (isAtRight && e.deltaX > 25) {
    wheelAccumX += Math.abs(e.deltaX)
    if (wheelAccumX > 100) {
      wheelAccumX = 0
      if (currentWeek.value < TOTAL_WEEKS) {
        switchToAdjacentWeek(currentWeek.value + 1, 'start')
      }
    }
  } else {
    wheelAccumX = 0
  }

  if (wheelDebounceTimer) clearTimeout(wheelDebounceTimer)
  wheelDebounceTimer = setTimeout(() => {
    wheelAccumX = 0
  }, 250)
}

function switchToAdjacentWeek(targetWeek: number, position: 'start' | 'end') {
  if (targetWeek < 1 || targetWeek > TOTAL_WEEKS || targetWeek === currentWeek.value) return
  switching.value = true
  currentWeek.value = targetWeek
  setTimeout(() => {
    switching.value = false
    nextTick(() => {
      if (gridContainer.value) {
        if (position === 'start') {
          gridContainer.value.scrollLeft = 0
        } else {
          gridContainer.value.scrollLeft = gridContainer.value.scrollWidth - gridContainer.value.clientWidth
        }
      }
    })
  }, 100)
}

function selectWeek(w: number) {
  if (w < 1 || w > TOTAL_WEEKS) return
  showWeekPicker.value = false
  if (w === currentWeek.value) return
  switching.value = true
  currentWeek.value = w
  setTimeout(() => {
    switching.value = false
    nextTick(() => {
      if (w === systemWeek()) {
        scrollToToday()
      } else if (gridContainer.value) {
        gridContainer.value.scrollLeft = 0
      }
    })
  }, 100)
}

function changeWeek(delta: number) {
  const next = Math.min(TOTAL_WEEKS, Math.max(1, currentWeek.value + delta))
  if (next === currentWeek.value) return
  switching.value = true
  currentWeek.value = next
  setTimeout(() => {
    switching.value = false
    nextTick(() => {
      if (gridContainer.value) {
        if (delta > 0) {
          gridContainer.value.scrollLeft = 0
        } else {
          gridContainer.value.scrollLeft = gridContainer.value.scrollWidth - gridContainer.value.clientWidth
        }
      }
    })
  }, 100)
}

onMounted(async () => {
  document.body.classList.add('schedule-page')

  // 1. 若 URL 中指定了 user 或 student_id（形如 ?user=250100109 或 ?student_id=xxx）
  const qSid = (route.query.user || route.query.student_id || route.query.sid) as string | undefined
  const qUid = (route.query.user_id || route.query.uid) as string | undefined

  if (qSid && qSid.trim()) {
    const cleanSid = qSid.trim()
    studentId.value = cleanSid

    // 优先从本学号本地离线缓存读取
    const cachedForUser = localStorage.getItem(`bjfu-schedule-cache-${cleanSid}`)
    if (cachedForUser) {
      try {
        const parsed = JSON.parse(cachedForUser)
        if (parsed && Array.isArray(parsed.courses)) {
          schedule.value = parsed
          showForm.value = false
          scrollToToday()
          syncUrlWithUser(cleanSid)
          return
        }
      } catch {}
    }

    try {
      schedule.value = await api.get<ScheduleData>(`/api/schedule/query?student_id=${encodeURIComponent(cleanSid)}`)
      showForm.value = false
      scrollToToday()
      syncUrlWithUser(cleanSid)
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

  // 2. 勾选了保存账号密码的用户：直接后台静默拉取最新课表，并在 URL 同步 ?user=学号
  if (hasSavedCredentials) {
    if (schedule.value) {
      scrollToToday()
      syncUrlWithUser(savedSid.trim())
    }

    // 后台静默拉取最新课表覆盖本地
    syncingLatest.value = true
    try {
      const fresh = await api.post<ScheduleData>('/api/schedule/get', {
        student_id: savedSid.trim(),
        password: savedPwd,
        force: true,
      })
      if (fresh && fresh.courses) {
        schedule.value = fresh
        try {
          localStorage.setItem(`bjfu-schedule-cache-${savedSid.trim()}`, JSON.stringify(fresh))
          localStorage.setItem('bjfu-schedule-cache', JSON.stringify(fresh))
        } catch {}
        showForm.value = false
        scrollToToday()
        syncUrlWithUser(savedSid.trim())
      }
    } catch (err: any) {
      console.warn('Auto fetch latest schedule failed:', err)
      // 若拉取失败但已有缓存课表，保持展示当前课表，绝不弹回登录页面
      if (!schedule.value) {
        error.value = err.message || '自动拉取最新课表失败，请检查账号密码'
        showForm.value = true
      }
    } finally {
      syncingLatest.value = false
    }
    return
  }

  // 3. 新用户或未勾选保存账号密码的用户：直接展示登录表单，严禁自动加载其他课表
  showForm.value = true

  window.addEventListener('keydown', onKeydown)
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (showWeekPicker.value) showWeekPicker.value = false
    else if (viewer.value) viewer.value = null
    else if (detail.value) detail.value = null
  }
}

onUnmounted(() => {
  document.body.classList.remove('schedule-page')
  window.removeEventListener('keydown', onKeydown)
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

async function fetchSchedule(force = true) {
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
    // 根据是否勾选“保存账号密码”进行持久化存储或清理
    if (rememberCredentials.value) {
      localStorage.setItem('bjfu-remember-credentials', 'true')
      localStorage.setItem('bjfu-student-id', studentId.value.trim())
      localStorage.setItem('bjfu-student-pwd', password.value)
      try {
        localStorage.setItem(`bjfu-schedule-cache-${studentId.value.trim()}`, JSON.stringify(schedule.value))
        localStorage.setItem('bjfu-schedule-cache', JSON.stringify(schedule.value))
      } catch {}
    } else {
      localStorage.removeItem('bjfu-remember-credentials')
      localStorage.removeItem('bjfu-student-pwd')
      localStorage.setItem('bjfu-student-id', studentId.value.trim())
      // 未勾选保存密码时清除本地课表缓存，下次打开必须重新输入密码登录
      localStorage.removeItem(`bjfu-schedule-cache-${studentId.value.trim()}`)
      localStorage.removeItem('bjfu-schedule-cache')
    }
    showForm.value = false
    scrollToToday()
    syncUrlWithUser(studentId.value.trim())
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
  <div class="relative min-h-[calc(100vh-8rem)] py-4 sm:py-12">
    <!-- Custom Background Wallpaper Layer -->
    <div
      v-if="bgConfig.url"
      class="fixed inset-0 pointer-events-none z-0 bg-cover bg-center transition-all duration-300"
      :style="{
        backgroundImage: `url(${bgConfig.url})`,
        opacity: bgConfig.opacity,
        filter: `blur(${bgConfig.blur}px)`,
      }"
    />

    <!-- Top Header -->
    <header class="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-4 border-b border-[#E5E5E5]/70 pb-3 sm:pb-6 mb-3 sm:mb-8">
      <div>
        <div class="flex items-center gap-2 font-mono text-[11px] sm:text-xs text-neutral-400 uppercase tracking-widest mb-0.5 sm:mb-1.5">
          <BrandWordmark size="xs" :animated-dot="false" />
          <span class="text-neutral-300">·</span>
          <span>北林课表</span>
          <span class="text-neutral-300">·</span>
          <span class="text-neutral-400 font-mono text-[10px] lowercase bg-neutral-100 px-1.5 py-0.5 rounded">v1.3.0</span>
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
            title="上一周"
            @click="changeWeek(-1)"
          >
            ←
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-2 sm:px-2.5 py-0.5 sm:py-1 font-medium text-neutral-900 hover:bg-neutral-50 hover:text-neutral-950 border-x border-[#E5E5E5]/80 text-[11px] sm:text-xs cursor-pointer transition-colors"
            title="点击快速跳转周次"
            @click="showWeekPicker = true"
          >
            <span>第 {{ currentWeek }} 周</span>
            <svg class="w-3 h-3 text-neutral-400" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            class="px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-950 disabled:opacity-30 cursor-pointer"
            :disabled="currentWeek >= TOTAL_WEEKS"
            title="下一周"
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
            今天
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] bg-white px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 hover:text-neutral-900 hover:border-neutral-400 disabled:opacity-50 transition-colors cursor-pointer text-[11px] sm:text-xs"
            title="刷新最新课表"
            :disabled="loading"
            @click="refresh"
          >
            刷新
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] bg-white px-2.5 sm:px-3 py-0.5 sm:py-1 text-neutral-700 hover:text-neutral-950 hover:border-neutral-400 transition-colors cursor-pointer text-[11px] sm:text-xs font-medium flex items-center gap-1"
            title="工具箱与更多功能"
            @click="showToolbox = true"
          >
            <span>更多</span>
            <svg class="w-3 h-3 text-neutral-400" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
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
        输入教务学号与密码同步个人课表。勾选保存账号密码将在本设备明文存储，并在每次打开页面时自动重新拉取最新课表覆盖原版本。
      </p>
      <form class="space-y-4 font-mono text-xs" @submit.prevent="fetchSchedule(true)">
        <div>
          <label class="block uppercase tracking-widest text-neutral-400 text-[10px] mb-1">教务学号</label>
          <input
            v-model="studentId"
            type="text"
            placeholder="请输入学号"
            class="w-full rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-neutral-900 focus:border-neutral-900 focus:bg-white focus:outline-none"
          />
        </div>
        <div>
          <label class="block uppercase tracking-widest text-neutral-400 text-[10px] mb-1">教务系统密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="请输入教务密码"
            class="w-full rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-neutral-900 focus:border-neutral-900 focus:bg-white focus:outline-none"
          />
        </div>

        <!-- 保存账号密码选项 -->
        <div class="flex items-center justify-between text-[11px] text-neutral-600 select-none py-0.5">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="rememberCredentials"
              type="checkbox"
              class="h-3.5 w-3.5 rounded border-[#E5E5E5] text-neutral-900 accent-neutral-900 focus:ring-0 cursor-pointer"
            />
            <span class="font-sans">保存账号密码（每次打开网页自动拉取最新课表）</span>
          </label>
        </div>

        <p v-if="error" class="text-red-600 text-xs">{{ error }}</p>
        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded bg-neutral-900 py-2.5 text-white hover:bg-neutral-800 disabled:opacity-50 transition-colors cursor-pointer"
        >
          {{ loading ? '正在同步...' : '同步课表' }}
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
        <div class="flex items-center gap-3">
          <div v-if="syncingLatest" class="flex items-center gap-1.5 text-amber-600 text-[10px] sm:text-[11px] animate-pulse font-sans">
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping" />
            正在拉取最新课表...
          </div>
          <div v-if="termTip" class="text-neutral-400 text-[10px] sm:text-[11px]">
            {{ termTip }}
          </div>
        </div>
      </div>

      <!-- Timetable Grid with Edge Swipe Support -->
      <div class="relative">
        <!-- Floating edge swipe week switcher indicator -->
        <transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="opacity-0 -translate-y-2 scale-95"
          enter-to-class="opacity-100 translate-y-0 scale-100"
          leave-active-class="transition duration-150 ease-in"
          leave-from-class="opacity-100 translate-y-0 scale-100"
          leave-to-class="opacity-0 -translate-y-2 scale-95"
        >
          <div
            v-if="edgePullDirection"
            class="absolute left-1/2 -translate-x-1/2 top-3 z-40 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-mono shadow-lg border backdrop-blur-md pointer-events-none transition-all duration-150 select-none"
            :class="[
              edgePullDistance >= PULL_THRESHOLD
                ? 'bg-neutral-900 text-white border-neutral-800 scale-105 shadow-neutral-900/20'
                : 'bg-white/95 text-neutral-700 border-neutral-200'
            ]"
          >
            <template v-if="edgePullDirection === 'prev'">
              <span v-if="currentWeek <= 1">已是第 1 周</span>
              <template v-else>
                <span>←</span>
                <span>{{ edgePullDistance >= PULL_THRESHOLD ? `松开切换至第 ${currentWeek - 1} 周` : `继续向右滑切换至第 ${currentWeek - 1} 周` }}</span>
              </template>
            </template>
            <template v-else-if="edgePullDirection === 'next'">
              <span v-if="currentWeek >= TOTAL_WEEKS">已是最后一周</span>
              <template v-else>
                <span>{{ edgePullDistance >= PULL_THRESHOLD ? `松开切换至第 ${currentWeek + 1} 周` : `继续向左滑切换至第 ${currentWeek + 1} 周` }}</span>
                <span>→</span>
              </template>
            </template>
          </div>
        </transition>

        <div
          ref="gridContainer"
          class="overflow-x-auto rounded-lg border border-[#E5E5E5] bg-white p-0.5 sm:p-2 shadow-[0_1px_3px_rgba(0,0,0,0.02)] scroll-smooth"
          @touchstart.passive="onTouchStart"
          @touchmove.passive="onTouchMove"
          @touchend="onTouchEnd"
          @touchcancel="onTouchCancel"
          @wheel="onGridWheel"
        >
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
      </div>

    </template>

    <!-- Loading placeholder for first-time auto sync without cached data -->
    <div v-else-if="syncingLatest || loading" class="max-w-md mx-auto text-center py-20 font-mono text-xs text-neutral-400">
      <div class="inline-block h-5 w-5 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-900 mb-3" />
      <p class="font-sans text-neutral-600 text-sm">正在同步最新课表...</p>
    </div>

    <!-- Course Detail Modal -->
    <div
      v-if="detail"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-xs p-4"
      @click.self="detail = null"
    >
      <div class="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl border border-[#E5E5E5]">
        <div class="flex items-center justify-between mb-4 border-b border-neutral-100 pb-3">
          <h3 class="text-sm font-medium text-neutral-900 font-sans">课程详情</h3>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer p-1" title="关闭" @click="detail = null">✕</button>
        </div>
        <div class="space-y-3 font-mono text-xs">
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">课程名称</span>
            <span class="text-neutral-900 font-sans font-medium text-sm">{{ detail.name }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">授课教师</span>
            <span class="text-neutral-700 font-sans">{{ detail.teacher || '—' }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">上课地点</span>
            <span class="text-neutral-700">{{ detail.room || '—' }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">时间节次</span>
            <span class="text-neutral-700">{{ weekdayName(detail.day) }} · {{ detail.period }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">上课周次</span>
            <span class="text-neutral-700">{{ weekCount(detail.weeks) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Week Picker Modal (周数快速切换弹窗) -->
    <div
      v-if="showWeekPicker"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      @click.self="showWeekPicker = false"
    >
      <div class="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl border border-[#E5E5E5] animate-in fade-in zoom-in-95 duration-150">
        <div class="flex items-center justify-between pb-3 border-b border-neutral-100 mb-4">
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-medium text-neutral-900 font-sans">快速跳转周次</h3>
            <span class="text-[11px] font-mono text-neutral-400">(共 {{ TOTAL_WEEKS }} 周)</span>
          </div>
          <button
            class="text-neutral-400 hover:text-neutral-900 cursor-pointer p-1 rounded hover:bg-neutral-100 transition-colors"
            title="关闭"
            @click="showWeekPicker = false"
          >
            ✕
          </button>
        </div>

        <!-- Weeks Grid -->
        <div class="grid grid-cols-4 sm:grid-cols-5 gap-2 font-mono text-xs max-h-[60vh] overflow-y-auto p-0.5">
          <button
            v-for="w in TOTAL_WEEKS"
            :key="w"
            type="button"
            class="flex flex-col items-center justify-center p-2 rounded-lg border transition-all cursor-pointer relative text-center"
            :class="[
              w === currentWeek
                ? 'bg-neutral-900 border-neutral-900 text-white shadow-sm'
                : 'bg-neutral-50/70 border-neutral-200/80 text-neutral-800 hover:bg-neutral-100 hover:border-neutral-300',
              w === systemWeek() && w !== currentWeek ? 'border-amber-400 bg-amber-50/40 text-amber-950 font-medium' : ''
            ]"
            @click="selectWeek(w)"
          >
            <span class="font-medium text-xs leading-tight">第 {{ w }} 周</span>
            <span
              class="text-[9px] mt-0.5 leading-tight scale-95"
              :class="w === currentWeek ? 'text-neutral-300' : 'text-neutral-400'"
            >
              {{ getDateLabel(w, 0) }}
            </span>
            <span
              v-if="w === systemWeek()"
              class="absolute -top-1.5 -right-1 px-1 py-0.2 rounded text-[8px] font-sans font-medium"
              :class="w === currentWeek ? 'bg-amber-400 text-neutral-900' : 'bg-amber-500 text-white'"
            >
              本周
            </span>
          </button>
        </div>

        <!-- Quick actions at footer -->
        <div class="mt-4 pt-3 border-t border-neutral-100 flex items-center justify-between font-mono text-xs">
          <button
            type="button"
            class="text-neutral-600 hover:text-neutral-950 cursor-pointer text-[11px] underline underline-offset-2 flex items-center gap-1"
            @click="selectWeek(systemWeek())"
          >
            <span>跳转到本周 (第 {{ systemWeek() }} 周)</span>
          </button>
          <button
            type="button"
            class="px-3 py-1 rounded bg-neutral-100 hover:bg-neutral-200 text-neutral-700 cursor-pointer text-[11px]"
            @click="showWeekPicker = false"
          >
            关闭
          </button>
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
              校历大图
            </button>
            <button
              class="px-3 py-1 rounded transition-colors cursor-pointer"
              :class="viewer === 'time' ? 'bg-neutral-900 text-white' : 'border border-[#E5E5E5] text-neutral-600 hover:text-neutral-900'"
              @click="viewer = 'time'"
            >
              作息时间表
            </button>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer p-1" title="关闭" @click="closeImgViewer">✕</button>
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

    <!-- Toolbox Modal (更多功能工具箱) -->
    <ToolboxModal
      :show="showToolbox"
      :schedule="schedule"
      :student-id="studentId"
      @close="showToolbox = false"
      @open-calendar="showToolbox = false; viewer = 'calendar'"
      @logout="handleScheduleLogout"
      @update-bg="onUpdateBg"
    />

  </div>
</template>
