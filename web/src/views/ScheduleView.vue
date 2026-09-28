<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import BrandWordmark from '@/components/BrandWordmark.vue'
import ToolboxModal from '@/components/schedule/ToolboxModal.vue'
import { processImageFile } from '@/utils/image'

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
  id?: string
  isCustom?: boolean
  color?: string
  note?: string
}
interface CustomScheduleEvent extends Course {
  id: string
  isCustom: true
}
interface ScheduleData {
  semester: string
  updated_time: string
  courses: Course[]
}

const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const showWeekend = ref(localStorage.getItem('bjfu-show-weekend') !== 'false')
const colorfulCards = ref(localStorage.getItem('bjfu-colorful-cards') !== 'false')
const showCourseTime = ref(localStorage.getItem('bjfu-show-course-time') === 'true')
const slotTimeFormat = ref<'start' | 'range'>(
  (localStorage.getItem('bjfu-slot-time-format') || 'start') as 'start' | 'range'
)

function formatSlotMinute(min: number): string {
  const h = String(Math.floor(min / 60)).padStart(2, '0')
  const m = String(min % 60).padStart(2, '0')
  return `${h}:${m}`
}

const displayedWeekdays = computed(() => {
  return showWeekend.value ? weekdays : weekdays.slice(0, 5)
})
const daysCount = computed(() => (showWeekend.value ? 7 : 5))

const TERM_START = '2026-09-07'
const TERM_END = '2027-01-15'
const TERM_LABEL = '2026年秋季学期'

const periodSlots = [
  { start: 1, end: 2, label: '1-2', from: 480, to: 575 },
  { start: 3, end: 4, label: '3-4', from: 590, to: 685 },
  { start: 5, end: 5, label: '5', from: 690, to: 735 },
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

function isSameCourse(a: Course, b: Course): boolean {
  if (a.day !== b.day) return false
  if (a.name.trim() !== b.name.trim()) return false
  if ((a.teacher || '').trim() !== (b.teacher || '').trim()) return false
  if ((a.room || '').trim() !== (b.room || '').trim()) return false
  if (!!a.isCustom !== !!b.isCustom) return false

  const wA = (a.weeks || '').trim()
  const wB = (b.weeks || '').trim()
  if (wA !== wB) {
    const listA = parseWeeks(wA)
    const listB = parseWeeks(wB)
    if (!listA || !listB || listA.join(',') !== listB.join(',')) return false
  }
  return true
}

function mergeAdjacentCourses(courses: Course[]): Course[] {
  if (!courses || courses.length <= 1) return courses ? [...courses] : []

  // 按星期分组
  const byDay: Record<number, Course[]> = {}
  for (const c of courses) {
    if (!byDay[c.day]) byDay[c.day] = []
    byDay[c.day].push({ ...c })
  }

  const result: Course[] = []
  for (const dayStr of Object.keys(byDay)) {
    const dayList = byDay[Number(dayStr)]
    dayList.sort((a, b) => a.start - b.start)

    let merged = true
    while (merged) {
      merged = false
      for (let i = 0; i < dayList.length - 1; i++) {
        const cur = dayList[i]
        const nxt = dayList[i + 1]

        // 连续节次且非跨大休息段（上午5节与下午6节之间午休，下午9节与晚间10节之间晚饭休）
        const canMerge =
          isSameCourse(cur, nxt) &&
          cur.end + 1 === nxt.start &&
          cur.end !== 5 &&
          cur.end !== 9

        if (canMerge) {
          cur.end = nxt.end
          cur.period = cur.start === cur.end ? `第${cur.start}节` : `第${cur.start}-${cur.end}节`
          dayList.splice(i + 1, 1)
          merged = true
          break
        }
      }
    }
    result.push(...dayList)
  }

  return result
}

function courseCoversSlot(c: Course, slotBlock: number): boolean {
  const startB = blockOf(c.start)
  const endB = blockOf(c.end)
  return slotBlock >= startB && slotBlock <= endB
}

function coursePeriodLabel(c: Course): string {
  if (c.period) return c.period.replace(/^第/, '').replace(/节$/, '') + '节'
  return c.start === c.end ? `${c.start}节` : `${c.start}-${c.end}节`
}

function courseTimeRange(c: Course): string {
  const startB = periodSlots[blockOf(c.start) - 1]
  const endB = periodSlots[blockOf(c.end) - 1]
  if (!startB || !endB) return ''
  const startH = String(Math.floor(startB.from / 60)).padStart(2, '0')
  const startM = String(startB.from % 60).padStart(2, '0')
  const endH = String(Math.floor(endB.to / 60)).padStart(2, '0')
  const endM = String(endB.to % 60).padStart(2, '0')
  return `${startH}:${startM}-${endH}:${endM}`
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
const storedRemember = localStorage.getItem('bjfu-remember-credentials')
// 默认记住凭据（除非用户明确取消），确保 App 移动端免重复输入
const remember = storedRemember !== null ? storedRemember === 'true' : true
const hasSavedCredentials = remember && !!savedSid.trim() && !!savedPwd

// 尝试从本地持久化缓存立即读取已有课表（实现 0ms 秒开呈现）
function loadCachedSchedule(): ScheduleData | null {
  if (!savedSid.trim()) return null
  try {
    const raw = localStorage.getItem(`bjfu-schedule-cache-${savedSid.trim()}`) || localStorage.getItem('bjfu-schedule-cache')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed && Array.isArray(parsed.courses)) {
        parsed.courses = mergeAdjacentCourses(parsed.courses)
        return parsed
      }
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

const toolboxInitialTool = ref<string>('none')
const isPageDraggingImage = ref(false)
let dragCounter = 0

function onUpdateBg(bg: { url: string; opacity: number; blur: number }) {
  bgConfig.value = {
    url: bg.url,
    opacity: bg.opacity > 1 ? bg.opacity / 100 : bg.opacity,
    blur: bg.blur,
  }
}

function onWindowDragEnter(e: DragEvent) {
  if (e.dataTransfer?.types.includes('Files')) {
    e.preventDefault()
    dragCounter++
    isPageDraggingImage.value = true
  }
}

function onWindowDragOver(e: DragEvent) {
  if (e.dataTransfer?.types.includes('Files')) {
    e.preventDefault()
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy'
    }
    isPageDraggingImage.value = true
  }
}

function onWindowDragLeave(e: DragEvent) {
  e.preventDefault()
  dragCounter--
  if (dragCounter <= 0) {
    dragCounter = 0
    isPageDraggingImage.value = false
  }
}

async function onWindowDrop(e: DragEvent) {
  e.preventDefault()
  dragCounter = 0
  isPageDraggingImage.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) {
    try {
      const dataUrl = await processImageFile(file)
      localStorage.setItem('bjfu-bg-url', dataUrl)
      bgConfig.value.url = dataUrl
      // 唤起背景设置弹窗以便用户直接微调不透明度和模糊度
      toolboxInitialTool.value = 'background'
      showToolbox.value = true
    } catch (err: any) {
      if (typeof window !== 'undefined') {
        window.alert(err.message || '图片导入失败')
      }
    }
  }
}

function onUpdateAppearance(pref: {
  showWeekend: boolean
  themeMode: string
  colorfulCards: boolean
  showCourseTime: boolean
  slotTimeFormat?: 'start' | 'range'
}) {
  showWeekend.value = pref.showWeekend
  colorfulCards.value = pref.colorfulCards
  showCourseTime.value = pref.showCourseTime
  if (pref.slotTimeFormat) {
    slotTimeFormat.value = pref.slotTimeFormat
  }
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

const isViewingShared = ref(false)
const sharedCode = ref('')
const sharedOwnerName = ref('')
const sharedSaveSuccess = ref(false)

function saveFriendFromShared() {
  if (!sharedCode.value) return
  try {
    const list = JSON.parse(localStorage.getItem('bjfu-shared-friends') || '[]')
    if (!list.some((f: any) => f.code === sharedCode.value)) {
      list.push({
        name: sharedOwnerName.value || '同学',
        code: sharedCode.value,
        semester: schedule.value?.semester || '',
        coursesCount: schedule.value?.courses?.length || 0,
      })
      localStorage.setItem('bjfu-shared-friends', JSON.stringify(list))
    }
    sharedSaveSuccess.value = true
    setTimeout(() => {
      sharedSaveSuccess.value = false
    }, 2500)
  } catch {}
}

function backToMySchedule() {
  isViewingShared.value = false
  sharedCode.value = ''
  sharedOwnerName.value = ''
  router.replace({ query: {} }).catch(() => {})
  const mySched = loadCachedSchedule()
  if (mySched) {
    schedule.value = mySched
    showForm.value = false
    if (savedSid.trim()) {
      syncUrlWithUser(savedSid.trim())
    }
  } else {
    showForm.value = true
    schedule.value = null
  }
}

function syncUrlWithUser(sid: string) {
  if (isViewingShared.value) return
  if (sid && route.query.user !== sid) {
    router.replace({
      query: { ...route.query, user: sid }
    }).catch(() => {})
  }
}

// 课表初始数据：优先从本地持久化缓存立即读取，避免白屏与闪烁
const initialSchedule = loadCachedSchedule()
const schedule = ref<ScheduleData | null>(initialSchedule)

// 核心流转控制：若本地已有缓存数据（或保存了凭据），首屏直接呈现课表，绝不闪现登录页
const showForm = ref(!initialSchedule && !hasSavedCredentials)

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

// APP 端全屏沉浸与环境识别
const isApp = computed(() => {
  if (typeof window === 'undefined') return false
  return route.query.app === '1' || navigator.userAgent.includes('SnhgnScheduleAndroid')
})

const showWeekPicker = ref(false)
const edgePullDirection = ref<'prev' | 'next' | null>(null)
const edgePullDistance = ref(0)
const PULL_THRESHOLD = 40
const wasSwiping = ref(false)
let swipingResetTimer: ReturnType<typeof setTimeout> | null = null

function openDetail(c: Course) {
  if (wasSwiping.value) return
  detail.value = c
}

function handleCellClick(day: number, slotBlock: number) {
  if (wasSwiping.value) return
  openAddCustomEventModal(day, slotBlock)
}

let touchStartX = 0
let touchStartY = 0
let edgePullStartX = 0
let isTouching = false

function onTouchStart(e: TouchEvent) {
  if ((!gridContainer.value && !isApp.value) || e.touches.length !== 1) return
  isTouching = true
  wasSwiping.value = false
  if (swipingResetTimer) {
    clearTimeout(swipingResetTimer)
    swipingResetTimer = null
  }
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
  edgePullStartX = e.touches[0].clientX
  edgePullDirection.value = null
  edgePullDistance.value = 0
}

function onTouchMove(e: TouchEvent) {
  if (!isTouching || (!gridContainer.value && !isApp.value) || e.touches.length !== 1) return
  const currentX = e.touches[0].clientX
  const currentY = e.touches[0].clientY
  const dx = currentX - touchStartX
  const dy = currentY - touchStartY

  // 必须主要是水平滑动手势
  if (Math.abs(dx) <= Math.abs(dy) || Math.abs(dx) < 8) {
    if (edgePullDirection.value) {
      edgePullDirection.value = null
      edgePullDistance.value = 0
    }
    return
  }

  // 滑动位移超过 10px 时锁定为正在滑动，抬手时抑制卡片点击事件
  if (Math.abs(dx) > 10) {
    wasSwiping.value = true
  }

  // App 模式：由于页面全屏且无横向滚动条，任意位置左右滑都可以直接触发切周
  if (isApp.value) {
    if (dx > 0) {
      // 向右滑 -> 上一周
      edgePullDirection.value = 'prev'
      edgePullDistance.value = Math.min(80, dx * 0.8)
    } else {
      // 向左滑 -> 下一周
      edgePullDirection.value = 'next'
      edgePullDistance.value = Math.min(80, Math.abs(dx) * 0.8)
    }
    return
  }

  const container = gridContainer.value
  if (!container) return
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

  if (wasSwiping.value) {
    if (swipingResetTimer) clearTimeout(swipingResetTimer)
    swipingResetTimer = setTimeout(() => {
      wasSwiping.value = false
    }, 200)
  }
}

function onTouchCancel() {
  isTouching = false
  edgePullDirection.value = null
  edgePullDistance.value = 0
  if (wasSwiping.value) {
    if (swipingResetTimer) clearTimeout(swipingResetTimer)
    swipingResetTimer = setTimeout(() => {
      wasSwiping.value = false
    }, 200)
  }
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

  // 0. 优先检测是否传入了 4 位共享课表邀请码 (?code=XXXX 或 ?share=XXXX)
  const qCode = (route.query.code || route.query.share) as string | undefined
  if (qCode && qCode.trim()) {
    const code = qCode.trim().toUpperCase()
    try {
      const shared = await api.get<any>(`/api/schedule/share/${encodeURIComponent(code)}`)
      if (shared && Array.isArray(shared.courses)) {
        schedule.value = shared
        isViewingShared.value = true
        sharedCode.value = code
        sharedOwnerName.value = shared.owner_name || '同学'
        showForm.value = false
        scrollToToday()
        return
      }
    } catch (err: any) {
      console.warn('Failed to load shared schedule via code:', err)
      error.value = '该 4 位邀请码不存在或已失效'
    }
  }

  // 1. 若 URL 中指定了 user 或本地有保存的学号
  const qSid = (route.query.user || route.query.student_id || route.query.sid) as string | undefined
  const qUid = (route.query.user_id || route.query.uid) as string | undefined
  const effectiveSid = qSid?.trim() || savedSid.trim()

  if (effectiveSid) {
    studentId.value = effectiveSid

    // 优先从该学号的本地持久化离线缓存读取
    const cachedForUser =
      localStorage.getItem(`bjfu-schedule-cache-${effectiveSid}`) ||
      localStorage.getItem('bjfu-schedule-cache')
    if (cachedForUser) {
      try {
        const parsed = JSON.parse(cachedForUser)
        if (parsed && Array.isArray(parsed.courses)) {
          schedule.value = parsed
          showForm.value = false
          scrollToToday()
          syncUrlWithUser(effectiveSid)
          if (!hasSavedCredentials) return
        }
      } catch {}
    }

    // 若本地暂无离线缓存且未保存密码，尝试直接从服务端无密码公开缓存查询
    if (!schedule.value && !hasSavedCredentials) {
      try {
        schedule.value = await api.get<ScheduleData>(
          `/api/schedule/query?student_id=${encodeURIComponent(effectiveSid)}`
        )
        showForm.value = false
        scrollToToday()
        syncUrlWithUser(effectiveSid)
        return
      } catch {
        // 未查询到缓存时向下流转
      }
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
      showForm.value = false
      scrollToToday()
      syncUrlWithUser(savedSid.trim())
    }

    // 后台静默校验与更新课表（优先使用服务端新鲜缓存，绝不每次打开都重爬教务）
    syncingLatest.value = !schedule.value
    try {
      const fresh = await api.post<ScheduleData>('/api/schedule/get', {
        student_id: savedSid.trim(),
        password: savedPwd,
        force: false,
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

  // 3. 既无有效学号也无课表缓存的新用户：展示登录表单
  if (!schedule.value) {
    showForm.value = true
  }

  window.addEventListener('keydown', onKeydown)
  window.addEventListener('dragenter', onWindowDragEnter)
  window.addEventListener('dragover', onWindowDragOver)
  window.addEventListener('dragleave', onWindowDragLeave)
  window.addEventListener('drop', onWindowDrop)
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (showCustomEventModal.value) showCustomEventModal.value = false
    else if (showWeekPicker.value) showWeekPicker.value = false
    else if (viewer.value) viewer.value = null
    else if (detail.value) detail.value = null
  }
}

onUnmounted(() => {
  document.body.classList.remove('schedule-page')
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('dragenter', onWindowDragEnter)
  window.removeEventListener('dragover', onWindowDragOver)
  window.removeEventListener('dragleave', onWindowDragLeave)
  window.removeEventListener('drop', onWindowDrop)
})

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

// ================= 自定义时间安排系统 (空闲时段添加日程) =================
function getCustomEventsStorageKey(): string {
  const sid = studentId.value?.trim()
  return sid ? `bjfu-custom-events-${sid}` : 'bjfu-custom-events'
}

function loadCustomEvents(): CustomScheduleEvent[] {
  if (typeof localStorage === 'undefined') return []
  const key = getCustomEventsStorageKey()
  try {
    let raw = localStorage.getItem(key)
    if (!raw && key !== 'bjfu-custom-events') {
      raw = localStorage.getItem('bjfu-custom-events')
      if (raw) {
        localStorage.setItem(key, raw)
      }
    }
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed
    }
  } catch (e) {
    console.error('Failed to load custom events:', e)
  }
  return []
}

const customEvents = ref<CustomScheduleEvent[]>(loadCustomEvents())

function saveCustomEventsToStorage() {
  if (typeof localStorage === 'undefined') return
  const key = getCustomEventsStorageKey()
  try {
    localStorage.setItem(key, JSON.stringify(customEvents.value))
    localStorage.setItem('bjfu-custom-events', JSON.stringify(customEvents.value))
  } catch (e) {
    console.error('Failed to save custom events:', e)
  }
}

// 监听学号变动时同步切换该用户的自定义日程
watch(studentId, () => {
  customEvents.value = loadCustomEvents()
})

const combinedCourses = computed<Course[]>(() => {
  const official = schedule.value?.courses ?? []
  return mergeAdjacentCourses([...official, ...customEvents.value])
})

const combinedSchedule = computed<ScheduleData | null>(() => {
  if (!schedule.value) return null
  return {
    ...schedule.value,
    courses: combinedCourses.value,
  }
})

const weekCourses = computed<Course[]>(() => {
  const week = currentWeek.value
  return combinedCourses.value.filter((c) => {
    if (!showWeekend.value && c.day > 5) return false
    const list = parseWeeks(c.weeks)
    return list === null || list.includes(week)
  })
})

const hasHiddenWeekendCourses = computed(() => {
  if (showWeekend.value) return false
  const week = currentWeek.value
  return combinedCourses.value.some((c) => {
    if (c.day <= 5) return false
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
  const todayCourses = combinedCourses.value
    .filter((c) => {
      const list = parseWeeks(c.weeks)
      const matchesWeek = list === null || list.includes(realWeek)
      return matchesWeek && c.day === today
    })
    .sort((a, b) => a.start - b.start)

  const ongoing = todayCourses.find((c) => {
    const startB = periodSlots[blockOf(c.start) - 1]
    const endB = periodSlots[blockOf(c.end) - 1]
    if (!startB || !endB) return false
    return mins >= startB.from && mins < endB.to
  })
  if (ongoing) return { type: 'ongoing', course: ongoing, label: ongoing.isCustom ? '日程进行中' : '正在进行' }

  const next = todayCourses.find((c) => {
    const startB = periodSlots[blockOf(c.start) - 1]
    if (!startB) return false
    return mins < startB.from
  })
  if (next) {
    const startB = periodSlots[blockOf(next.start) - 1]
    const h = Math.floor(startB.from / 60)
    const mm = startB.from % 60
    return {
      type: 'next',
      course: next,
      label: `${next.isCustom ? '下个安排' : '下一节'} ${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`,
    }
  }
  return { type: 'none', course: null, label: '今日暂无课程安排' }
})

// 移动端专用日视图 / 日程流配置
const mobileViewMode = ref<'agenda' | 'week'>(
  isApp.value ? 'week' : ((localStorage.getItem('bjfu-mobile-view-mode') as 'agenda' | 'week') || 'agenda')
)
const selectedDay = ref<number>(nowDay.value)

function selectDay(d: number) {
  selectedDay.value = d
}

function setMobileViewMode(mode: 'agenda' | 'week') {
  mobileViewMode.value = mode
  localStorage.setItem('bjfu-mobile-view-mode', mode)
  if (mode === 'week') {
    nextTick(() => scrollToToday())
  }
}

const selectedDayCourses = computed(() => {
  return weekCourses.value
    .filter((c) => c.day === selectedDay.value)
    .sort((a, b) => a.start - b.start)
})

function dayHasCourses(d: number): boolean {
  return weekCourses.value.some((c) => c.day === d)
}

function getCourseLiveState(c: Course): { isLive: boolean; label: string } {
  if (currentWeek.value !== systemWeek() || selectedDay.value !== nowDay.value) {
    return { isLive: false, label: '' }
  }
  const now = new Date()
  const mins = now.getHours() * 60 + now.getMinutes()
  const startB = periodSlots[blockOf(c.start) - 1]
  const endB = periodSlots[blockOf(c.end) - 1]
  if (!startB || !endB) return { isLive: false, label: '' }
  if (mins >= startB.from && mins < endB.to) {
    return { isLive: true, label: '正在上课' }
  }
  if (mins < startB.from && startB.from - mins <= 35) {
    return { isLive: false, label: `${startB.from - mins}分钟后开始` }
  }
  return { isLive: false, label: '' }
}

let agendaTouchStartX = 0
let agendaTouchStartY = 0

function onAgendaTouchStart(e: TouchEvent) {
  if (e.touches.length !== 1) return
  agendaTouchStartX = e.touches[0].clientX
  agendaTouchStartY = e.touches[0].clientY
}

function onAgendaTouchEnd(e: TouchEvent) {
  if (e.changedTouches.length !== 1) return
  const dx = e.changedTouches[0].clientX - agendaTouchStartX
  const dy = e.changedTouches[0].clientY - agendaTouchStartY
  if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 40) {
    const maxDay = showWeekend.value ? 7 : 5
    if (dx < 0) {
      if (selectedDay.value < maxDay) {
        selectedDay.value++
      } else if (currentWeek.value < TOTAL_WEEKS) {
        changeWeek(1)
        selectedDay.value = 1
      }
    } else {
      if (selectedDay.value > 1) {
        selectedDay.value--
      } else if (currentWeek.value > 1) {
        changeWeek(-1)
        selectedDay.value = maxDay
      }
    }
  }
}

interface PlacedCourse extends Course {
  key: string
  stackIndex: number
  startBlock: number
  endBlock: number
  rowSpan: number
}
const placedCourses = computed<PlacedCourse[]>(() => {
  const groups = new Map<string, number>()
  return weekCourses.value.map((c, i) => {
    const sB = blockOf(c.start)
    const eB = blockOf(c.end)
    const span = Math.max(1, eB - sB + 1)
    const key = `${c.day}-${sB}`
    const idx = groups.get(key) ?? 0
    groups.set(key, idx + 1)
    return {
      ...c,
      startBlock: sB,
      endBlock: eB,
      rowSpan: span,
      key: c.id ? `custom-${c.id}` : `${c.day}-${c.start}-${c.end}-${c.name}-${i}`,
      stackIndex: idx,
    }
  })
})

function isCellFree(day: number, slotBlock: number): boolean {
  return !weekCourses.value.some((c) => c.day === day && courseCoversSlot(c, slotBlock))
}

const COLOR_PALETTES = [
  { name: 'Indigo', label: '靛蓝', lightBg: '#EEF2FF', lightBorder: '#C7D2FE', lightText: '#3730A3', darkBg: 'rgba(99, 102, 241, 0.18)', darkBorder: 'rgba(129, 140, 248, 0.45)', darkText: '#C7D2FE' },
  { name: 'Emerald', label: '薄荷绿', lightBg: '#ECFDF5', lightBorder: '#A7F3D0', lightText: '#065F46', darkBg: 'rgba(16, 185, 129, 0.18)', darkBorder: 'rgba(52, 211, 153, 0.45)', darkText: '#A7F3D0' },
  { name: 'Sky', label: '晴空蓝', lightBg: '#F0F9FF', lightBorder: '#BAE6FD', lightText: '#0369A1', darkBg: 'rgba(14, 165, 233, 0.18)', darkBorder: 'rgba(56, 189, 248, 0.45)', darkText: '#BAE6FD' },
  { name: 'Fuchsia', label: '紫晶', lightBg: '#FDF4FF', lightBorder: '#F5D0FE', lightText: '#86198F', darkBg: 'rgba(217, 70, 239, 0.18)', darkBorder: 'rgba(232, 121, 249, 0.45)', darkText: '#F5D0FE' },
  { name: 'Amber', label: '暖琥珀', lightBg: '#FFFBEB', lightBorder: '#FDE68A', lightText: '#92400E', darkBg: 'rgba(245, 158, 11, 0.18)', darkBorder: 'rgba(251, 191, 36, 0.45)', darkText: '#FDE68A' },
  { name: 'Violet', label: '罗兰紫', lightBg: '#F5F3FF', lightBorder: '#DDD6FE', lightText: '#5B21B6', darkBg: 'rgba(139, 92, 246, 0.18)', darkBorder: 'rgba(167, 139, 250, 0.45)', darkText: '#DDD6FE' },
  { name: 'Rose', label: '落霞红', lightBg: '#FFF1F2', lightBorder: '#FECDD3', lightText: '#9F1239', darkBg: 'rgba(244, 63, 94, 0.18)', darkBorder: 'rgba(251, 113, 133, 0.45)', darkText: '#FECDD3' },
  { name: 'Teal', label: '青石色', lightBg: '#F0FDFA', lightBorder: '#99F6E4', lightText: '#115E59', darkBg: 'rgba(20, 184, 166, 0.18)', darkBorder: 'rgba(45, 212, 191, 0.45)', darkText: '#99F6E4' },
]

function getCourseCardStyle(c: Course | string, customColor?: string): Record<string, string> {
  const name = typeof c === 'string' ? c : c.name
  const color = typeof c === 'string' ? customColor : c.color
  const isCustom = typeof c === 'string' ? false : !!c.isCustom

  if (!colorfulCards.value && !isCustom) return {}

  let idx = 0
  if (color) {
    const found = COLOR_PALETTES.findIndex((p) => p.name.toLowerCase() === color.toLowerCase())
    idx = found !== -1 ? found : Number(color) || 0
  } else {
    let hash = 0
    for (let i = 0; i < name.length; i++) {
      hash = (hash << 5) - hash + name.charCodeAt(i)
      hash |= 0
    }
    idx = Math.abs(hash) % COLOR_PALETTES.length
  }
  const p = COLOR_PALETTES[idx % COLOR_PALETTES.length]
  return {
    '--card-l-bg': p.lightBg,
    '--card-l-border': p.lightBorder,
    '--card-l-text': p.lightText,
    '--card-d-bg': p.darkBg,
    '--card-d-border': p.darkBorder,
    '--card-d-text': p.darkText,
  }
}

function slotTimeOf(period: number): string {
  const b = periodSlots[blockOf(period) - 1]
  if (!b) return ''
  const startH = String(Math.floor(b.from / 60)).padStart(2, '0')
  const startM = String(b.from % 60).padStart(2, '0')
  const endH = String(Math.floor(b.to / 60)).padStart(2, '0')
  const endM = String(b.to % 60).padStart(2, '0')
  return `${startH}:${startM}-${endH}:${endM}`
}

function weekdayName(day: number): string {
  return weekdays[day - 1] ?? ''
}

// ---- 自定义日程模态框表单与操作 ----
const QUICK_ACTIVITIES = [
  '自习',
  '组会',
  '考研备战',
  '健身运动',
  '社团活动',
  '科研实验',
  '学科竞赛',
  '兼职实习',
  '答辩报告',
  '志愿服务',
]

const showCustomEventModal = ref(false)
const editingEventId = ref<string | null>(null)

interface CustomEventForm {
  name: string
  room: string
  teacher: string
  day: number
  slotIndex: number
  weekType: 'current' | 'all' | 'odd' | 'even' | 'custom'
  customWeeksInput: string
  color: string
  note: string
}

const customForm = ref<CustomEventForm>({
  name: '',
  room: '',
  teacher: '个人安排',
  day: 1,
  slotIndex: 0,
  weekType: 'all',
  customWeeksInput: '',
  color: 'Emerald',
  note: '',
})

function openAddCustomEventModal(preDay?: number, preSlotBlock?: number) {
  editingEventId.value = null
  const defaultDay = preDay ?? (nowDay.value <= (showWeekend.value ? 7 : 5) ? nowDay.value : 1)
  const defaultSlotIdx = preSlotBlock !== undefined ? preSlotBlock - 1 : 0

  customForm.value = {
    name: '',
    room: '',
    teacher: '个人安排',
    day: defaultDay,
    slotIndex: Math.max(0, Math.min(periodSlots.length - 1, defaultSlotIdx)),
    weekType: 'all',
    customWeeksInput: `1-${Math.max(16, TOTAL_WEEKS)}`,
    color: 'Emerald',
    note: '',
  }
  showCustomEventModal.value = true
}

function openEditCustomEventModal(ev: CustomScheduleEvent) {
  editingEventId.value = ev.id
  const sIdx = blockOf(ev.start) - 1
  let wType: 'current' | 'all' | 'odd' | 'even' | 'custom' = 'custom'
  if (ev.weeks === '1-16' || ev.weeks === '1-20' || ev.weeks === `1-${TOTAL_WEEKS}`) {
    wType = 'all'
  } else if (ev.weeks === String(currentWeek.value)) {
    wType = 'current'
  }

  customForm.value = {
    name: ev.name,
    room: ev.room || '',
    teacher: ev.teacher || '个人安排',
    day: ev.day,
    slotIndex: Math.max(0, Math.min(periodSlots.length - 1, sIdx)),
    weekType: wType,
    customWeeksInput: ev.weeks,
    color: ev.color || 'Emerald',
    note: ev.note || '',
  }
  showCustomEventModal.value = true
}

function setWeekType(type: 'current' | 'all' | 'odd' | 'even' | 'custom') {
  customForm.value.weekType = type
  if (type === 'current') {
    customForm.value.customWeeksInput = `${currentWeek.value}`
  } else if (type === 'all') {
    customForm.value.customWeeksInput = `1-${Math.max(16, TOTAL_WEEKS)}`
  } else if (type === 'odd') {
    const odds: number[] = []
    for (let w = 1; w <= Math.max(16, TOTAL_WEEKS); w += 2) odds.push(w)
    customForm.value.customWeeksInput = odds.join(',')
  } else if (type === 'even') {
    const evens: number[] = []
    for (let w = 2; w <= Math.max(16, TOTAL_WEEKS); w += 2) evens.push(w)
    customForm.value.customWeeksInput = evens.join(',')
  }
}

function saveCustomEvent() {
  if (!customForm.value.name.trim()) return

  const slot = periodSlots[customForm.value.slotIndex]
  let weeksVal = customForm.value.customWeeksInput.trim()
  if (customForm.value.weekType === 'current') {
    weeksVal = `${currentWeek.value}`
  } else if (customForm.value.weekType === 'all') {
    weeksVal = `1-${Math.max(16, TOTAL_WEEKS)}`
  }
  if (!weeksVal) weeksVal = `1-${Math.max(16, TOTAL_WEEKS)}`

  if (editingEventId.value) {
    const idx = customEvents.value.findIndex((e) => e.id === editingEventId.value)
    if (idx !== -1) {
      customEvents.value[idx] = {
        ...customEvents.value[idx],
        name: customForm.value.name.trim(),
        room: customForm.value.room.trim() || '',
        teacher: customForm.value.teacher.trim() || '个人安排',
        day: customForm.value.day,
        start: slot.start,
        end: slot.end,
        period: `${slot.label}节`,
        weeks: weeksVal,
        color: customForm.value.color,
        note: customForm.value.note.trim() || '',
        isCustom: true,
      }
    }
  } else {
    const newEvent: CustomScheduleEvent = {
      id: `ev_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      name: customForm.value.name.trim(),
      room: customForm.value.room.trim() || '',
      teacher: customForm.value.teacher.trim() || '个人安排',
      day: customForm.value.day,
      start: slot.start,
      end: slot.end,
      period: `${slot.label}节`,
      weeks: weeksVal,
      color: customForm.value.color,
      note: customForm.value.note.trim() || '',
      isCustom: true,
    }
    customEvents.value.push(newEvent)
  }

  saveCustomEventsToStorage()
  showCustomEventModal.value = false
  if (detail.value && detail.value.isCustom) {
    detail.value = null
  }
}

function deleteCustomEvent(id: string) {
  if (typeof window !== 'undefined' && !window.confirm('确定要删除这条日程安排吗？')) {
    return
  }
  customEvents.value = customEvents.value.filter((e) => e.id !== id)
  saveCustomEventsToStorage()
  detail.value = null
}
</script>

<template>
  <div
    class="relative select-none"
    :class="isApp ? 'h-full w-full flex flex-col overflow-hidden p-1 sm:p-2 bg-[#FAFAFA] dark:bg-[#0A0B0D]' : 'min-h-[calc(100vh-8rem)] py-4 sm:py-12'"
  >
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

    <!-- ==================== APP 专属模式：一页全显，无需滑动，全屏课表 ==================== -->
    <template v-if="isApp">
      <!-- App 极简顶栏 (高度仅 ~36px，所有非课表内容折叠于此) -->
      <header class="shrink-0 flex items-center justify-between px-1.5 py-1 mb-1 border-b border-neutral-200/80 dark:border-neutral-800 text-xs font-mono">
        <div class="flex items-center gap-1.5">
          <button
            type="button"
            class="flex items-center gap-1 px-2.5 py-1 rounded-full bg-neutral-900 text-white dark:bg-emerald-400 dark:text-neutral-950 font-bold text-xs shadow-xs active:scale-95 transition-transform cursor-pointer"
            title="点击切换周次"
            @click="showWeekPicker = true"
          >
            <span>第 {{ currentWeek }} 周</span>
            <svg class="w-3 h-3 opacity-70" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
          <span v-if="schedule" class="text-[11px] text-neutral-400 dark:text-neutral-500 font-sans hidden xs:inline">
            {{ semesterLabel(schedule.semester) }}
          </span>
        </div>

        <div class="flex items-center gap-1">
          <button
            type="button"
            class="px-2 py-0.5 rounded-md text-[11px] font-medium border transition-colors cursor-pointer"
            :class="currentWeek === systemWeek() ? 'bg-neutral-200 dark:bg-neutral-800 text-neutral-900 dark:text-white border-neutral-300 dark:border-neutral-700 font-semibold' : 'text-neutral-500 border-transparent hover:bg-neutral-100 dark:hover:bg-neutral-800'"
            title="快速回今天"
            @click="goToToday"
          >
            今天
          </button>

          <button
            type="button"
            class="px-1.5 py-0.5 rounded-md text-[11px] font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 border border-transparent cursor-pointer"
            :title="showWeekend ? '切换为5天模式' : '切换为7天模式'"
            @click="showWeekend = !showWeekend"
          >
            {{ showWeekend ? '7天' : '5天' }}
          </button>

          <button
            type="button"
            class="p-1 rounded-md text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 cursor-pointer"
            title="添加安排"
            @click="openAddCustomEventModal(nowDay)"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd"/>
            </svg>
          </button>

          <button
            type="button"
            class="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 border border-neutral-300/70 dark:border-neutral-700 transition-colors cursor-pointer active:scale-95"
            title="打开实用工具箱"
            @click="showToolbox = true"
          >
            <span>🧰</span>
            <span>工具箱</span>
          </button>
        </div>
      </header>

      <!-- App 课表全屏网格 (占满剩余100%高度，0滚动条，横滑切周) -->
      <div
        v-if="schedule"
        class="flex-1 min-h-0 flex flex-col rounded-xl border border-neutral-200/90 dark:border-neutral-800 bg-white dark:bg-[#131418] shadow-xs overflow-hidden relative touch-pan-y"
        style="touch-action: pan-y;"
        @touchstart.passive="onTouchStart"
        @touchmove.passive="onTouchMove"
        @touchend="onTouchEnd"
        @touchcancel="onTouchCancel"
      >
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
            class="absolute left-1/2 -translate-x-1/2 top-2 z-40 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono shadow-lg border backdrop-blur-md pointer-events-none transition-all duration-150 select-none"
            :class="[
              edgePullDistance >= PULL_THRESHOLD
                ? 'bg-neutral-900 text-white border-neutral-800 scale-105 shadow-neutral-900/20 dark:bg-white dark:text-neutral-950 dark:border-white'
                : 'bg-white/95 text-neutral-700 border-neutral-200 dark:bg-[#1a1d21]/95 dark:text-neutral-200 dark:border-neutral-700'
            ]"
          >
            <template v-if="edgePullDirection === 'prev'">
              <span v-if="currentWeek <= 1">已是第 1 周</span>
              <template v-else>
                <span>←</span>
                <span>{{ edgePullDistance >= PULL_THRESHOLD ? `松开至第 ${currentWeek - 1} 周` : `滑至第 ${currentWeek - 1} 周` }}</span>
              </template>
            </template>
            <template v-else-if="edgePullDirection === 'next'">
              <span v-if="currentWeek >= TOTAL_WEEKS">已是最后一周</span>
              <template v-else>
                <span>{{ edgePullDistance >= PULL_THRESHOLD ? `松开至第 ${currentWeek + 1} 周` : `滑至第 ${currentWeek + 1} 周` }}</span>
                <span>→</span>
              </template>
            </template>
          </div>
        </transition>

        <!-- Weekday Header Row (~26px) -->
        <div
          class="shrink-0 h-[26px] grid gap-0.5 border-b border-neutral-100 dark:border-neutral-800/80 bg-[#FAFAFA] dark:bg-[#17191e] px-0.5 select-none"
          :class="showWeekend ? 'grid-cols-[24px_repeat(7,1fr)]' : 'grid-cols-[28px_repeat(5,1fr)]'"
        >
          <div class="flex items-center justify-center font-mono text-[8px] text-neutral-400">
            节
          </div>
          <div
            v-for="(day, idx) in displayedWeekdays"
            :key="day"
            class="flex items-center justify-center gap-1 font-mono leading-none rounded-sm transition-colors"
            :class="isToday(idx) ? 'bg-neutral-900 text-white dark:bg-emerald-400 dark:text-neutral-950 font-bold' : 'text-neutral-600 dark:text-neutral-400'"
          >
            <span class="text-[9.5px]">{{ day.replace('周', '') }}</span>
            <span class="text-[7.5px] opacity-75">{{ getDateLabel(currentWeek, idx) }}</span>
          </div>
        </div>

        <!-- 7 Period Rows (Single flat CSS grid so courses span rows seamlessly without scrolling) -->
        <div
          class="flex-1 min-h-0 grid grid-rows-7 gap-0.5 p-0.5"
          :class="showWeekend ? 'grid-cols-[24px_repeat(7,1fr)]' : 'grid-cols-[28px_repeat(5,1fr)]'"
        >
          <!-- Period Slot Labels (Col 1, Rows 1..7) -->
          <div
            v-for="(slot, sIdx) in periodSlots"
            :key="`app-label-${slot.label}`"
            class="flex flex-col items-center justify-center rounded-sm bg-[#FAFAFA] dark:bg-neutral-900/60 font-mono text-neutral-400 border border-neutral-100 dark:border-neutral-800/50 leading-tight select-none"
            :style="{ gridColumn: 1, gridRow: sIdx + 1 }"
          >
            <span class="text-[8.5px] font-bold text-neutral-700 dark:text-neutral-300">{{ slot.label }}</span>
            <span class="text-[7px] text-neutral-400 scale-90">{{ formatSlotMinute(slot.from) }}</span>
          </div>

          <!-- Free Day Cells (only rendered when slot is free) -->
          <template v-for="d in daysCount" :key="`app-day-${d}`">
            <template v-for="(_, sIdx) in periodSlots" :key="`app-free-${d}-${sIdx}`">
              <div
                v-if="isCellFree(d, sIdx + 1)"
                class="rounded border border-neutral-100 dark:border-neutral-800/40 bg-white dark:bg-[#131418] p-0.5 overflow-hidden transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-800/30 cursor-pointer"
                :style="{ gridColumn: d + 1, gridRow: sIdx + 1 }"
                @click="handleCellClick(d, sIdx + 1)"
              />
            </template>
          </template>

          <!-- Placed Course Cards (spans rows: startBlock / span rowSpan) -->
          <div
            v-for="c in placedCourses"
            :key="c.key"
            v-show="!(!showWeekend && c.day > 5)"
            class="rounded p-1 flex flex-col justify-between overflow-hidden relative cursor-pointer active:scale-[0.98] transition-transform select-none z-10"
            :class="[
              c.isCustom ? 'border border-emerald-300 dark:border-emerald-700 shadow-xs' : 'border border-black/5 dark:border-white/5',
              colorfulCards || c.isCustom ? 'course-card-colorful' : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-white'
            ]"
            :style="{
              ...getCourseCardStyle(c),
              gridColumn: c.day + 1,
              gridRow: `${c.startBlock} / span ${c.rowSpan}`,
            }"
            @click.stop="openDetail(c)"
          >
            <div class="min-w-0">
              <div
                class="font-medium leading-tight font-sans break-all"
                :class="c.rowSpan > 1 ? 'text-[10px] line-clamp-4' : 'text-[9px] line-clamp-2'"
              >
                {{ c.name }}
              </div>
              <div v-if="c.rowSpan > 1 && showCourseTime" class="text-[7px] opacity-75 font-mono mt-0.5 leading-none">
                {{ courseTimeRange(c) }}
              </div>
            </div>
            <div class="flex items-center justify-between text-[7.5px] font-mono opacity-80 mt-auto pt-0.5 truncate">
              <span class="truncate">{{ c.room || (c.isCustom ? '自建' : '') }}</span>
              <span v-if="getCourseLiveState(c).isLive" class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping shrink-0" />
            </div>
          </div>
        </div>
      </div>

      <!-- App Mode Login / Sync placeholder if needed -->
      <section v-else-if="showForm" class="flex-1 flex flex-col justify-center max-w-sm mx-auto p-4 font-sans">
        <h2 class="text-base font-semibold text-neutral-900 dark:text-white mb-2">登录并同步课表</h2>
        <form class="space-y-3 font-mono text-xs" @submit.prevent="fetchSchedule(true)">
          <input v-model="studentId" type="text" placeholder="教务学号" class="w-full rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-neutral-900 dark:text-white" />
          <input v-model="password" type="password" placeholder="教务密码" class="w-full rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-neutral-900 dark:text-white" />
          <label class="flex items-center gap-2 cursor-pointer select-none text-neutral-600 dark:text-neutral-400 py-0.5">
            <input v-model="rememberCredentials" type="checkbox" class="rounded border-neutral-300 dark:border-neutral-700 text-neutral-900 focus:ring-0" />
            <span>记住账号与密码 (免重复输入)</span>
          </label>
          <p v-if="error" class="text-red-500 text-xs">{{ error }}</p>
          <button type="submit" :disabled="loading" class="w-full rounded bg-neutral-900 dark:bg-white text-white dark:text-neutral-950 py-2.5 font-bold cursor-pointer">
            {{ loading ? '正在同步...' : '立即同步课表' }}
          </button>
        </form>
      </section>
    </template>

    <!-- ==================== 网页端模式 (原有完整排版) ==================== -->
    <template v-else>
      <!-- Mobile Top Header (sm:hidden) -->
      <header class="sm:hidden relative z-10 flex items-center justify-between pb-2.5 mb-2.5 border-b border-[#E5E5E5]/70 dark:border-neutral-800">
      <div class="flex items-center gap-2">
        <h1 class="text-base font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 flex items-center gap-1.5">
          <BrandWordmark size="xs" :animated-dot="false" />
          <span>课表</span>
        </h1>
        <button
          v-if="schedule && !showForm"
          type="button"
          class="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-xs font-mono font-medium text-neutral-800 dark:text-neutral-200 transition-colors cursor-pointer"
          title="点击切换周次"
          @click="showWeekPicker = true"
        >
          <span>第 {{ currentWeek }} 周</span>
          <svg class="w-3 h-3 text-neutral-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>

      <div v-if="schedule && !showForm" class="flex items-center gap-1.5 font-mono text-xs">
        <button
          type="button"
          class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 font-medium border border-emerald-200 dark:border-emerald-800/80 active:scale-95 transition-all cursor-pointer"
          title="添加安排"
          @click="openAddCustomEventModal(selectedDay)"
        >
          <span class="font-bold text-xs leading-none">+</span>
          <span>安排</span>
        </button>
        <button
          type="button"
          class="p-1.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-300 active:scale-95 transition-all cursor-pointer"
          title="刷新课表"
          :disabled="loading"
          @click="refresh"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': loading }" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/>
          </svg>
        </button>
        <button
          type="button"
          class="p-1.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-300 active:scale-95 transition-all cursor-pointer"
          title="更多功能"
          @click="showToolbox = true"
        >
          <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z"/>
          </svg>
        </button>
      </div>
    </header>

    <!-- Desktop Top Header (hidden sm:flex) -->
    <header class="hidden sm:flex relative z-10 flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-4 border-b border-[#E5E5E5]/70 dark:border-neutral-800 pb-3 sm:pb-6 mb-3 sm:mb-8">
      <div>
        <div class="flex items-center gap-2 font-mono text-[11px] sm:text-xs text-neutral-400 uppercase tracking-widest mb-0.5 sm:mb-1.5">
          <BrandWordmark size="xs" :animated-dot="false" />
          <span class="text-neutral-300">·</span>
          <span>北林课表</span>
          <span class="text-neutral-300">·</span>
          <span class="text-neutral-400 font-mono text-[10px] lowercase bg-neutral-100 dark:bg-neutral-800 px-1.5 py-0.5 rounded">v1.4.2</span>
          <span v-if="schedule" class="text-neutral-300">·</span>
          <span v-if="schedule" class="text-neutral-600 dark:text-neutral-400 font-sans font-normal">{{ semesterLabel(schedule.semester) }}</span>
        </div>
        <h1 class="text-xl sm:text-2xl font-light tracking-tight text-neutral-900 dark:text-neutral-100 font-sans">
          智能课表
        </h1>
      </div>

      <div class="flex items-center gap-2 sm:gap-2.5 flex-wrap">
        <!-- Week Navigation -->
        <nav v-if="schedule && !showForm" class="flex items-center rounded border border-[#E5E5E5] dark:border-neutral-800 bg-white dark:bg-neutral-900 font-mono text-xs shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          <button
            class="px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 dark:text-neutral-400 hover:text-neutral-950 dark:hover:text-white disabled:opacity-30 cursor-pointer"
            :disabled="currentWeek <= 1"
            title="上一周"
            @click="changeWeek(-1)"
          >
            ←
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-2 sm:px-2.5 py-0.5 sm:py-1 font-medium text-neutral-900 dark:text-neutral-100 hover:bg-neutral-50 dark:hover:bg-neutral-800 border-x border-[#E5E5E5]/80 dark:border-neutral-800 text-[11px] sm:text-xs cursor-pointer transition-colors"
            title="点击快速跳转周次"
            @click="showWeekPicker = true"
          >
            <span>第 {{ currentWeek }} 周</span>
            <svg class="w-3 h-3 text-neutral-400" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            class="px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 dark:text-neutral-400 hover:text-neutral-950 dark:hover:text-white disabled:opacity-30 cursor-pointer"
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
            type="button"
            class="rounded border border-emerald-300 bg-emerald-50/70 text-emerald-800 hover:bg-emerald-100 hover:border-emerald-400 dark:bg-emerald-950/40 dark:border-emerald-700/60 dark:text-emerald-300 dark:hover:bg-emerald-900/50 px-2 sm:px-2.5 py-0.5 sm:py-1 transition-colors cursor-pointer text-[11px] sm:text-xs font-medium flex items-center gap-1"
            title="添加自定义时间安排"
            @click="openAddCustomEventModal()"
          >
            <span class="font-bold text-xs leading-none">+</span>
            <span>安排</span>
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] dark:border-neutral-800 bg-white dark:bg-neutral-900 px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:border-neutral-400 transition-colors cursor-pointer text-[11px] sm:text-xs font-medium"
            :class="{ 'bg-neutral-100 text-neutral-900 border-neutral-300 font-semibold dark:bg-[#252a32] dark:text-white dark:border-[#434b57]': currentWeek === systemWeek() }"
            title="快速跳转到当天"
            @click="goToToday"
          >
            今天
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] dark:border-neutral-800 bg-white dark:bg-neutral-900 px-2 sm:px-2.5 py-0.5 sm:py-1 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:border-neutral-400 disabled:opacity-50 transition-colors cursor-pointer text-[11px] sm:text-xs"
            title="刷新最新课表"
            :disabled="loading"
            @click="refresh"
          >
            刷新
          </button>
          <button
            v-if="schedule && !showForm"
            class="rounded border border-[#E5E5E5] dark:border-neutral-800 bg-white dark:bg-neutral-900 px-2.5 sm:px-3 py-0.5 sm:py-1 text-neutral-700 dark:text-neutral-300 hover:text-neutral-950 dark:hover:text-white hover:border-neutral-400 transition-colors cursor-pointer text-[11px] sm:text-xs font-medium flex items-center gap-1"
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

    <!-- 正在查看共享课表横幅 (4位邀请码访问) -->
    <div
      v-if="isViewingShared"
      class="relative z-10 mb-4 sm:mb-6 p-3 sm:p-3.5 rounded-xl bg-neutral-900 dark:bg-[#1c2026] dark:border dark:border-[#333a44] text-white flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 shadow-sm"
    >
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-sm">🔗</span>
        <span class="font-medium text-xs sm:text-sm">正在查看【{{ sharedOwnerName }}】的共享课表</span>
        <span class="font-mono text-[10px] bg-white/20 text-white px-2 py-0.5 rounded tracking-wider">邀请码: {{ sharedCode }}</span>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="px-2.5 py-1 bg-white text-neutral-900 rounded-lg text-xs font-medium hover:bg-neutral-100 cursor-pointer transition-colors"
          @click="saveFriendFromShared"
        >
          {{ sharedSaveSuccess ? '✓ 已保存到好友列表' : '+ 存入我的好友课表' }}
        </button>
        <button
          type="button"
          class="text-neutral-300 hover:text-white text-xs cursor-pointer underline ml-1 transition-colors"
          @click="backToMySchedule"
        >
          返回我的个人课表
        </button>
      </div>
    </div>

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
    </section>

    <!-- Main Timetable Content -->
    <template v-else-if="schedule">
      
      <!-- Today's Status Banner -->
      <div
        class="mb-3 sm:mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-2 rounded border border-[#E5E5E5] dark:border-neutral-800 bg-white dark:bg-neutral-900 px-2.5 py-1.5 sm:p-3 font-mono text-[11px] sm:text-xs shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
        :class="{ 'hidden sm:flex': mobileViewMode === 'agenda' }"
      >
        <div class="flex items-center gap-2 sm:gap-2.5">
          <span class="h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-neutral-900 dark:bg-emerald-400 shrink-0 shadow-xs" />
          <span class="font-medium text-neutral-900 dark:text-neutral-100 shrink-0">{{ todayState.label }}:</span>
          <span v-if="todayState.course" class="text-neutral-700 dark:text-neutral-300 font-sans font-medium truncate">
            {{ todayState.course.name }} ({{ todayState.course.room }})
          </span>
          <span v-else class="text-neutral-400 dark:text-neutral-500 font-sans">
            今日暂无安排课程
          </span>
        </div>
        <div class="flex items-center gap-3">
          <button
            v-if="hasHiddenWeekendCourses"
            class="flex items-center gap-1 text-[10px] sm:text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 cursor-pointer hover:bg-amber-100 transition-colors"
            @click="showWeekend = true"
          >
            <span>⚠️ 周末有课已隐藏 (点击显示)</span>
          </button>
          <div v-if="syncingLatest" class="flex items-center gap-1.5 text-amber-600 text-[10px] sm:text-[11px] animate-pulse font-sans">
            <span class="inline-block h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping" />
            正在拉取最新课表...
          </div>
          <div v-if="termTip" class="text-neutral-400 text-[10px] sm:text-[11px]">
            {{ termTip }}
          </div>
        </div>
      </div>

      <!-- 移动端视图切换与日选择器 (仅在手机端显示) -->
      <div class="sm:hidden mb-3 space-y-2.5">
        <!-- 顶部视图切换药丸 (日视图 vs 周视图) -->
        <div class="flex items-center justify-between">
          <div class="inline-flex p-0.5 rounded-lg bg-neutral-100 dark:bg-neutral-800 text-xs font-medium">
            <button
              type="button"
              class="px-3 py-1 rounded-md transition-all cursor-pointer"
              :class="mobileViewMode === 'agenda' ? 'bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white shadow-xs font-semibold' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900'"
              @click="setMobileViewMode('agenda')"
            >
              📅 今日日程
            </button>
            <button
              type="button"
              class="px-3 py-1 rounded-md transition-all cursor-pointer"
              :class="mobileViewMode === 'week' ? 'bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white shadow-xs font-semibold' : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-900'"
              @click="setMobileViewMode('week')"
            >
              🗓️ 整周课表
            </button>
          </div>

          <!-- 快速定位今天 -->
          <button
            v-if="currentWeek !== systemWeek() || selectedDay !== nowDay"
            type="button"
            class="text-xs font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 rounded-full px-2.5 py-0.5 cursor-pointer"
            @click="goToToday(); selectedDay = nowDay"
          >
            回今天
          </button>
        </div>

        <!-- 7 天水平滑动日期选择条 (仅在日程流模式下展示) -->
        <div v-if="mobileViewMode === 'agenda'" class="grid grid-cols-7 gap-1 bg-white dark:bg-[#131418] border border-[#E5E5E5] dark:border-neutral-800 rounded-xl p-1.5 shadow-xs">
          <button
            v-for="(day, idx) in displayedWeekdays"
            :key="day"
            type="button"
            class="flex flex-col items-center justify-center py-1.5 rounded-lg transition-all cursor-pointer relative"
            :class="[
              selectedDay === idx + 1
                ? 'bg-neutral-900 text-white dark:bg-emerald-400 dark:text-neutral-950 shadow-xs font-bold'
                : isToday(idx)
                  ? 'bg-neutral-100 text-neutral-900 dark:bg-neutral-800/80 dark:text-neutral-100 font-semibold'
                  : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800/50'
            ]"
            @click="selectDay(idx + 1)"
          >
            <span class="text-[11px] leading-tight">{{ day.replace('周', '') }}</span>
            <span class="text-[9px] mt-0.5 font-mono scale-95 opacity-80">{{ getDateLabel(currentWeek, idx) }}</span>
            <span
              v-if="dayHasCourses(idx + 1)"
              class="w-1 h-1 rounded-full mt-0.5 transition-colors"
              :class="selectedDay === idx + 1 ? 'bg-emerald-400 dark:bg-neutral-950' : 'bg-emerald-500/70 dark:bg-emerald-400/80'"
            />
          </button>
        </div>
      </div>

      <!-- 移动端今日日程流 (极简卡片流) -->
      <div
        v-if="mobileViewMode === 'agenda'"
        class="sm:hidden space-y-3 min-h-[300px]"
        @touchstart.passive="onAgendaTouchStart"
        @touchend="onAgendaTouchEnd"
      >
        <template v-if="selectedDayCourses.length > 0">
          <div
            v-for="c in selectedDayCourses"
            :key="c.id || `${c.day}-${c.start}-${c.name}`"
            class="relative rounded-2xl border border-neutral-200/90 dark:border-neutral-800/90 bg-white dark:bg-[#131418] p-4 shadow-xs transition-all active:scale-[0.99] cursor-pointer"
            :style="getCourseCardStyle(c)"
            @click="detail = c"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-1.5 font-mono text-xs text-neutral-500 dark:text-neutral-400">
                <span class="font-semibold text-neutral-800 dark:text-neutral-200">
                  {{ courseTimeRange(c) }}
                </span>
                <span class="text-[10px] px-1.5 py-0.2 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300">
                  {{ coursePeriodLabel(c) }}
                </span>
              </div>

              <span
                v-if="getCourseLiveState(c).isLive"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-sans font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                正在上课
              </span>
              <span
                v-else-if="getCourseLiveState(c).label"
                class="px-2 py-0.5 rounded-full text-[10px] font-mono text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20"
              >
                {{ getCourseLiveState(c).label }}
              </span>
            </div>

            <div class="text-base font-semibold text-neutral-900 dark:text-neutral-50 mb-2 leading-snug">
              {{ c.name }}
            </div>

            <div class="flex items-center gap-2 flex-wrap text-xs text-neutral-600 dark:text-neutral-400">
              <span class="inline-flex items-center gap-1 px-2 py-0.8 rounded-lg bg-neutral-100 dark:bg-neutral-800/80 font-mono text-neutral-700 dark:text-neutral-300">
                📍 {{ c.room || (c.isCustom ? '无地点' : '待定教室') }}
              </span>
              <span v-if="c.teacher" class="inline-flex items-center gap-1 px-2 py-0.8 rounded-lg bg-neutral-100 dark:bg-neutral-800/80 text-neutral-600 dark:text-neutral-300">
                👤 {{ c.teacher }}
              </span>
              <span class="text-[11px] font-mono text-neutral-400 dark:text-neutral-500 ml-auto">
                {{ weekCount(c.weeks) }}
              </span>
            </div>
          </div>
        </template>

        <div
          v-else
          class="rounded-2xl border border-dashed border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-[#131418]/50 p-8 text-center"
        >
          <div class="text-3xl mb-2">☕</div>
          <div class="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
            {{ isToday(selectedDay - 1) ? '今天没有课程安排' : '该日没有排课' }}
          </div>
          <div class="text-xs text-neutral-400 dark:text-neutral-500 mb-4">
            自由安排自习或放松休息
          </div>
          <button
            type="button"
            class="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-full text-xs font-medium bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 hover:opacity-90 cursor-pointer shadow-xs"
            @click="openAddCustomEventModal(selectedDay, 1)"
          >
            <span>+</span>
            <span>添加个人日程</span>
          </button>
        </div>

        <div class="text-center pt-2 pb-1 text-[11px] text-neutral-400 dark:text-neutral-600 font-mono">
          ← 左右滑动切换前后日期 →
        </div>
      </div>

      <!-- Timetable Grid with Edge Swipe Support -->
      <div class="relative" :class="{ 'hidden sm:block': mobileViewMode === 'agenda' }">
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
                ? 'bg-neutral-900 text-white border-neutral-800 scale-105 shadow-neutral-900/20 dark:bg-white dark:text-neutral-950 dark:border-white'
                : 'bg-white/95 text-neutral-700 border-neutral-200 dark:bg-[#1a1d21]/95 dark:text-neutral-200 dark:border-neutral-700'
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
          <div
            class="grid gap-0.5 sm:gap-1.5"
            :class="[
              slotTimeFormat === 'range'
                ? (showWeekend ? 'grid-cols-[46px_repeat(7,1fr)] sm:grid-cols-[70px_repeat(7,1fr)] min-w-[600px] sm:min-w-[820px]' : 'grid-cols-[46px_repeat(5,1fr)] sm:grid-cols-[70px_repeat(5,1fr)] min-w-[480px] sm:min-w-[670px]')
                : (showWeekend ? 'grid-cols-[40px_repeat(7,1fr)] sm:grid-cols-[56px_repeat(7,1fr)] min-w-[580px] sm:min-w-[800px]' : 'grid-cols-[40px_repeat(5,1fr)] sm:grid-cols-[56px_repeat(5,1fr)] min-w-[460px] sm:min-w-[650px]')
            ]"
            :style="{ gridTemplateRows: 'auto repeat(7, minmax(50px, 1fr))' }"
          >
            
            <!-- Column Headers: Weekdays & Dates -->
            <div
              class="sticky left-0 z-20 bg-white dark:bg-[#131418] p-1 sm:p-2 flex flex-col items-center justify-center font-mono text-[9px] sm:text-[11px] text-neutral-400 border-r border-[#E5E5E5]/50 dark:border-neutral-800"
              :style="{ gridColumn: 1, gridRow: 1 }"
            >
              <span class="leading-tight">节次</span>
            </div>
            <div
              v-for="(day, idx) in displayedWeekdays"
              :key="day"
              class="flex flex-col items-center justify-center p-1 sm:p-2 text-center font-mono rounded transition-colors"
              :class="isToday(idx) ? 'today-col-header bg-neutral-900 text-white shadow-sm dark:bg-emerald-400 dark:text-neutral-950 font-bold' : 'text-neutral-700 dark:text-neutral-300 bg-[#FAFAFA] dark:bg-neutral-800/60'"
              :style="{ gridColumn: idx + 2, gridRow: 1 }"
            >
              <span class="text-[10px] sm:text-xs font-medium leading-tight">{{ day }}</span>
              <span
                class="text-[8px] sm:text-[10px] mt-0.5 font-normal leading-tight tracking-tight scale-90 sm:scale-100 origin-center"
                :class="isToday(idx) ? 'text-neutral-300 dark:text-neutral-900' : 'text-neutral-400 dark:text-neutral-500'"
              >
                {{ getDateLabel(currentWeek, idx) }}
              </span>
            </div>

            <!-- Period Labels (Col 1, Rows 2..8) -->
            <div
              v-for="(slot, sIdx) in periodSlots"
              :key="`dt-label-${slot.label}`"
              class="sticky left-0 z-10 flex flex-col items-center justify-center p-0.5 sm:p-2 rounded-l bg-[#FAFAFA] dark:bg-neutral-900/60 font-mono text-neutral-500 dark:text-neutral-400 border border-neutral-100 dark:border-neutral-800 border-r-[#E5E5E5]/50 shadow-[2px_0_4px_-2px_rgba(0,0,0,0.03)]"
              :style="{ gridColumn: 1, gridRow: sIdx + 2 }"
            >
              <span class="font-semibold text-neutral-700 dark:text-neutral-300 text-[9px] sm:text-[11px]">{{ slot.label }}</span>
              <template v-if="slotTimeFormat === 'range'">
                <!-- Mobile compact stacked time -->
                <div class="sm:hidden flex flex-col items-center text-[7px] text-neutral-400 mt-0.5 leading-tight tracking-tight">
                  <span>{{ formatSlotMinute(slot.from) }}</span>
                  <span class="text-[6px] text-neutral-300 leading-none my-[0.5px]">-</span>
                  <span>{{ formatSlotMinute(slot.to) }}</span>
                </div>
                <!-- Desktop inline time -->
                <span class="hidden sm:inline text-[9px] text-neutral-400 mt-0.5 whitespace-nowrap tracking-tighter scale-95 origin-center">
                  {{ formatSlotMinute(slot.from) }} - {{ formatSlotMinute(slot.to) }}
                </span>
              </template>
              <template v-else>
                <span class="text-[7.5px] sm:text-[9px] text-neutral-400 mt-0.5 whitespace-nowrap scale-90 sm:scale-100 origin-center">
                  {{ formatSlotMinute(slot.from) }}
                </span>
              </template>
            </div>

            <!-- Free Day Cells in Desktop Mode -->
            <template v-for="d in daysCount" :key="`dt-day-${d}`">
              <template v-for="(_, sIdx) in periodSlots" :key="`dt-free-${d}-${sIdx}`">
                <div
                  v-if="isCellFree(d, sIdx + 1)"
                  class="relative rounded border border-neutral-100 dark:border-neutral-800 min-h-[50px] sm:min-h-[72px] bg-white dark:bg-[#131418] p-0.5 sm:p-1 group transition-colors hover:border-dashed hover:border-emerald-400/80 hover:bg-emerald-50/20 dark:hover:bg-emerald-950/10 cursor-pointer"
                  :style="{ gridColumn: d + 1, gridRow: sIdx + 2 }"
                  @click="handleCellClick(d, sIdx + 1)"
                >
                  <!-- Free cell hover prompt: + 安排 -->
                  <div class="w-full h-full min-h-[46px] sm:min-h-[66px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none select-none">
                    <span class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-emerald-50/90 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-[10px] sm:text-xs font-sans shadow-xs scale-90 sm:scale-95">
                      <span class="font-bold text-xs leading-none">+</span>
                      <span>安排</span>
                    </span>
                  </div>
                </div>
              </template>
            </template>

            <!-- Placed Course Cards in Desktop Mode -->
            <div
              v-for="c in placedCourses"
              :key="`dt-course-${c.key}`"
              v-show="!(!showWeekend && c.day > 5)"
              class="rounded border p-1 sm:p-1.5 transition-all cursor-pointer flex flex-col justify-between overflow-hidden relative select-none z-10"
              :class="[
                c.isCustom
                  ? 'border-emerald-300/80 dark:border-emerald-700/60 shadow-xs'
                  : '',
                colorfulCards || c.isCustom
                  ? 'course-card-colorful'
                  : 'course-card-default border-[#E5E5E5] bg-[#FAFAFA] dark:bg-neutral-800 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-700 hover:border-neutral-400',
              ]"
              :style="{
                ...getCourseCardStyle(c),
                gridColumn: c.day + 1,
                gridRow: `${c.startBlock + 1} / span ${c.rowSpan}`,
              }"
              @click.stop="openDetail(c)"
            >
              <div>
                <div class="flex items-start justify-between gap-0.5">
                  <div
                    class="font-medium text-neutral-900 dark:text-neutral-100 font-sans leading-tight sm:leading-snug text-[9.5px] sm:text-xs"
                    :class="c.rowSpan > 1 ? 'line-clamp-4' : 'line-clamp-2'"
                  >
                    {{ c.name }}
                  </div>
                  <span
                    v-if="c.isCustom"
                    class="px-1 py-0.2 rounded text-[7.5px] sm:text-[8px] bg-emerald-600/10 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-300 font-sans font-medium shrink-0 leading-tight"
                    title="自定义时间安排"
                  >
                    日程
                  </span>
                </div>
                <div v-if="showCourseTime" class="text-[7.5px] sm:text-[9px] opacity-75 font-mono mt-0.5">
                  {{ courseTimeRange(c) }}
                </div>
              </div>
              <div class="font-mono text-[8px] sm:text-[10px] text-neutral-500 dark:text-neutral-400 mt-0.5 sm:mt-1 flex items-center justify-between gap-0.5">
                <span class="truncate">{{ c.room || (c.isCustom ? '无地点' : '待定') }}</span>
                <span class="text-neutral-400 dark:text-neutral-500 shrink-0 hidden sm:inline">{{ weekCount(c.weeks) }}</span>
              </div>
            </div>

          </div>
        </div>
      </div>

    </template>

    <!-- Loading placeholder for first-time auto sync without cached data -->
    <div v-else-if="syncingLatest || loading" class="max-w-md mx-auto text-center py-20 font-mono text-xs text-neutral-400">
      <div class="inline-block h-5 w-5 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-900 mb-3" />
      <p class="font-sans text-neutral-600 text-sm">正在同步最新课表...</p>
    </div>
    </template>

    <!-- Course Detail Modal -->
    <div
      v-if="detail"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-xs p-4"
      @click.self="detail = null"
    >
      <div class="w-full max-w-sm rounded-lg bg-white dark:bg-[#1a1d21] p-6 shadow-xl border border-[#E5E5E5] dark:border-neutral-700">
        <div class="flex items-center justify-between mb-4 border-b border-neutral-100 dark:border-neutral-800 pb-3">
          <div class="flex items-center gap-2">
            <span v-if="detail.isCustom" class="px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">自建日程</span>
            <h3 class="text-sm font-medium text-neutral-900 dark:text-white font-sans">{{ detail.isCustom ? '日程安排详情' : '课程详情' }}</h3>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 dark:hover:text-white cursor-pointer p-1" title="关闭" @click="detail = null">✕</button>
        </div>
        <div class="space-y-3 font-mono text-xs">
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">{{ detail.isCustom ? '事项名称' : '课程名称' }}</span>
            <span class="text-neutral-900 dark:text-white font-sans font-medium text-sm">{{ detail.name }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">{{ detail.isCustom ? '发起人/参与者' : '授课教师' }}</span>
            <span class="text-neutral-700 dark:text-neutral-300 font-sans">{{ detail.teacher || '—' }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">{{ detail.isCustom ? '安排地点' : '上课地点' }}</span>
            <span class="text-neutral-700 dark:text-neutral-300">{{ detail.room || '—' }}</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">时间节次</span>
            <span class="text-neutral-700 dark:text-neutral-300">{{ weekdayName(detail.day) }} · {{ coursePeriodLabel(detail) }} ({{ courseTimeRange(detail) }})</span>
          </div>
          <div>
            <span class="text-neutral-400 block text-[10px] uppercase">适用周次</span>
            <span class="text-neutral-700 dark:text-neutral-300">{{ weekCount(detail.weeks) }}</span>
          </div>
          <div v-if="detail.note">
            <span class="text-neutral-400 block text-[10px] uppercase">详细备注</span>
            <p class="text-neutral-700 dark:text-neutral-300 font-sans text-xs whitespace-pre-wrap bg-neutral-50 dark:bg-neutral-800/60 p-2.5 rounded border border-neutral-100 dark:border-neutral-700/80 mt-1">{{ detail.note }}</p>
          </div>
        </div>

        <!-- 自建日程：编辑与删除按钮 -->
        <div v-if="detail.isCustom && detail.id" class="mt-5 pt-3.5 border-t border-neutral-100 dark:border-neutral-800 flex items-center justify-end gap-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded border border-red-200 dark:border-red-800/60 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 text-xs font-mono cursor-pointer transition-colors"
            @click="deleteCustomEvent(detail.id)"
          >
            删除安排
          </button>
          <button
            type="button"
            class="px-3.5 py-1.5 rounded bg-neutral-900 text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-950 dark:hover:bg-neutral-100 text-xs font-mono font-medium cursor-pointer transition-colors"
            @click="openEditCustomEventModal(detail as CustomScheduleEvent)"
          >
            编辑修改
          </button>
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
                ? 'bg-neutral-900 border-neutral-900 text-white shadow-sm dark:bg-white dark:text-neutral-950 dark:border-white font-medium'
                : 'bg-neutral-50/70 border-neutral-200/80 text-neutral-800 hover:bg-neutral-100 hover:border-neutral-300 dark:text-neutral-200',
              w === systemWeek() && w !== currentWeek ? 'border-amber-400 bg-amber-50/40 text-amber-950 dark:text-amber-300 dark:border-amber-500 font-medium' : ''
            ]"
            @click="selectWeek(w)"
          >
            <span class="font-medium text-xs leading-tight">第 {{ w }} 周</span>
            <span
              class="text-[9px] mt-0.5 leading-tight scale-95"
              :class="w === currentWeek ? 'text-neutral-300 dark:text-neutral-700' : 'text-neutral-400'"
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
              :class="viewer === 'calendar' ? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 font-medium' : 'border border-[#E5E5E5] text-neutral-600 hover:text-neutral-900'"
              @click="viewer = 'calendar'"
            >
              校历大图
            </button>
            <button
              class="px-3 py-1 rounded transition-colors cursor-pointer"
              :class="viewer === 'time' ? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 font-medium' : 'border border-[#E5E5E5] text-neutral-600 hover:text-neutral-900'"
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

    <!-- Add / Edit Custom Event Modal (添加/修改日程安排弹窗) -->
    <div
      v-if="showCustomEventModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
      @click.self="showCustomEventModal = false"
    >
      <div class="w-full max-w-md rounded-xl bg-white dark:bg-[#1a1d21] p-5 sm:p-6 shadow-2xl border border-[#E5E5E5] dark:border-neutral-700 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-150">
        <div class="flex items-center justify-between pb-3 border-b border-neutral-100 dark:border-neutral-800 mb-4">
          <div class="flex items-center gap-2">
            <span class="h-2 w-2 rounded-full bg-emerald-500" />
            <h3 class="text-sm font-medium text-neutral-900 dark:text-white font-sans">
              {{ editingEventId ? '编辑时间安排' : '新建时间安排' }}
            </h3>
            <span class="text-[11px] font-mono text-neutral-400">Custom Schedule</span>
          </div>
          <button
            type="button"
            class="text-neutral-400 hover:text-neutral-900 dark:hover:text-white cursor-pointer p-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            title="关闭"
            @click="showCustomEventModal = false"
          >
            ✕
          </button>
        </div>

        <form class="space-y-4 text-xs font-sans" @submit.prevent="saveCustomEvent">
          <!-- 事项名称 -->
          <div>
            <label class="block text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase mb-1">
              事项名称 <span class="text-red-500">*</span>
            </label>
            <input
              v-model="customForm.name"
              type="text"
              required
              placeholder="如：自习、组会、考研备战、羽毛球..."
              class="w-full rounded border border-[#E5E5E5] dark:border-neutral-700 bg-[#FAFAFA] dark:bg-neutral-800/80 px-3 py-2 text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:border-neutral-900 dark:focus:border-white focus:bg-white dark:focus:bg-neutral-800 focus:outline-none transition-colors"
            />
            <!-- Quick Chips -->
            <div class="flex flex-wrap gap-1.5 mt-2">
              <button
                v-for="act in QUICK_ACTIVITIES"
                :key="act"
                type="button"
                class="px-2 py-0.5 rounded border border-neutral-200 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-[11px] text-neutral-600 dark:text-neutral-300 hover:border-neutral-400 dark:hover:border-neutral-500 hover:bg-white dark:hover:bg-neutral-700 cursor-pointer transition-colors"
                @click="customForm.name = act"
              >
                {{ act }}
              </button>
            </div>
          </div>

          <!-- 星期与节次 -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase mb-1">
                星期
              </label>
              <select
                v-model.number="customForm.day"
                class="w-full rounded border border-[#E5E5E5] dark:border-neutral-700 bg-[#FAFAFA] dark:bg-neutral-800/80 px-2.5 py-2 text-neutral-900 dark:text-white focus:border-neutral-900 dark:focus:border-white focus:outline-none font-mono"
              >
                <option v-for="(name, idx) in weekdays" :key="idx" :value="idx + 1">
                  {{ name }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase mb-1">
                时段节次
              </label>
              <select
                v-model.number="customForm.slotIndex"
                class="w-full rounded border border-[#E5E5E5] dark:border-neutral-700 bg-[#FAFAFA] dark:bg-neutral-800/80 px-2.5 py-2 text-neutral-900 dark:text-white focus:border-neutral-900 dark:focus:border-white focus:outline-none font-mono"
              >
                <option v-for="(slot, idx) in periodSlots" :key="idx" :value="idx">
                  第 {{ slot.label }} 节 ({{ slotTimeOf(slot.start) }})
                </option>
              </select>
            </div>
          </div>

          <!-- 地点/场所 -->
          <div>
            <label class="block text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase mb-1">
              地点 / 场所 (选填)
            </label>
            <input
              v-model="customForm.room"
              type="text"
              placeholder="如：图书馆四层、二教201、西操场、实验室..."
              class="w-full rounded border border-[#E5E5E5] dark:border-neutral-700 bg-[#FAFAFA] dark:bg-neutral-800/80 px-3 py-2 text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:border-neutral-900 dark:focus:border-white focus:bg-white dark:focus:bg-neutral-800 focus:outline-none transition-colors"
            />
          </div>

          <!-- 适用周次预设与自定义 -->
          <div>
            <div class="flex items-center justify-between mb-1">
              <label class="text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase">
                适用周次
              </label>
              <span class="text-[10px] font-mono text-neutral-400">当前学期共 {{ TOTAL_WEEKS }} 周</span>
            </div>
            
            <div class="grid grid-cols-4 gap-1.5 mb-2 font-mono text-[11px]">
              <button
                type="button"
                class="py-1 rounded border text-center transition-colors cursor-pointer"
                :class="customForm.weekType === 'current' ? 'bg-neutral-900 text-white border-neutral-900 dark:bg-white dark:text-neutral-950 dark:border-white font-medium' : 'border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800'"
                @click="setWeekType('current')"
              >
                本周 (第{{ currentWeek }}周)
              </button>
              <button
                type="button"
                class="py-1 rounded border text-center transition-colors cursor-pointer"
                :class="customForm.weekType === 'all' ? 'bg-neutral-900 text-white border-neutral-900 dark:bg-white dark:text-neutral-950 dark:border-white font-medium' : 'border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800'"
                @click="setWeekType('all')"
              >
                全学期 (1-16周)
              </button>
              <button
                type="button"
                class="py-1 rounded border text-center transition-colors cursor-pointer"
                :class="customForm.weekType === 'odd' ? 'bg-neutral-900 text-white border-neutral-900 dark:bg-white dark:text-neutral-950 dark:border-white font-medium' : 'border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800'"
                @click="setWeekType('odd')"
              >
                单周
              </button>
              <button
                type="button"
                class="py-1 rounded border text-center transition-colors cursor-pointer"
                :class="customForm.weekType === 'even' ? 'bg-neutral-900 text-white border-neutral-900 dark:bg-white dark:text-neutral-950 dark:border-white font-medium' : 'border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800'"
                @click="setWeekType('even')"
              >
                双周
              </button>
            </div>

            <div class="flex items-center gap-2">
              <span class="text-neutral-400 font-mono text-[10px] shrink-0">自定义周:</span>
              <input
                v-model="customForm.customWeeksInput"
                type="text"
                placeholder="例如: 1-8 或 1,3,5,7 或 2-16"
                class="flex-1 rounded border border-[#E5E5E5] dark:border-neutral-700 bg-[#FAFAFA] dark:bg-neutral-800/80 px-2.5 py-1.5 text-neutral-900 dark:text-white font-mono text-xs focus:border-neutral-900 dark:focus:border-white focus:outline-none"
                @input="customForm.weekType = 'custom'"
              />
            </div>
          </div>

          <!-- 卡片配色 -->
          <div>
            <label class="block text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase mb-1.5">
              卡片配色
            </label>
            <div class="grid grid-cols-4 sm:grid-cols-8 gap-2">
              <button
                v-for="p in COLOR_PALETTES"
                :key="p.name"
                type="button"
                class="flex flex-col items-center justify-center p-1.5 rounded-lg border cursor-pointer transition-all"
                :class="[
                  customForm.color === p.name
                    ? 'border-neutral-900 ring-2 ring-neutral-900/20 dark:border-white dark:ring-white/30 scale-105'
                    : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-400'
                ]"
                :style="{ backgroundColor: p.lightBg }"
                @click="customForm.color = p.name"
              >
                <span class="w-3.5 h-3.5 rounded-full mb-1 shadow-xs" :style="{ backgroundColor: p.lightText }" />
                <span class="text-[9px] font-sans font-medium" :style="{ color: p.lightText }">{{ p.label }}</span>
              </button>
            </div>
          </div>

          <!-- 详细备注 -->
          <div>
            <label class="block text-neutral-500 dark:text-neutral-400 font-mono text-[10px] uppercase mb-1">
              详细备注 (选填)
            </label>
            <textarea
              v-model="customForm.note"
              rows="2"
              placeholder="添加重要提示、携带材料或待办事项..."
              class="w-full rounded border border-[#E5E5E5] dark:border-neutral-700 bg-[#FAFAFA] dark:bg-neutral-800/80 px-3 py-2 text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:border-neutral-900 dark:focus:border-white focus:bg-white dark:focus:bg-neutral-800 focus:outline-none transition-colors resize-none"
            />
          </div>

          <!-- 底部操作按钮 -->
          <div class="pt-3 border-t border-neutral-100 dark:border-neutral-800 flex items-center justify-between">
            <button
              v-if="editingEventId"
              type="button"
              class="text-red-600 dark:text-red-400 hover:underline cursor-pointer text-xs"
              @click="deleteCustomEvent(editingEventId)"
            >
              删除该安排
            </button>
            <div v-else />

            <div class="flex items-center gap-2">
              <button
                type="button"
                class="px-3.5 py-1.5 rounded border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 cursor-pointer transition-colors"
                @click="showCustomEventModal = false"
              >
                取消
              </button>
              <button
                type="submit"
                class="px-4 py-1.5 rounded bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 hover:bg-neutral-800 dark:hover:bg-neutral-100 font-medium cursor-pointer transition-colors shadow-xs"
              >
                {{ editingEventId ? '保存修改' : '立即添加' }}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>

    <!-- Full-screen Desktop Drag & Drop Background Overlay -->
    <div
      v-if="isPageDraggingImage"
      class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm pointer-events-none transition-all duration-200"
    >
      <div class="p-8 rounded-2xl bg-white/95 dark:bg-neutral-900/95 border-2 border-dashed border-emerald-500 shadow-2xl flex flex-col items-center gap-3 text-center scale-105 animate-in zoom-in-95 duration-200 max-w-sm mx-4">
        <div class="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-300 flex items-center justify-center text-3xl shadow-xs animate-bounce">
          🖼️
        </div>
        <div class="text-base font-semibold text-neutral-900 dark:text-white font-sans">
          释放图片以设置为课表背景
        </div>
        <p class="text-xs text-neutral-500 dark:text-neutral-400 font-sans leading-relaxed">
          松开鼠标即可自动导入并设置为个性化背景，可在弹窗中自由调节不透明度与模糊度
        </p>
      </div>
    </div>

    <!-- Toolbox Modal (更多功能工具箱) -->
    <ToolboxModal
      :show="showToolbox"
      :schedule="combinedSchedule"
      :student-id="studentId"
      :password="password"
      :custom-events="customEvents"
      :initial-tool="toolboxInitialTool as any"
      @close="showToolbox = false; toolboxInitialTool = 'none'"
      @open-calendar="showToolbox = false; viewer = 'calendar'"
      @logout="handleScheduleLogout"
      @update-bg="onUpdateBg"
      @update-appearance="onUpdateAppearance"
      @open-add-event="showToolbox = false; openAddCustomEventModal()"
      @delete-custom-event="deleteCustomEvent"
    />

  </div>
</template>
