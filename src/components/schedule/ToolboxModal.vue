<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/api'
import { applyTheme, type ThemeMode } from '@/utils/theme'

function showAlert(msg: string) {
  if (typeof window !== 'undefined') {
    window.alert(msg)
  }
}

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

const props = defineProps<{
  show: boolean
  schedule: ScheduleData | null
  studentId: string
  password?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'openCalendar'): void
  (e: 'logout'): void
  (e: 'updateBg', bg: { url: string; opacity: number; blur: number }): void
  (e: 'updateAppearance', pref: { showWeekend: boolean; themeMode: string; colorfulCards: boolean; showCourseTime: boolean }): void
}>()

type ActiveTool =
  | 'none'
  | 'grades'
  | 'exams'
  | 'training'
  | 'classroom'
  | 'autoeval'
  | 'share_friends'
  | 'common_free'
  | 'background'
  | 'appearance'
  | 'export_ics'
  | 'grade_monitor'

const activeTool = ref<ActiveTool>('none')

// ================= 凭据解析与弹窗内即时输入支持 =================
const inputPassword = ref('')
const tempPasswordInput = ref('')
const effectivePassword = computed(() => {
  return (
    props.password?.trim() ||
    inputPassword.value.trim() ||
    localStorage.getItem('bjfu-student-pwd') ||
    ''
  )
})

function submitTempPassword() {
  if (!tempPasswordInput.value.trim()) {
    showAlert('请输入教务系统密码')
    return
  }
  inputPassword.value = tempPasswordInput.value.trim()
  if (localStorage.getItem('bjfu-remember-credentials') === 'true') {
    localStorage.setItem('bjfu-student-pwd', inputPassword.value)
  }
  // 重新触发对应工具查询
  if (activeTool.value === 'grades') fetchGrades(true)
  else if (activeTool.value === 'exams') fetchOfficialExams(true)
  else if (activeTool.value === 'training') fetchTrainingPlan(true)
  else if (activeTool.value === 'classroom') queryClassrooms()
}

// ================= 1. 成绩查询 (GPA与各学期成绩) =================
interface GradeCourse {
  term: string
  code: string
  name: string
  score: string
  credit: number
  hours: string
  attribute: string
  category: string
}

interface GradesData {
  courses: GradeCourse[]
  total_courses: number
  total_credits: number
  avg_gpa: number
  avg_score: number
}

interface LevelExam {
  batch: string
  code: string
  name: string
  time: string
  score: string
  ticket: string
  [key: string]: any
}

const gradesData = ref<GradesData | null>(null)
const gradesLoading = ref(false)
const gradesError = ref('')
const gradesSemester = ref('all')
const activeGradeTab = ref<'grades' | 'level'>('grades')
const levelExams = ref<LevelExam[]>([])
const levelExamsLoading = ref(false)

function loadCachedGrades() {
  if (!props.studentId) return
  try {
    const raw = localStorage.getItem(`bjfu-grades-cache-${props.studentId}`)
    if (raw) {
      gradesData.value = JSON.parse(raw)
    }
  } catch {}
}

async function fetchGrades(_force = false) {
  if (!props.studentId) {
    gradesError.value = '未找到有效学号'
    return
  }
  if (!effectivePassword.value) {
    gradesError.value = '请输入教务系统密码以拉取最新成绩'
    return
  }
  gradesLoading.value = true
  gradesError.value = ''
  try {
    const res = await api.post<GradesData>('/api/schedule/grades', {
      student_id: props.studentId,
      password: effectivePassword.value,
      semester: '',
      display_mode: 'all',
    })
    gradesData.value = res
    localStorage.setItem(`bjfu-grades-cache-${props.studentId}`, JSON.stringify(res))
  } catch (err: any) {
    gradesError.value = err.message || '成绩拉取失败，请检查网络或密码'
  } finally {
    gradesLoading.value = false
  }
}

async function fetchLevelExams() {
  if (!props.studentId || !effectivePassword.value) return
  levelExamsLoading.value = true
  try {
    const res = await api.post<LevelExam[]>('/api/schedule/level_exams', {
      student_id: props.studentId,
      password: effectivePassword.value,
    })
    levelExams.value = res || []
  } catch (err: any) {
    showAlert(err.message || '等级考试查询失败')
  } finally {
    levelExamsLoading.value = false
  }
}

const availableGradeSemesters = computed(() => {
  if (!gradesData.value?.courses) return []
  const terms = [...new Set(gradesData.value.courses.map((c) => c.term).filter(Boolean))]
  return terms.sort().reverse()
})

const displayedCourses = computed(() => {
  if (!gradesData.value?.courses) return []
  if (gradesSemester.value === 'all') return gradesData.value.courses
  return gradesData.value.courses.filter((c) => c.term === gradesSemester.value)
})

// ================= 2. 考试安排与自定义考试 =================
interface OfficialExam {
  batch: string
  code: string
  name: string
  time: string
  room: string
  seat: string
  ticket: string
}

interface CustomExam {
  id: string
  name: string
  date: string
  time: string
  room: string
  seat: string
}

const officialExams = ref<OfficialExam[]>([])
const examsLoading = ref(false)
const examsError = ref('')
const customExams = ref<CustomExam[]>([])
try {
  customExams.value = JSON.parse(localStorage.getItem('bjfu-custom-exams') || '[]')
} catch {}

const newExamName = ref('')
const newExamDate = ref('')
const newExamTime = ref('09:00 - 11:00')
const newExamRoom = ref('')
const newExamSeat = ref('')
const showAddExamForm = ref(false)

function loadCachedExams() {
  if (!props.studentId) return
  try {
    const raw = localStorage.getItem(`bjfu-exams-cache-${props.studentId}`)
    if (raw) {
      officialExams.value = JSON.parse(raw)
    }
  } catch {}
}

async function fetchOfficialExams(_force = false) {
  if (!props.studentId) {
    examsError.value = '未找到有效学号'
    return
  }
  if (!effectivePassword.value) {
    examsError.value = '请输入教务系统密码以拉取考试'
    return
  }
  examsLoading.value = true
  examsError.value = ''
  try {
    const res = await api.post<OfficialExam[]>('/api/schedule/exams', {
      student_id: props.studentId,
      password: effectivePassword.value,
      semester: '',
      category: '',
    })
    officialExams.value = res || []
    localStorage.setItem(`bjfu-exams-cache-${props.studentId}`, JSON.stringify(officialExams.value))
  } catch (err: any) {
    examsError.value = err.message || '考试日程拉取失败'
  } finally {
    examsLoading.value = false
  }
}

function addCustomExam() {
  if (!newExamName.value.trim() || !newExamDate.value) {
    showAlert('请填写考试科目和考试日期')
    return
  }
  customExams.value.push({
    id: String(Date.now()),
    name: newExamName.value.trim(),
    date: newExamDate.value,
    time: newExamTime.value.trim(),
    room: newExamRoom.value.trim() || '待定',
    seat: newExamSeat.value.trim() || '—',
  })
  localStorage.setItem('bjfu-custom-exams', JSON.stringify(customExams.value))
  newExamName.value = ''
  newExamDate.value = ''
  newExamRoom.value = ''
  newExamSeat.value = ''
  showAddExamForm.value = false
}

function removeCustomExam(id: string) {
  customExams.value = customExams.value.filter((e) => e.id !== id)
  localStorage.setItem('bjfu-custom-exams', JSON.stringify(customExams.value))
}

// ================= 3. 培养方案 =================
interface TrainingPlanItem {
  term: string
  code: string
  name: string
  dept: string
  credit: number
  hours: string
  attribute: string
}

const trainingPlan = ref<TrainingPlanItem[]>([])
const planLoading = ref(false)
const planError = ref('')
const selectedPlanCategory = ref('all')

function loadCachedPlan() {
  if (!props.studentId) return
  try {
    const raw = localStorage.getItem(`bjfu-plan-cache-${props.studentId}`)
    if (raw) {
      trainingPlan.value = JSON.parse(raw)
    }
  } catch {}
}

async function fetchTrainingPlan(_force = false) {
  if (!props.studentId) {
    planError.value = '未找到有效学号'
    return
  }
  if (!effectivePassword.value) {
    planError.value = '请输入教务系统密码以拉取培养方案'
    return
  }
  planLoading.value = true
  planError.value = ''
  try {
    const res = await api.post<TrainingPlanItem[]>('/api/schedule/training_plan', {
      student_id: props.studentId,
      password: effectivePassword.value,
    })
    trainingPlan.value = res || []
    localStorage.setItem(`bjfu-plan-cache-${props.studentId}`, JSON.stringify(trainingPlan.value))
  } catch (err: any) {
    planError.value = err.message || '培养方案拉取失败'
  } finally {
    planLoading.value = false
  }
}

const planSearchQuery = ref('')
const planCollapsedTerms = ref<Record<string, boolean>>({})

function formatTermName(rawTerm: string): string {
  if (!rawTerm || !rawTerm.trim() || rawTerm === 'unknown') return '其他 / 未指定学期'
  const t = rawTerm.trim()
  if (/^\d+$/.test(t)) {
    const num = parseInt(t, 10)
    const gradeMap: Record<number, string> = {
      1: '第 1 学期 (大一上)',
      2: '第 2 学期 (大一下)',
      3: '第 3 学期 (大二上)',
      4: '第 4 学期 (大二下)',
      5: '第 5 学期 (大三上)',
      6: '第 6 学期 (大三下)',
      7: '第 7 学期 (大四上)',
      8: '第 8 学期 (大四下)',
    }
    return gradeMap[num] || `第 ${num} 学期`
  }
  const matchNum = t.match(/^第\s*(\d+)\s*学期$/)
  if (matchNum) {
    const num = parseInt(matchNum[1], 10)
    const gradeMap: Record<number, string> = {
      1: '第 1 学期 (大一上)',
      2: '第 2 学期 (大一下)',
      3: '第 3 学期 (大二上)',
      4: '第 4 学期 (大二下)',
      5: '第 5 学期 (大三上)',
      6: '第 6 学期 (大三下)',
      7: '第 7 学期 (大四上)',
      8: '第 8 学期 (大四下)',
    }
    return gradeMap[num] || t
  }
  if (/^\d{4}-\d{4}-[123]$/.test(t)) {
    const parts = t.split('-')
    const subTerm = parts[2] === '1' ? '秋季 (第1学期)' : parts[2] === '2' ? '春季 (第2学期)' : `第${parts[2]}学期`
    return `${parts[0]}-${parts[1]} 学年 ${subTerm}`
  }
  return t
}

interface PlanSemesterGroup {
  termKey: string
  displayName: string
  courses: TrainingPlanItem[]
  totalCredits: number
  courseCount: number
}

const planCategories = computed(() => {
  if (!trainingPlan.value.length) return []
  const set = new Set<string>()
  trainingPlan.value.forEach((item) => {
    const key = item.attribute?.trim() || '其他'
    if (key) set.add(key)
  })
  return [...set]
})

const planTotalCredits = computed(() => {
  return Math.round(trainingPlan.value.reduce((acc, cur) => acc + (cur.credit || 0), 0) * 10) / 10
})

const filteredPlanCourses = computed(() => {
  let list = trainingPlan.value
  if (selectedPlanCategory.value !== 'all') {
    list = list.filter((item) => (item.attribute?.trim() || '其他') === selectedPlanCategory.value)
  }
  if (planSearchQuery.value.trim()) {
    const q = planSearchQuery.value.trim().toLowerCase()
    list = list.filter((item) =>
      item.name.toLowerCase().includes(q) ||
      item.code.toLowerCase().includes(q) ||
      (item.dept && item.dept.toLowerCase().includes(q))
    )
  }
  return list
})

const planSemesterGroups = computed<PlanSemesterGroup[]>(() => {
  const groups: Record<string, TrainingPlanItem[]> = {}
  
  filteredPlanCourses.value.forEach((course) => {
    const key = (course.term && course.term.trim()) ? course.term.trim() : 'unknown'
    if (!groups[key]) groups[key] = []
    groups[key].push(course)
  })

  // 按学期自然时间递增排序
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    if (a === 'unknown' || !a) return 1
    if (b === 'unknown' || !b) return -1
    if (/^\d{4}-\d{4}-\d$/.test(a) && /^\d{4}-\d{4}-\d$/.test(b)) {
      return a.localeCompare(b)
    }
    const numA = parseInt(a.replace(/\D/g, ''), 10)
    const numB = parseInt(b.replace(/\D/g, ''), 10)
    if (!isNaN(numA) && !isNaN(numB) && numA !== numB) {
      return numA - numB
    }
    return a.localeCompare(b, 'zh-CN')
  })

  return sortedKeys.map((key) => {
    const list = groups[key]
    const credits = Math.round(list.reduce((sum, c) => sum + (c.credit || 0), 0) * 10) / 10
    return {
      termKey: key,
      displayName: formatTermName(key === 'unknown' ? '' : key),
      courses: list,
      totalCredits: credits,
      courseCount: list.length,
    }
  })
})

function toggleTermCollapse(termKey: string) {
  planCollapsedTerms.value[termKey] = !planCollapsedTerms.value[termKey]
}

function isTermCollapsed(termKey: string) {
  return !!planCollapsedTerms.value[termKey]
}

const areAllTermsCollapsed = computed(() => {
  if (!planSemesterGroups.value.length) return false
  return planSemesterGroups.value.every((g) => isTermCollapsed(g.termKey))
})

function toggleAllTermsCollapse() {
  const target = !areAllTermsCollapsed.value
  const newMap: Record<string, boolean> = {}
  planSemesterGroups.value.forEach((g) => {
    newMap[g.termKey] = target
  })
  planCollapsedTerms.value = newMap
}

function getAttributeBadgeClass(attr?: string) {
  if (!attr) return 'bg-neutral-100 text-neutral-600'
  if (attr.includes('必修') || attr.includes('核心')) {
    return 'bg-blue-50 text-blue-700 border border-blue-200/60'
  }
  if (attr.includes('选修')) {
    return 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
  }
  if (attr.includes('实践') || attr.includes('实验') || attr.includes('实习') || attr.includes('论文') || attr.includes('设计')) {
    return 'bg-amber-50 text-amber-700 border border-amber-200/60'
  }
  return 'bg-neutral-100 text-neutral-600'
}

// ================= 4. 空闲教室查询 =================
interface FreeRoom {
  name: string
  raw: string
  capacity: string
  building: string
  short_building?: string
}

const classroomBuilding = ref('')
const currentSystemWeek = Math.min(
  30,
  Math.max(1, Math.floor((Date.now() - new Date('2026-09-07T00:00:00').getTime()) / 86400000 / 7) + 1)
)
const classroomWeek = ref(currentSystemWeek)
const currentDayOfWeek = new Date().getDay() || 7
const classroomDay = ref(currentDayOfWeek)
const classroomStartPeriod = ref(1)
const classroomEndPeriod = ref(2)
const selectingAnchor = ref<number | null>(null)
let isDraggingPeriod = false
let dragStartPeriod = 1
let pointerStartX = 0
let hasMoved = false
const periodBarRef = ref<HTMLElement | null>(null)

const PERIOD_TIMES: Record<number, { start: string; end: string }> = {
  1: { start: '08:00', end: '08:45' },
  2: { start: '08:50', end: '09:35' },
  3: { start: '09:50', end: '10:35' },
  4: { start: '10:40', end: '11:25' },
  5: { start: '11:30', end: '12:15' },
  6: { start: '13:30', end: '14:15' },
  7: { start: '14:20', end: '15:05' },
  8: { start: '15:20', end: '16:05' },
  9: { start: '16:10', end: '16:55' },
  10: { start: '18:30', end: '19:15' },
  11: { start: '19:20', end: '20:05' },
  12: { start: '20:10', end: '20:55' },
}

const selectedPeriodTimeRange = computed(() => {
  const s = PERIOD_TIMES[classroomStartPeriod.value]?.start || '08:00'
  const e = PERIOD_TIMES[classroomEndPeriod.value]?.end || '09:35'
  return `${s} - ${e}`
})

function setPeriodPreset(start: number, end: number) {
  classroomStartPeriod.value = start
  classroomEndPeriod.value = end
  selectingAnchor.value = null
}

function handlePointerDown(p: number, e: PointerEvent) {
  isDraggingPeriod = true
  hasMoved = false
  pointerStartX = e.clientX
  dragStartPeriod = p
  if (periodBarRef.value) {
    try {
      periodBarRef.value.setPointerCapture?.(e.pointerId)
    } catch {}
  }
}

function handlePointerMove(e: PointerEvent) {
  if (!isDraggingPeriod || !periodBarRef.value) return
  if (Math.abs(e.clientX - pointerStartX) > 5) {
    hasMoved = true
    const rect = periodBarRef.value.getBoundingClientRect()
    const relX = Math.max(0, Math.min(rect.width, e.clientX - rect.left))
    const p = Math.min(12, Math.max(1, Math.ceil((relX / rect.width) * 12)))
    classroomStartPeriod.value = Math.min(dragStartPeriod, p)
    classroomEndPeriod.value = Math.max(dragStartPeriod, p)
    selectingAnchor.value = null
  }
}

function handlePointerUp(e: PointerEvent) {
  if (!isDraggingPeriod) return
  isDraggingPeriod = false
  if (periodBarRef.value) {
    try {
      periodBarRef.value.releasePointerCapture?.(e.pointerId)
    } catch {}
  }
  if (!hasMoved) {
    if (selectingAnchor.value !== null) {
      classroomStartPeriod.value = Math.min(selectingAnchor.value, dragStartPeriod)
      classroomEndPeriod.value = Math.max(selectingAnchor.value, dragStartPeriod)
      selectingAnchor.value = null
    } else {
      selectingAnchor.value = dragStartPeriod
      classroomStartPeriod.value = dragStartPeriod
      classroomEndPeriod.value = dragStartPeriod
    }
  }
}

function getBuildingTag(room: FreeRoom) {
  if (room.short_building) return room.short_building
  if (room.building) {
    if (room.building.includes('一教')) return '一教'
    if (room.building.includes('二教')) return '二教'
    if (room.building.includes('学研')) return '学研中心'
  }
  if (room.name.includes('一教')) return '一教'
  if (room.name.includes('二教')) return '二教'
  if (room.name.includes('学研') || room.name.startsWith('A') || room.name.startsWith('B') || room.name.startsWith('C')) {
    return '学研中心'
  }
  return '教学区'
}

const freeClassrooms = ref<FreeRoom[]>([])
const classroomsLoading = ref(false)
const classroomsError = ref('')
const classroomsSearched = ref(false)

async function queryClassrooms() {
  if (!props.studentId) {
    classroomsError.value = '未找到有效学号'
    return
  }
  if (!effectivePassword.value) {
    classroomsError.value = '请输入教务系统密码以查询空闲教室'
    return
  }
  const startP = classroomStartPeriod.value
  const endP = classroomEndPeriod.value
  classroomsLoading.value = true
  classroomsError.value = ''
  try {
    const res = await api.post<FreeRoom[]>('/api/schedule/classrooms', {
      student_id: props.studentId,
      password: effectivePassword.value,
      semester: props.schedule?.semester || '2026-2027-1',
      building: classroomBuilding.value,
      week: Number(classroomWeek.value),
      day: Number(classroomDay.value),
      start_period: startP,
      end_period: endP,
    })
    freeClassrooms.value = res || []
    classroomsSearched.value = true
  } catch (err: any) {
    classroomsError.value = err.message || '空闲教室查询失败'
  } finally {
    classroomsLoading.value = false
  }
}

// 自动在打开对应卡片时加载本地缓存或拉取
watch(activeTool, (tool) => {
  if (tool === 'grades') {
    loadCachedGrades()
    if (!gradesData.value && effectivePassword.value) {
      fetchGrades()
    }
  } else if (tool === 'exams') {
    loadCachedExams()
    if (!officialExams.value.length && effectivePassword.value) {
      fetchOfficialExams()
    }
  } else if (tool === 'training') {
    loadCachedPlan()
    if (!trainingPlan.value.length && effectivePassword.value) {
      fetchTrainingPlan()
    }
  } else if (tool === 'share_friends') {
    fetchMyShareCode()
  }
})

// ================= 背景设置 (纯前端直接可用) =================
const bgUrl = ref(localStorage.getItem('bjfu-bg-url') || '')
const bgOpacity = ref(Number(localStorage.getItem('bjfu-bg-opacity')) || 20)
const bgBlur = ref(Number(localStorage.getItem('bjfu-bg-blur')) || 0)

function saveBg() {
  localStorage.setItem('bjfu-bg-url', bgUrl.value.trim())
  localStorage.setItem('bjfu-bg-opacity', String(bgOpacity.value))
  localStorage.setItem('bjfu-bg-blur', String(bgBlur.value))
  emit('updateBg', {
    url: bgUrl.value.trim(),
    opacity: bgOpacity.value / 100,
    blur: bgBlur.value,
  })
  activeTool.value = 'none'
}

function clearBg() {
  bgUrl.value = ''
  bgOpacity.value = 20
  bgBlur.value = 0
  saveBg()
}

function handleFileUpload(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (file.size > 4 * 1024 * 1024) {
    showAlert('图片大小不能超过 4MB')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    if (typeof reader.result === 'string') {
      bgUrl.value = reader.result
    }
  }
  reader.readAsDataURL(file)
}

// ================= 外观设置 =================
const showWeekend = ref(localStorage.getItem('bjfu-show-weekend') !== 'false')
const themeMode = ref<ThemeMode>((localStorage.getItem('bjfu-theme-mode') || 'auto') as ThemeMode)
const colorfulCards = ref(localStorage.getItem('bjfu-colorful-cards') !== 'false')
const showCourseTime = ref(localStorage.getItem('bjfu-show-course-time') === 'true')

function onThemeChange(mode: ThemeMode) {
  themeMode.value = mode
  applyTheme(mode)
  emitAppearance()
}

function onWeekendChange() {
  emitAppearance()
}

function onColorfulChange() {
  emitAppearance()
}

function onCourseTimeChange() {
  emitAppearance()
}

function emitAppearance() {
  localStorage.setItem('bjfu-show-weekend', String(showWeekend.value))
  localStorage.setItem('bjfu-theme-mode', themeMode.value)
  localStorage.setItem('bjfu-colorful-cards', String(colorfulCards.value))
  localStorage.setItem('bjfu-show-course-time', String(showCourseTime.value))
  emit('updateAppearance', {
    showWeekend: showWeekend.value,
    themeMode: themeMode.value,
    colorfulCards: colorfulCards.value,
    showCourseTime: showCourseTime.value,
  })
}

function saveAppearance() {
  emitAppearance()
  activeTool.value = 'none'
}

// ================= 导出 ICS 日历 =================
const exportIncludeExams = ref(true)

function parseWeeksList(weeks: string): number[] {
  const list: number[] = []
  const m = weeks.match(/\d+(?:-\d+)?/g)
  if (!m) return []
  for (const part of m) {
    if (part.includes('-')) {
      const [a, b] = part.split('-').map(Number)
      for (let i = a; i <= b; i++) list.push(i)
    } else {
      list.push(Number(part))
    }
  }
  return [...new Set(list)].sort((a, b) => a - b)
}

function generateICS(): string {
  const TERM_START = '2026-09-07'
  const [startY, startM, startD] = TERM_START.split('-').map(Number)

  const periodTimeMap: Record<number, { start: string; end: string }> = {
    1: { start: '080000', end: '093500' },
    2: { start: '080000', end: '093500' },
    3: { start: '095000', end: '112500' },
    4: { start: '095000', end: '112500' },
    5: { start: '113000', end: '121500' },
    6: { start: '133000', end: '150500' },
    7: { start: '133000', end: '150500' },
    8: { start: '152000', end: '165500' },
    9: { start: '152000', end: '165500' },
    10: { start: '183000', end: '200500' },
    11: { start: '183000', end: '200500' },
    12: { start: '201000', end: '205500' },
  }

  let ics = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//snhgn.me//BJFU Timetable//CN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'X-WR-CALNAME:北林课表',
    'X-WR-TIMEZONE:Asia/Shanghai',
  ]

  if (props.schedule?.courses) {
    props.schedule.courses.forEach((c, idx) => {
      const weeks = parseWeeksList(c.weeks)
      const dayOffset = c.day - 1
      const times = periodTimeMap[c.start] || { start: '080000', end: '093500' }

      weeks.forEach((w) => {
        const d = new Date(startY, startM - 1, startD + (w - 1) * 7 + dayOffset)
        const dateStr = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`

        ics.push(
          'BEGIN:VEVENT',
          `UID:course-${idx}-w${w}-${dateStr}@snhgn.me`,
          `DTSTAMP:${dateStr}T${times.start}Z`,
          `DTSTART;TZID=Asia/Shanghai:${dateStr}T${times.start}`,
          `DTEND;TZID=Asia/Shanghai:${dateStr}T${times.end}`,
          `SUMMARY:${c.name}`,
          `LOCATION:${c.room || '待定'}`,
          `DESCRIPTION:教师: ${c.teacher || '—'}\\n节次: ${c.period}\\n第${w}周`,
          'STATUS:CONFIRMED',
          'END:VEVENT'
        )
      })
    })
  }

  // 考试导出 (官方 + 自定义)
  if (exportIncludeExams.value) {
    officialExams.value.forEach((e, idx) => {
      const m = e.time.match(/(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})-(\d{2}:\d{2})/)
      if (m) {
        const cleanDate = m[1].replace(/-/g, '')
        const startT = m[2].replace(':', '') + '00'
        const endT = m[3].replace(':', '') + '00'
        ics.push(
          'BEGIN:VEVENT',
          `UID:official-exam-${idx}-${cleanDate}@snhgn.me`,
          `DTSTAMP:${cleanDate}T${startT}Z`,
          `DTSTART;TZID=Asia/Shanghai:${cleanDate}T${startT}`,
          `DTEND;TZID=Asia/Shanghai:${cleanDate}T${endT}`,
          `SUMMARY:[考试] ${e.name}`,
          `LOCATION:${e.room}`,
          `DESCRIPTION:场次: ${e.batch}\\n时间: ${e.time}\\n座位号: ${e.seat}\\n准考证号: ${e.ticket}`,
          'STATUS:CONFIRMED',
          'END:VEVENT'
        )
      }
    })

    customExams.value.forEach((e) => {
      const cleanDate = e.date.replace(/-/g, '')
      ics.push(
        'BEGIN:VEVENT',
        `UID:exam-${e.id}@snhgn.me`,
        `DTSTAMP:${cleanDate}T090000Z`,
        `DTSTART;TZID=Asia/Shanghai:${cleanDate}T090000`,
        `DTEND;TZID=Asia/Shanghai:${cleanDate}T110000`,
        `SUMMARY:[考试] ${e.name}`,
        `LOCATION:${e.room}`,
        `DESCRIPTION:时间: ${e.time}\\n座位号: ${e.seat}`,
        'STATUS:CONFIRMED',
        'END:VEVENT'
      )
    })
  }

  ics.push('END:VCALENDAR')
  return ics.join('\r\n')
}

function downloadICS() {
  const content = generateICS()
  const blob = new Blob([content], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bjfu_schedule_${props.studentId || 'timetable'}.ics`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ================= 4位邀请码与共享课表 =================
interface SharedFriend {
  name: string
  code: string
  semester?: string
  coursesCount?: number
}

const myShareCode = ref('')
const myOwnerName = ref(localStorage.getItem('bjfu-share-nickname') || '')
const isGeneratingCode = ref(false)
const copySuccess = ref(false)
const shareError = ref('')

const inputFriendCode = ref('')
const inputFriendName = ref('')
const isAddingFriend = ref(false)
const addFriendError = ref('')

const sharedFriends = ref<SharedFriend[]>([])
try {
  const rawShared = localStorage.getItem('bjfu-shared-friends')
  if (rawShared) {
    sharedFriends.value = JSON.parse(rawShared)
  }
} catch {}

async function fetchMyShareCode() {
  if (!props.studentId) return
  try {
    const res = await api.get<{ has_code: boolean; code?: string; owner_name?: string }>(
      `/api/schedule/share/my?student_id=${encodeURIComponent(props.studentId)}`
    )
    if (res && res.has_code && res.code) {
      myShareCode.value = res.code
      if (res.owner_name && !myOwnerName.value) {
        myOwnerName.value = res.owner_name
      }
    }
  } catch {}
}

async function createOrRegenerateCode(regenerate: boolean = false) {
  if (!props.studentId) {
    showAlert('请先获取或导入个人课表后再生成邀请码')
    return
  }
  isGeneratingCode.value = true
  shareError.value = ''
  try {
    const res = await api.post<{ code: string; owner_name: string; share_url: string }>(
      '/api/schedule/share/create',
      {
        student_id: props.studentId,
        owner_name: myOwnerName.value.trim(),
        regenerate,
      }
    )
    myShareCode.value = res.code
    localStorage.setItem('bjfu-share-nickname', myOwnerName.value.trim())
    if (regenerate) {
      showAlert(`已成功生成全新 4 位邀请码：${res.code}`)
    }
  } catch (err: any) {
    shareError.value = err.message || '生成邀请码失败'
  } finally {
    isGeneratingCode.value = false
  }
}

async function copyShareLink() {
  if (!myShareCode.value) return
  const url = `${window.location.origin}/schedule?code=${myShareCode.value}`
  try {
    await navigator.clipboard.writeText(url)
    copySuccess.value = true
    setTimeout(() => {
      copySuccess.value = false
    }, 2000)
  } catch {
    showAlert(`分享链接为：${url}`)
  }
}

async function copyShareCodeOnly() {
  if (!myShareCode.value) return
  try {
    await navigator.clipboard.writeText(myShareCode.value)
    showAlert(`已复制邀请码：${myShareCode.value}`)
  } catch {}
}

async function addFriendByCode() {
  const code = inputFriendCode.value.trim().toUpperCase()
  if (!code || code.length !== 4) {
    addFriendError.value = '请输入标准的 4 位邀请码 (例如: 8K2M)'
    return
  }
  if (code === myShareCode.value) {
    addFriendError.value = '不能绑定自己的邀请码'
    return
  }
  if (sharedFriends.value.some((f) => f.code === code)) {
    addFriendError.value = '该邀请码已在好友列表中'
    return
  }

  isAddingFriend.value = true
  addFriendError.value = ''
  try {
    const res = await api.get<{ code: string; owner_name: string; semester: string; courses: any[] }>(
      `/api/schedule/share/${encodeURIComponent(code)}`
    )
    const displayName = inputFriendName.value.trim() || res.owner_name || '同学'
    sharedFriends.value.push({
      name: displayName,
      code: res.code,
      semester: res.semester,
      coursesCount: res.courses?.length || 0,
    })
    localStorage.setItem('bjfu-shared-friends', JSON.stringify(sharedFriends.value))
    inputFriendCode.value = ''
    inputFriendName.value = ''
    showAlert(`成功绑定好友【${displayName}】的共享课表！`)
  } catch (err: any) {
    addFriendError.value = err.message || '邀请码不存在或已失效'
  } finally {
    isAddingFriend.value = false
  }
}

function removeFriend(idx: number) {
  sharedFriends.value.splice(idx, 1)
  localStorage.setItem('bjfu-shared-friends', JSON.stringify(sharedFriends.value))
}

// 模拟成绩出分监控
const monitorEmail = ref(localStorage.getItem('bjfu-monitor-email') || '')
const monitorEnabled = ref(localStorage.getItem('bjfu-monitor-enabled') === 'true')
function saveMonitor() {
  localStorage.setItem('bjfu-monitor-email', monitorEmail.value.trim())
  localStorage.setItem('bjfu-monitor-enabled', String(monitorEnabled.value))
  showAlert('成绩监控设置已保存')
  activeTool.value = 'none'
}
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4" @click.self="emit('close')">
    <div class="w-full max-w-lg rounded-xl bg-white shadow-2xl border border-[#E5E5E5] flex flex-col max-h-[88vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
      
      <!-- Toolbox Header -->
      <div class="flex items-center justify-between px-5 py-4 border-b border-neutral-100">
        <div class="flex items-center gap-2">
          <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-neutral-900 text-white">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
          </div>
          <div>
            <h2 class="text-sm font-medium text-neutral-900 font-sans">工具箱 · 更多功能</h2>
            <p class="text-[11px] text-neutral-400 font-mono">BJFU Toolbox & Services</p>
          </div>
        </div>
        <button class="text-neutral-400 hover:text-neutral-900 transition-colors p-1 cursor-pointer" @click="emit('close')">
          ✕
        </button>
      </div>

      <!-- Main Tool Selection Grid -->
      <div class="overflow-y-auto p-5 space-y-6 flex-1 text-xs">
        
        <!-- Section 1: 教务与工具 -->
        <div>
          <div class="flex items-center gap-1.5 text-neutral-400 uppercase tracking-widest text-[10px] font-mono mb-3">
            <svg class="w-3.5 h-3.5 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <span>教务与工具</span>
          </div>

          <div class="grid grid-cols-3 gap-2.5">
            <!-- 成绩查询 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'grades'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span class="font-medium text-neutral-800">成绩查询</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">查看本人成绩</span>
            </button>

            <!-- 考试安排 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'exams'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="font-medium text-neutral-800">考试安排</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">查看考试安排</span>
            </button>

            <!-- 培养方案 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'training'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <span class="font-medium text-neutral-800">培养方案</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">查看培养方案</span>
            </button>

            <!-- 教室查询 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'classroom'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
              <span class="font-medium text-neutral-800">教室查询</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">查询空闲教室</span>
            </button>

            <!-- 自动评教 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'autoeval'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
              <span class="font-medium text-neutral-800">自动评教</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">一键课程评教</span>
            </button>

            <!-- 实用信息 (校历与作息) -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="emit('openCalendar')"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="font-medium text-neutral-800">校历作息</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">校历与时间表</span>
            </button>
          </div>
        </div>

        <!-- Section 2: 个性与互动 -->
        <div>
          <div class="flex items-center gap-1.5 text-neutral-400 uppercase tracking-widest text-[10px] font-mono mb-3">
            <svg class="w-3.5 h-3.5 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
            <span>个性与互动</span>
          </div>

          <div class="grid grid-cols-3 gap-2.5">
            <!-- 共享课表 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'share_friends'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
              <span class="font-medium text-neutral-800">共享课表</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">好友课表绑定</span>
            </button>

            <!-- 寻找共同空闲 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'common_free'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span class="font-medium text-neutral-800">共同空闲</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">寻找共同无课</span>
            </button>

            <!-- 设置背景 (已可用) -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'background'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="font-medium text-neutral-800">设置背景</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">自定义课表图</span>
            </button>

            <!-- 外观设置 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'appearance'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
              <span class="font-medium text-neutral-800">外观设置</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">周末与主题</span>
            </button>

            <!-- 导出课表 (已可用) -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'export_ics'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span class="font-medium text-neutral-800">导出课表</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">导出日历文件</span>
            </button>

            <!-- 成绩出分监控 -->
            <button
              class="flex flex-col items-center justify-center p-3 rounded-lg border border-[#E5E5E5] bg-[#FAFAFA] hover:bg-neutral-100 hover:border-neutral-400 transition-all text-center cursor-pointer group"
              @click="activeTool = 'grade_monitor'"
            >
              <svg class="w-5 h-5 text-neutral-700 mb-1.5 group-hover:scale-105 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span class="font-medium text-neutral-800">出分监控</span>
              <span class="text-[10px] text-neutral-400 mt-0.5">新成绩提醒</span>
            </button>
          </div>
        </div>

      </div>

      <!-- Toolbox Footer: Logout / Switch -->
      <div class="p-3 border-t border-neutral-100 bg-[#FAFAFA] flex items-center justify-between">
        <span class="text-[11px] font-mono text-neutral-400 pl-2">学号: {{ studentId || '未登录' }}</span>
        <button
          type="button"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
          @click="emit('logout')"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>退出当前课表</span>
        </button>
      </div>

    </div>

    <!-- ======================= 子功能弹窗合集 ======================= -->

    <!-- 1. 成绩查询弹窗 -->
    <div v-if="activeTool === 'grades'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-xl rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] flex flex-col overflow-hidden">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">成绩查询与绩点分析</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Academic Grades & GPA Analysis</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <!-- 密码未提供时的即时补全卡片 -->
        <div v-if="!effectivePassword" class="rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-center space-y-2.5">
          <div class="text-xs text-neutral-600">当前未保存教务密码，请输入密码以拉取个人成绩与计算 GPA：</div>
          <div class="flex gap-2 max-w-xs mx-auto">
            <input
              v-model="tempPasswordInput"
              type="password"
              placeholder="教务系统登录密码"
              class="flex-1 px-3 py-1.5 border border-neutral-300 rounded text-xs bg-white focus:outline-none focus:border-neutral-900"
              @keyup.enter="submitTempPassword"
            />
            <button
              class="px-3.5 py-1.5 bg-neutral-900 text-white rounded text-xs hover:bg-neutral-800 cursor-pointer"
              @click="submitTempPassword"
            >
              确定
            </button>
          </div>
        </div>

        <!-- 功能栏：学期筛选、四六级等级切换与刷新 -->
        <div class="flex items-center justify-between text-xs gap-2">
          <div class="flex items-center gap-1.5">
            <button
              class="px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors"
              :class="activeGradeTab === 'grades' ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'"
              @click="activeGradeTab = 'grades'"
            >
              课程成绩
            </button>
            <button
              class="px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors"
              :class="activeGradeTab === 'level' ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'"
              @click="activeGradeTab = 'level'; if (!levelExams.length) fetchLevelExams()"
            >
              等级考试 (四六级)
            </button>
          </div>

          <div v-if="activeGradeTab === 'grades'" class="flex items-center gap-2">
            <select
              v-if="availableGradeSemesters.length"
              v-model="gradesSemester"
              class="border border-[#E5E5E5] rounded px-2 py-1 bg-white text-xs text-neutral-700"
            >
              <option value="all">全部学期 ({{ gradesData?.courses.length || 0 }} 门)</option>
              <option v-for="t in availableGradeSemesters" :key="t" :value="t">{{ t }}</option>
            </select>
            <button
              class="px-2.5 py-1 text-xs border border-[#E5E5E5] rounded hover:border-neutral-400 bg-white cursor-pointer flex items-center gap-1 disabled:opacity-50"
              :disabled="gradesLoading"
              @click="fetchGrades(true)"
            >
              <span :class="{ 'animate-spin': gradesLoading }">🔄</span>
              <span>{{ gradesLoading ? '拉取中' : '刷新' }}</span>
            </button>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="gradesError" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 flex items-center justify-between">
          <span>{{ gradesError }}</span>
          <button class="px-2 py-0.5 bg-red-600 text-white rounded text-[11px] cursor-pointer" @click="fetchGrades(true)">重试</button>
        </div>

        <!-- 课程成绩视图 -->
        <div v-if="activeGradeTab === 'grades'" class="flex-1 overflow-y-auto space-y-3">
          <!-- 统计概览指标 -->
          <div v-if="gradesData" class="grid grid-cols-4 gap-2 font-mono text-center">
            <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-2.5">
              <div class="text-[11px] text-neutral-400 font-sans">平均绩点 (GPA)</div>
              <div class="text-lg font-bold text-neutral-900 mt-0.5">{{ gradesData.avg_gpa }}</div>
            </div>
            <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-2.5">
              <div class="text-[11px] text-neutral-400 font-sans">加权平均分</div>
              <div class="text-lg font-bold text-neutral-900 mt-0.5">{{ gradesData.avg_score }}</div>
            </div>
            <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-2.5">
              <div class="text-[11px] text-neutral-400 font-sans">已修学分</div>
              <div class="text-lg font-bold text-neutral-900 mt-0.5">{{ gradesData.total_credits }}</div>
            </div>
            <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-2.5">
              <div class="text-[11px] text-neutral-400 font-sans">课程门数</div>
              <div class="text-lg font-bold text-neutral-900 mt-0.5">{{ gradesData.total_courses }}</div>
            </div>
          </div>

          <!-- 加载中动画 -->
          <div v-if="gradesLoading && !gradesData" class="py-12 text-center text-xs text-neutral-400 space-y-2">
            <div class="inline-block animate-spin text-lg">⏳</div>
            <div>正在连接北林教务系统拉取成绩并计算绩点...</div>
          </div>

          <!-- 课程列表表格 -->
          <div v-else-if="displayedCourses.length" class="border border-[#E5E5E5] rounded-lg overflow-hidden">
            <table class="w-full text-left text-xs font-mono">
              <thead class="bg-[#FAFAFA] border-b border-[#E5E5E5] text-neutral-500 text-[11px]">
                <tr>
                  <th class="p-2.5 font-normal">课程名称</th>
                  <th class="p-2.5 font-normal">学期</th>
                  <th class="p-2.5 font-normal">性质</th>
                  <th class="p-2.5 font-normal">学分</th>
                  <th class="p-2.5 font-normal text-right">成绩</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-neutral-100">
                <tr v-for="c in displayedCourses" :key="c.code + c.term" class="hover:bg-neutral-50/70 transition-colors">
                  <td class="p-2.5 font-sans font-medium text-neutral-900">
                    <div>{{ c.name }}</div>
                    <div class="text-[10px] text-neutral-400 font-mono">{{ c.code }}</div>
                  </td>
                  <td class="p-2.5 text-neutral-400 text-[11px]">{{ c.term }}</td>
                  <td class="p-2.5 text-neutral-500">
                    <span class="px-1.5 py-0.5 bg-neutral-100 text-neutral-600 rounded text-[10px]">{{ c.attribute || '必修' }}</span>
                  </td>
                  <td class="p-2.5 text-neutral-700">{{ c.credit }}</td>
                  <td class="p-2.5 text-right font-semibold" :class="Number(c.score) >= 90 || c.score === '优秀' || c.score === '优' ? 'text-emerald-600 font-bold' : (Number(c.score) < 60 || c.score === '不及格' ? 'text-red-500' : 'text-neutral-900')">
                    {{ c.score }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="!gradesLoading" class="text-center py-10 text-xs text-neutral-400">
            暂无成绩数据，请点击上方“刷新”拉取
          </div>
        </div>

        <!-- 等级考试视图 -->
        <div v-else class="flex-1 overflow-y-auto space-y-3">
          <div v-if="levelExamsLoading" class="py-12 text-center text-xs text-neutral-400 space-y-2">
            <div class="inline-block animate-spin text-lg">⏳</div>
            <div>正在拉取四六级等社会等级考试记录...</div>
          </div>
          <div v-else-if="levelExams.length" class="space-y-2">
            <div v-for="(lex, i) in levelExams" :key="i" class="p-3 border border-[#E5E5E5] rounded-lg bg-[#FAFAFA] flex items-center justify-between">
              <div>
                <div class="font-medium text-neutral-900 text-xs">{{ lex.name }}</div>
                <div class="text-[11px] text-neutral-400 font-mono mt-0.5">时间: {{ lex.time || '—' }} · 准考证号: {{ lex.ticket || '—' }}</div>
              </div>
              <div class="text-right">
                <div class="text-sm font-bold text-neutral-900 font-mono">{{ lex.score }}</div>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-10 text-xs text-neutral-400">
            暂无等级考试记录或尚未查询
          </div>
        </div>

      </div>
    </div>

    <!-- 2. 考试安排弹窗 -->
    <div v-if="activeTool === 'exams'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] flex flex-col overflow-hidden">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">考试日程安排</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Exam Schedule & Venue Details</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <!-- 密码未提供时的即时补全卡片 -->
        <div v-if="!effectivePassword" class="rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-center space-y-2.5">
          <div class="text-xs text-neutral-600">当前未保存教务密码，请输入密码以同步期末考试考场与座位号：</div>
          <div class="flex gap-2 max-w-xs mx-auto">
            <input
              v-model="tempPasswordInput"
              type="password"
              placeholder="教务系统登录密码"
              class="flex-1 px-3 py-1.5 border border-neutral-300 rounded text-xs bg-white focus:outline-none focus:border-neutral-900"
              @keyup.enter="submitTempPassword"
            />
            <button
              class="px-3.5 py-1.5 bg-neutral-900 text-white rounded text-xs hover:bg-neutral-800 cursor-pointer"
              @click="submitTempPassword"
            >
              确定
            </button>
          </div>
        </div>

        <div class="flex items-center justify-between text-xs">
          <span class="text-neutral-500 font-medium">当前考试日程列表</span>
          <div class="flex items-center gap-2">
            <button
              class="px-2.5 py-1 text-xs border border-[#E5E5E5] rounded hover:border-neutral-400 bg-white cursor-pointer flex items-center gap-1 disabled:opacity-50"
              :disabled="examsLoading"
              @click="fetchOfficialExams(true)"
            >
              <span :class="{ 'animate-spin': examsLoading }">🔄</span>
              <span>{{ examsLoading ? '同步中' : '同步教务' }}</span>
            </button>
            <button
              class="px-2.5 py-1 text-xs border border-[#E5E5E5] rounded hover:border-neutral-400 bg-white cursor-pointer"
              @click="showAddExamForm = !showAddExamForm"
            >
              {{ showAddExamForm ? '收起表单' : '+ 自定义考试' }}
            </button>
          </div>
        </div>

        <div v-if="examsError" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 flex items-center justify-between">
          <span>{{ examsError }}</span>
          <button class="px-2 py-0.5 bg-red-600 text-white rounded text-[11px] cursor-pointer" @click="fetchOfficialExams(true)">重试</button>
        </div>

        <!-- 添加考试表单 -->
        <div v-if="showAddExamForm" class="p-4 border border-[#E5E5E5] rounded-lg bg-[#FAFAFA] space-y-3 text-xs shrink-0">
          <div>
            <label class="block text-neutral-500 mb-1">考试科目</label>
            <input v-model="newExamName" placeholder="例如：线性代数期末考" class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-neutral-500 mb-1">日期</label>
              <input v-model="newExamDate" type="date" class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
            </div>
            <div>
              <label class="block text-neutral-500 mb-1">时间</label>
              <input v-model="newExamTime" placeholder="09:00 - 11:00" class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-neutral-500 mb-1">地点 / 考场</label>
              <input v-model="newExamRoom" placeholder="二教 201" class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
            </div>
            <div>
              <label class="block text-neutral-500 mb-1">座位号</label>
              <input v-model="newExamSeat" placeholder="28 号" class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
            </div>
          </div>
          <button class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="addCustomExam">
            保存考试
          </button>
        </div>

        <!-- 考试列表主体 -->
        <div class="flex-1 overflow-y-auto space-y-2 text-xs">
          <!-- 加载中 -->
          <div v-if="examsLoading && !officialExams.length" class="py-10 text-center text-neutral-400 space-y-2">
            <div class="inline-block animate-spin text-lg">⏳</div>
            <div>正在从教务系统同步最新排考日程...</div>
          </div>

          <!-- 官方教务考试列表 -->
          <div v-for="e in officialExams" :key="e.code + e.time" class="p-3.5 border border-[#E5E5E5] rounded-lg bg-[#FAFAFA] flex items-start justify-between">
            <div class="space-y-1">
              <div class="flex items-center gap-1.5">
                <span class="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded text-[10px] font-medium">{{ e.batch || '教务考试' }}</span>
                <span class="font-medium text-neutral-900 text-sm font-sans">{{ e.name }}</span>
              </div>
              <div class="text-xs text-neutral-600 font-mono">
                📅 {{ e.time }} · 📍 {{ e.room || '待定' }}
              </div>
              <div class="text-[11px] text-neutral-400 font-mono">
                座位号: <span class="font-semibold text-neutral-800">{{ e.seat || '—' }}</span> · 准考证号: {{ e.ticket || '—' }}
              </div>
            </div>
          </div>

          <!-- 自定义考试列表 -->
          <div v-for="e in customExams" :key="e.id" class="flex items-center justify-between p-3.5 border border-[#E5E5E5] rounded-lg bg-white">
            <div>
              <div class="flex items-center gap-1.5">
                <span class="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px]">自定义</span>
                <span class="font-medium text-neutral-900 text-sm font-sans">{{ e.name }}</span>
              </div>
              <div class="text-xs text-neutral-500 mt-1 font-mono">
                📅 {{ e.date }} {{ e.time }} · 📍 {{ e.room }} · 座位: {{ e.seat }}
              </div>
            </div>
            <button class="text-neutral-400 hover:text-red-600 text-xs cursor-pointer p-1" @click="removeCustomExam(e.id)">
              删除
            </button>
          </div>

          <!-- 空状态 -->
          <div v-if="!officialExams.length && !customExams.length && !examsLoading" class="text-center py-10 text-neutral-400">
            暂无考试安排，期末考试排考通常于考前 1-2 周公布，点击上方可同步教务或添加自定义考试
          </div>
        </div>
      </div>
    </div>

    <!-- 3. 培养方案弹窗 -->
    <div v-if="activeTool === 'training'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-2xl sm:max-w-3xl rounded-xl bg-white p-5 sm:p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[88vh] flex flex-col overflow-hidden text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">培养方案与课程进度</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Curriculum Plan & Graduation Credits (By Semester)</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <!-- 密码未提供时的即时补全卡片 -->
        <div v-if="!effectivePassword" class="rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-center space-y-2.5">
          <div class="text-xs text-neutral-600">当前未保存教务密码，请输入密码以拉取培养方案各模块学分进度：</div>
          <div class="flex gap-2 max-w-xs mx-auto">
            <input
              v-model="tempPasswordInput"
              type="password"
              placeholder="教务系统登录密码"
              class="flex-1 px-3 py-1.5 border border-neutral-300 rounded text-xs bg-white focus:outline-none focus:border-neutral-900"
              @keyup.enter="submitTempPassword"
            />
            <button
              class="px-3.5 py-1.5 bg-neutral-900 text-white rounded text-xs hover:bg-neutral-800 cursor-pointer"
              @click="submitTempPassword"
            >
              确定
            </button>
          </div>
        </div>

        <!-- 控制栏与概览 -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-neutral-50/80 p-3 rounded-xl border border-neutral-100">
          <div class="space-y-0.5">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-neutral-500 font-mono text-[11px]">方案要求:</span>
              <span class="font-bold text-neutral-900 font-mono text-xs">{{ planTotalCredits }} 学分</span>
              <span class="text-neutral-400 font-mono text-[11px]">({{ trainingPlan.length }} 门课程 / {{ planSemesterGroups.length }} 个学期)</span>
            </div>
            <div v-if="filteredPlanCourses.length !== trainingPlan.length" class="text-[10px] text-blue-600 font-mono">
              当前筛选显示: {{ filteredPlanCourses.length }} 门课程
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <!-- 搜索框 -->
            <div class="relative">
              <input
                v-model="planSearchQuery"
                type="text"
                placeholder="搜索课程/代码/学院..."
                class="w-32 sm:w-38 px-2.5 py-1 text-xs border border-[#E5E5E5] rounded-lg bg-white focus:outline-none focus:border-neutral-900"
              />
              <button
                v-if="planSearchQuery"
                class="absolute right-1.5 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-700 text-[10px] cursor-pointer"
                @click="planSearchQuery = ''"
              >
                ✕
              </button>
            </div>

            <!-- 分类下拉 -->
            <select v-model="selectedPlanCategory" class="border border-[#E5E5E5] rounded-lg px-2 py-1 bg-white text-xs text-neutral-700 cursor-pointer">
              <option value="all">全部分类</option>
              <option v-for="c in planCategories" :key="c" :value="c">{{ c }}</option>
            </select>

            <!-- 全部折叠/展开 -->
            <button
              v-if="planSemesterGroups.length"
              class="px-2.5 py-1 border border-[#E5E5E5] rounded-lg hover:border-neutral-400 bg-white text-neutral-700 cursor-pointer text-xs flex items-center gap-1 transition-colors"
              @click="toggleAllTermsCollapse"
            >
              <span>{{ areAllTermsCollapsed ? '全部展开' : '全部折叠' }}</span>
            </button>

            <!-- 刷新方案 -->
            <button
              class="px-2.5 py-1 border border-[#E5E5E5] rounded-lg hover:border-neutral-400 bg-white text-neutral-700 cursor-pointer flex items-center gap-1 disabled:opacity-50 text-xs transition-colors"
              :disabled="planLoading"
              @click="fetchTrainingPlan(true)"
            >
              <span :class="{ 'animate-spin': planLoading }">🔄</span>
              <span>{{ planLoading ? '拉取中' : '刷新方案' }}</span>
            </button>
          </div>
        </div>

        <div v-if="planError" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 flex items-center justify-between">
          <span>{{ planError }}</span>
          <button class="px-2 py-0.5 bg-red-600 text-white rounded text-[11px] cursor-pointer" @click="fetchTrainingPlan(true)">重试</button>
        </div>

        <!-- 学期可折叠列表 -->
        <div class="flex-1 overflow-y-auto space-y-3 pr-0.5">
          <div v-if="planLoading && !trainingPlan.length" class="py-12 text-center text-neutral-400 space-y-2">
            <div class="inline-block animate-spin text-lg">⏳</div>
            <div>正在拉取培养方案各学期课程及学分属性...</div>
          </div>

          <div v-else-if="planSemesterGroups.length" class="space-y-3">
            <div
              v-for="group in planSemesterGroups"
              :key="group.termKey"
              class="border border-[#E5E5E5] rounded-xl overflow-hidden bg-white shadow-xs transition-all"
            >
              <!-- 学期可折叠头部 -->
              <div
                class="flex items-center justify-between px-3.5 py-2.5 bg-neutral-50/90 hover:bg-neutral-100/90 cursor-pointer select-none transition-colors"
                :class="{ 'border-b border-neutral-200/80': !isTermCollapsed(group.termKey) }"
                @click="toggleTermCollapse(group.termKey)"
              >
                <div class="flex items-center gap-2">
                  <span
                    class="inline-block text-[10px] text-neutral-400 transition-transform duration-200"
                    :class="{ 'rotate-90': !isTermCollapsed(group.termKey) }"
                  >
                    ▶
                  </span>
                  <span class="font-medium text-neutral-900 text-xs sm:text-sm font-sans">
                    {{ group.displayName }}
                  </span>
                  <span class="text-[11px] text-neutral-400 font-mono">
                    ({{ group.courseCount }} 门)
                  </span>
                </div>

                <div class="flex items-center gap-2.5">
                  <span class="text-[11px] text-neutral-600 font-mono bg-white px-2 py-0.5 rounded border border-neutral-200/70">
                    学分小计: <strong class="text-neutral-900">{{ group.totalCredits }}</strong>
                  </span>
                  <span class="text-[11px] text-neutral-400 hover:text-neutral-700">
                    {{ isTermCollapsed(group.termKey) ? '展开' : '收起' }}
                  </span>
                </div>
              </div>

              <!-- 学期课程表格（折叠时隐藏） -->
              <div v-show="!isTermCollapsed(group.termKey)" class="overflow-x-auto">
                <table class="w-full text-left text-xs font-mono">
                  <thead class="bg-[#FAFAFA] border-b border-neutral-100 text-neutral-500 text-[11px]">
                    <tr>
                      <th class="p-2.5 font-normal">课程名称</th>
                      <th class="p-2.5 font-normal">课程性质</th>
                      <th class="p-2.5 font-normal">开课单位</th>
                      <th class="p-2.5 font-normal text-right">学分 / 学时</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-neutral-100">
                    <tr
                      v-for="item in group.courses"
                      :key="item.code + item.name"
                      class="hover:bg-neutral-50/70 transition-colors"
                    >
                      <td class="p-2.5 font-sans font-medium text-neutral-900">
                        <div>{{ item.name }}</div>
                        <div class="text-[10px] text-neutral-400 font-mono">{{ item.code }}</div>
                      </td>
                      <td class="p-2.5">
                        <span
                          class="px-1.5 py-0.5 rounded text-[10px] font-sans"
                          :class="getAttributeBadgeClass(item.attribute)"
                        >
                          {{ item.attribute || '其他' }}
                        </span>
                      </td>
                      <td class="p-2.5 text-neutral-400 text-[11px]">{{ item.dept || '—' }}</td>
                      <td class="p-2.5 text-right font-medium text-neutral-900 font-mono">
                        {{ item.credit }} 分 <span class="text-neutral-400 font-normal">({{ item.hours }}h)</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div v-else-if="!planLoading" class="text-center py-10 text-neutral-400">
            {{ planSearchQuery || selectedPlanCategory !== 'all' ? '未找到符合筛选条件的课程' : '暂无培养方案数据，请点击上方“刷新方案”' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 4. 教室查询弹窗 -->
    <div v-if="activeTool === 'classroom'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] flex flex-col overflow-hidden text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">空闲教室检索</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Real-time Available Study Classrooms</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <!-- 密码未提供时的即时补全卡片 -->
        <div v-if="!effectivePassword" class="rounded-lg bg-neutral-50 border border-neutral-200 p-4 text-center space-y-2.5">
          <div class="text-xs text-neutral-600">当前未保存教务密码，请输入密码以检索实时空闲自习教室：</div>
          <div class="flex gap-2 max-w-xs mx-auto">
            <input
              v-model="tempPasswordInput"
              type="password"
              placeholder="教务系统登录密码"
              class="flex-1 px-3 py-1.5 border border-neutral-300 rounded text-xs bg-white focus:outline-none focus:border-neutral-900"
              @keyup.enter="submitTempPassword"
            />
            <button
              class="px-3.5 py-1.5 bg-neutral-900 text-white rounded text-xs hover:bg-neutral-800 cursor-pointer"
              @click="submitTempPassword"
            >
              确定
            </button>
          </div>
        </div>

        <!-- 筛选控件 -->
        <div class="space-y-3 shrink-0">
          <div class="grid grid-cols-3 gap-2">
            <div>
              <label class="block text-neutral-500 mb-1 text-xs">教学楼</label>
              <select v-model="classroomBuilding" class="w-full border border-[#E5E5E5] rounded-lg px-2 py-1.5 bg-white text-xs">
                <option value="">全部教学楼</option>
                <option value="001">第一教学楼 (一教)</option>
                <option value="003">第二教学楼 (二教)</option>
                <option value="014">学研中心</option>
              </select>
            </div>
            <div>
              <label class="block text-neutral-500 mb-1 text-xs">周次</label>
              <select v-model.number="classroomWeek" class="w-full border border-[#E5E5E5] rounded-lg px-2 py-1.5 bg-white text-xs">
                <option v-for="w in 30" :key="w" :value="w">第 {{ w }} 周 {{ w === currentSystemWeek ? '(本周)' : '' }}</option>
              </select>
            </div>
            <div>
              <label class="block text-neutral-500 mb-1 text-xs">星期</label>
              <select v-model.number="classroomDay" class="w-full border border-[#E5E5E5] rounded-lg px-2 py-1.5 bg-white text-xs">
                <option :value="1">周一</option>
                <option :value="2">周二</option>
                <option :value="3">周三</option>
                <option :value="4">周四</option>
                <option :value="5">周五</option>
                <option :value="6">周六</option>
                <option :value="7">周日</option>
              </select>
            </div>
          </div>

          <!-- 节次为单位的长条 (支持滑动或点击任意相邻节次) -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label class="text-neutral-500 text-xs font-medium">节次区间 (可点击两端或滑动任选相邻节次)</label>
              <div class="flex items-center gap-1 font-mono text-[11px]">
                <span class="text-neutral-900 font-medium bg-neutral-100 px-2 py-0.5 rounded">
                  {{ classroomStartPeriod === classroomEndPeriod ? `第 ${classroomStartPeriod} 节` : `第 ${classroomStartPeriod}-${classroomEndPeriod} 节` }}
                  <span class="text-neutral-500 font-normal ml-1">({{ selectedPeriodTimeRange }})</span>
                </span>
              </div>
            </div>

            <!-- 12 节长条 -->
            <div
              ref="periodBarRef"
              class="relative flex items-stretch h-10 bg-neutral-100/90 rounded-xl p-1 select-none touch-none border border-[#E5E5E5] cursor-pointer"
              @pointermove="handlePointerMove"
              @pointerup="handlePointerUp"
              @pointercancel="handlePointerUp"
            >
              <div
                v-for="p in 12"
                :key="p"
                class="flex-1 flex flex-col items-center justify-center transition-colors relative"
                :class="[
                  p >= classroomStartPeriod && p <= classroomEndPeriod
                    ? 'bg-neutral-900 text-white font-medium shadow-xs z-10'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-200/50',
                  p === classroomStartPeriod && p === classroomEndPeriod ? 'rounded-lg' : '',
                  p === classroomStartPeriod && p !== classroomEndPeriod ? 'rounded-l-lg' : '',
                  p === classroomEndPeriod && p !== classroomStartPeriod ? 'rounded-r-lg' : '',
                ]"
                @pointerdown="(e) => handlePointerDown(p, e)"
              >
                <span class="text-xs leading-none font-mono font-medium">{{ p }}</span>
                <span
                  class="text-[7.5px] leading-tight font-mono mt-0.5"
                  :class="p >= classroomStartPeriod && p <= classroomEndPeriod ? 'text-neutral-300' : 'text-neutral-400'"
                >
                  {{ p <= 4 ? '早' : p === 5 ? '午' : p <= 9 ? '下' : '晚' }}
                </span>
              </div>
            </div>

            <!-- 提示与常用快捷预设 -->
            <div class="flex flex-wrap items-center justify-between gap-1 text-[11px] pt-0.5">
              <div class="text-[11px] text-neutral-400">
                <span v-if="selectingAnchor !== null" class="text-amber-600 font-medium">
                  👉 已定第 {{ selectingAnchor }} 节，点击任一节次完成连段选择
                </span>
                <span v-else>
                  共选 {{ classroomEndPeriod - classroomStartPeriod + 1 }} 节连段
                </span>
              </div>

              <!-- 快捷预设按钮 -->
              <div class="flex items-center gap-1 overflow-x-auto pb-0.5">
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 1 && classroomEndPeriod === 2 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(1, 2)"
                >
                  1-2
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 3 && classroomEndPeriod === 4 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(3, 4)"
                >
                  3-4
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 1 && classroomEndPeriod === 4 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(1, 4)"
                >
                  上午(1-4)
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 6 && classroomEndPeriod === 7 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(6, 7)"
                >
                  6-7
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 8 && classroomEndPeriod === 9 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(8, 9)"
                >
                  8-9
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 6 && classroomEndPeriod === 9 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(6, 9)"
                >
                  下午(6-9)
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 10 && classroomEndPeriod === 11 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(10, 11)"
                >
                  10-11
                </button>
                <button
                  type="button"
                  class="px-1.5 py-0.5 rounded border text-[10px] cursor-pointer transition-colors"
                  :class="classroomStartPeriod === 1 && classroomEndPeriod === 12 ? 'border-neutral-900 bg-neutral-900 text-white font-medium' : 'border-[#E5E5E5] bg-white text-neutral-600 hover:border-neutral-400'"
                  @click="setPeriodPreset(1, 12)"
                >
                  全天
                </button>
              </div>
            </div>
          </div>
        </div>

        <button
          class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800 flex items-center justify-center gap-1.5 disabled:opacity-50 shrink-0"
          :disabled="classroomsLoading"
          @click="queryClassrooms"
        >
          <span :class="{ 'animate-spin': classroomsLoading }">🔍</span>
          <span>{{ classroomsLoading ? '正在检索占用表...' : '查询空闲自习教室' }}</span>
        </button>

        <div v-if="classroomsError" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 flex items-center justify-between">
          <span>{{ classroomsError }}</span>
          <button class="px-2 py-0.5 bg-red-600 text-white rounded text-[11px] cursor-pointer" @click="queryClassrooms">重试</button>
        </div>

        <!-- 教室列表主体 -->
        <div class="flex-1 overflow-y-auto space-y-2">
          <div v-if="classroomsLoading" class="py-10 text-center text-neutral-400 space-y-2">
            <div class="inline-block animate-spin text-lg">⏳</div>
            <div>正在核查所选时段教室课程占用情况...</div>
          </div>

          <div v-else-if="classroomsSearched">
            <div class="flex items-center justify-between mb-2 text-neutral-500 text-[11px]">
              <span>检索结果：</span>
              <span class="font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">共 {{ freeClassrooms.length }} 间空闲教室</span>
            </div>

            <div v-if="freeClassrooms.length" class="grid grid-cols-2 gap-2">
              <div
                v-for="r in freeClassrooms"
                :key="r.name"
                class="p-2.5 border border-[#E5E5E5] rounded-lg bg-[#FAFAFA] flex items-center justify-between hover:border-neutral-400 transition-colors"
              >
                <div class="flex items-center gap-1.5">
                  <span class="font-medium text-neutral-900 text-xs">{{ r.name }}</span>
                  <span class="text-[9px] px-1.5 py-0.5 rounded bg-neutral-200 text-neutral-600 font-sans">
                    {{ getBuildingTag(r) }}
                  </span>
                </div>
                <span class="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-[10px] font-medium shrink-0">空闲</span>
              </div>
            </div>

            <div v-else class="text-center py-10 text-neutral-400">
              该时段该教学楼暂无完全空闲教室，建议尝试其它节次或教学楼
            </div>
          </div>

          <div v-else class="text-center py-10 text-neutral-400">
            选择教学楼与时段后，点击上方按钮开始查询
          </div>
        </div>

      </div>
    </div>

    <!-- 5. 自动评教弹窗 -->
    <div v-if="activeTool === 'autoeval'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">自动评教</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Course Evaluation Automation</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-neutral-500 mb-1">默认评级</label>
            <select class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white">
              <option>全五星满分好评 (推荐)</option>
              <option>优秀 / 良好混合</option>
            </select>
          </div>
          <div>
            <label class="block text-neutral-500 mb-1">评语风格</label>
            <select class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white">
              <option>严谨认真、教学清晰、受益匪浅</option>
              <option>生动形象、互动积极、非常喜欢</option>
              <option>随机多样化评语</option>
            </select>
          </div>
        </div>

        <button class="w-full py-2.5 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="showAlert('自动评教脚本对接中')">
          开始自动评教
        </button>
      </div>
    </div>

    <!-- 6. 共享课表 / 好友列表弹窗 (4位邀请码系统) -->
    <div v-if="activeTool === 'share_friends'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">共享课表与好友</h3>
            <p class="text-[11px] text-neutral-400 font-mono">4-Digit Invite Code Schedule Sharing</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer text-sm" @click="activeTool = 'none'">✕</button>
        </div>

        <!-- 隐私保护提示 -->
        <div class="p-2.5 rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-800 text-[11px] flex items-start gap-2">
          <span class="text-emerald-600 font-bold shrink-0 mt-0.5">🔒</span>
          <span>专属4位邀请码系统：不公开、不绑定真实学号，好友凭邀请码即可安全查看共享课表。</span>
        </div>

        <!-- 模块一：我的课表邀请码 -->
        <div class="p-3.5 border border-[#E5E5E5] rounded-xl bg-[#FAFAFA] space-y-3">
          <div class="flex items-center justify-between">
            <span class="font-medium text-neutral-800">我的共享邀请码</span>
            <span v-if="myShareCode" class="text-[10px] text-neutral-400 font-mono">Code: {{ myShareCode }}</span>
          </div>

          <div v-if="myShareCode" class="space-y-2.5">
            <div class="flex items-center justify-between bg-white border border-[#E5E5E5] rounded-lg p-2.5">
              <div>
                <div class="text-[10px] text-neutral-400">专属 4 位课表邀请码</div>
                <div class="font-mono text-xl font-bold tracking-widest text-neutral-900">{{ myShareCode }}</div>
              </div>
              <div class="flex items-center gap-1.5">
                <button
                  type="button"
                  class="px-2.5 py-1.5 rounded-lg border border-[#E5E5E5] hover:border-neutral-400 text-neutral-700 text-xs cursor-pointer transition-colors"
                  @click="copyShareCodeOnly"
                >
                  仅复制码
                </button>
                <button
                  type="button"
                  class="px-3 py-1.5 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-white font-medium text-xs cursor-pointer transition-colors"
                  @click="copyShareLink"
                >
                  {{ copySuccess ? '已复制！' : '复制分享链接' }}
                </button>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <input
                v-model="myOwnerName"
                placeholder="我的展示昵称 (例如: 小张)"
                class="flex-1 border border-[#E5E5E5] rounded-lg px-2.5 py-1.5 bg-white text-xs"
              />
              <button
                type="button"
                class="px-3 py-1.5 border border-[#E5E5E5] hover:border-neutral-400 rounded-lg text-neutral-600 text-xs cursor-pointer transition-colors whitespace-nowrap"
                :disabled="isGeneratingCode"
                @click="createOrRegenerateCode(false)"
              >
                保存昵称
              </button>
              <button
                type="button"
                class="px-2.5 py-1.5 border border-red-200 text-red-600 hover:bg-red-50 rounded-lg text-xs cursor-pointer transition-colors whitespace-nowrap"
                :disabled="isGeneratingCode"
                @click="createOrRegenerateCode(true)"
              >
                重新生成
              </button>
            </div>
          </div>

          <div v-else class="text-center py-2 space-y-2">
            <p class="text-neutral-500 text-[11px]">
              生成专属 4 位邀请码后，朋友只需输入这 4 位码或打开链接即可查看您的课表。
            </p>
            <button
              type="button"
              class="w-full py-2 bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 cursor-pointer font-medium transition-colors"
              :disabled="isGeneratingCode"
              @click="createOrRegenerateCode(false)"
            >
              {{ isGeneratingCode ? '正在生成邀请码...' : '一键生成我的 4 位共享邀请码' }}
            </button>
          </div>

          <div v-if="shareError" class="text-red-500 text-[11px]">{{ shareError }}</div>
        </div>

        <!-- 模块二：输入好友邀请码绑定 -->
        <div class="p-3.5 border border-[#E5E5E5] rounded-xl bg-white space-y-2.5">
          <span class="font-medium text-neutral-800">绑定好友的共享课表</span>
          <div class="grid grid-cols-2 gap-2">
            <input
              v-model="inputFriendCode"
              placeholder="4位邀请码 (如 8K2M)"
              maxlength="4"
              class="border border-[#E5E5E5] rounded-lg px-2.5 py-1.5 bg-white uppercase font-mono text-center font-bold tracking-widest text-xs"
              @input="inputFriendCode = inputFriendCode.toUpperCase()"
            />
            <input
              v-model="inputFriendName"
              placeholder="好友备注 (选填)"
              class="border border-[#E5E5E5] rounded-lg px-2.5 py-1.5 bg-white text-xs"
            />
          </div>

          <div v-if="addFriendError" class="text-red-500 text-[11px]">{{ addFriendError }}</div>

          <button
            type="button"
            class="w-full py-2 bg-neutral-900 text-white rounded-lg cursor-pointer hover:bg-neutral-800 font-medium transition-colors disabled:opacity-50"
            :disabled="isAddingFriend"
            @click="addFriendByCode"
          >
            {{ isAddingFriend ? '正在校验邀请码...' : '+ 导入并绑定好友课表' }}
          </button>
        </div>

        <!-- 模块三：已绑定的好友列表 -->
        <div class="space-y-2">
          <div class="flex items-center justify-between text-neutral-500 text-[11px]">
            <span>已保存的好友课表：</span>
            <span>共 {{ sharedFriends.length }} 位</span>
          </div>

          <div class="divide-y divide-neutral-100 border border-[#E5E5E5] rounded-xl overflow-hidden bg-white">
            <div v-if="!sharedFriends.length" class="text-center py-6 text-neutral-400">
              暂无已绑定的好友，输入好友的 4 位邀请码即可一键添加
            </div>
            <div
              v-for="(f, idx) in sharedFriends"
              :key="f.code"
              class="flex items-center justify-between p-3 bg-white hover:bg-neutral-50/60 transition-colors"
            >
              <div>
                <div class="font-medium text-neutral-900 flex items-center gap-1.5">
                  <span>{{ f.name }}</span>
                  <span class="font-mono text-[9px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600">
                    码: {{ f.code }}
                  </span>
                </div>
                <div class="text-[10px] text-neutral-400 font-mono mt-0.5">
                  {{ f.semester ? `${f.semester} · ` : '' }}{{ f.coursesCount ? `${f.coursesCount} 门课` : '可查看' }}
                </div>
              </div>
              <div class="flex items-center gap-2">
                <a
                  :href="`/schedule?code=${f.code}`"
                  target="_blank"
                  class="text-neutral-900 hover:text-black font-medium underline text-xs"
                >
                  查看课表 →
                </a>
                <button
                  type="button"
                  class="text-neutral-300 hover:text-red-600 cursor-pointer p-1 transition-colors"
                  title="移除好友"
                  @click="removeFriend(idx)"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 7. 寻找共同空闲时间弹窗 -->
    <div v-if="activeTool === 'common_free'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">寻找共同空闲时间</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Find Mutual Free Periods</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <p class="text-neutral-500 leading-relaxed">
          自动比对多位同学的课表，找出每周没课的共同空闲节次，方便聚餐、约自习或小组开会讨论。
        </p>

        <div class="border border-[#E5E5E5] rounded-lg p-3 bg-[#FAFAFA] space-y-2">
          <div class="font-medium text-neutral-800">推荐本周空闲时段：</div>
          <div class="text-neutral-600">· 周三 下午 6-7 节 (13:30 - 15:05)</div>
          <div class="text-neutral-600">· 周五 下午 8-9 节 (15:20 - 16:55)</div>
          <div class="text-neutral-600">· 周日 全天无课</div>
        </div>

        <button class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="showAlert('多好友协同交叉比对脚本对接中')">
          开始多维空闲比对
        </button>
      </div>
    </div>

    <!-- 8. 设置课表背景 (纯前端完全可用) -->
    <div v-if="activeTool === 'background'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">设置课表背景</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Custom Timetable Background</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-neutral-600 mb-1">图片地址 (URL) 或上传本地图片</label>
            <input v-model="bgUrl" placeholder="https://example.com/wallpaper.jpg" class="w-full border border-[#E5E5E5] rounded px-3 py-2 bg-white text-xs" />
            <div class="mt-2">
              <input type="file" accept="image/*" class="text-xs text-neutral-500" @change="handleFileUpload" />
            </div>
          </div>

          <div>
            <div class="flex justify-between text-neutral-600 mb-1">
              <span>背景不透明度:</span>
              <span class="font-mono">{{ bgOpacity }}%</span>
            </div>
            <input v-model.number="bgOpacity" type="range" min="5" max="100" class="w-full accent-neutral-900" />
          </div>

          <div>
            <div class="flex justify-between text-neutral-600 mb-1">
              <span>高斯模糊度:</span>
              <span class="font-mono">{{ bgBlur }}px</span>
            </div>
            <input v-model.number="bgBlur" type="range" min="0" max="20" class="w-full accent-neutral-900" />
          </div>

          <div class="flex gap-2 pt-2">
            <button class="flex-1 py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="saveBg">
              应用背景
            </button>
            <button class="px-4 py-2 border border-[#E5E5E5] text-neutral-600 rounded cursor-pointer hover:border-neutral-400" @click="clearBg">
              清除背景
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 9. 外观设置 -->
    <div v-if="activeTool === 'appearance'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">外观设置</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Appearance & Display Preferences</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="space-y-4">
          <!-- 主题模式 -->
          <div>
            <label class="block text-neutral-600 mb-1.5 font-medium">主题模式</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                class="py-2 border rounded-lg text-center cursor-pointer transition-colors"
                :class="themeMode === 'auto' ? 'border-neutral-900 bg-neutral-900 text-white font-medium shadow-xs' : 'border-[#E5E5E5] text-neutral-700 hover:border-neutral-400'"
                @click="onThemeChange('auto')"
              >
                跟随系统
              </button>
              <button
                class="py-2 border rounded-lg text-center cursor-pointer transition-colors"
                :class="themeMode === 'light' ? 'border-neutral-900 bg-neutral-900 text-white font-medium shadow-xs' : 'border-[#E5E5E5] text-neutral-700 hover:border-neutral-400'"
                @click="onThemeChange('light')"
              >
                浅色模式
              </button>
              <button
                class="py-2 border rounded-lg text-center cursor-pointer transition-colors"
                :class="themeMode === 'dark' ? 'border-neutral-900 bg-neutral-900 text-white font-medium shadow-xs' : 'border-[#E5E5E5] text-neutral-700 hover:border-neutral-400'"
                @click="onThemeChange('dark')"
              >
                深色模式
              </button>
            </div>
          </div>

          <!-- 课表显示周末 -->
          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-xl cursor-pointer hover:bg-neutral-50/50 transition-colors">
            <div>
              <div class="font-medium text-neutral-800">显示周末 (周六与周日)</div>
              <div class="text-[10px] text-neutral-400">关闭后仅显示周一至周五 5 天，视图更宽敞</div>
            </div>
            <input
              v-model="showWeekend"
              type="checkbox"
              class="h-4 w-4 accent-neutral-900 cursor-pointer"
              @change="onWeekendChange"
            />
          </label>

          <!-- 彩色课程卡片 -->
          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-xl cursor-pointer hover:bg-neutral-50/50 transition-colors">
            <div>
              <div class="font-medium text-neutral-800">多彩课程卡片</div>
              <div class="text-[10px] text-neutral-400">为不同课程分配不同优雅莫兰迪配色，便于区分识别</div>
            </div>
            <input
              v-model="colorfulCards"
              type="checkbox"
              class="h-4 w-4 accent-neutral-900 cursor-pointer"
              @change="onColorfulChange"
            />
          </label>

          <!-- 课程时间显示 -->
          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-xl cursor-pointer hover:bg-neutral-50/50 transition-colors">
            <div>
              <div class="font-medium text-neutral-800">卡片内显示具体节次时间</div>
              <div class="text-[10px] text-neutral-400">在课程方块内直接展示如 08:00 - 09:35</div>
            </div>
            <input
              v-model="showCourseTime"
              type="checkbox"
              class="h-4 w-4 accent-neutral-900 cursor-pointer"
              @change="onCourseTimeChange"
            />
          </label>

          <button class="w-full py-2.5 bg-neutral-900 text-white rounded-lg cursor-pointer hover:bg-neutral-800 font-medium transition-colors" @click="saveAppearance">
            完成并保存偏好
          </button>
        </div>
      </div>
    </div>

    <!-- 10. 导出课表 (纯前端完全可用) -->
    <div v-if="activeTool === 'export_ics'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">导出课表</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Export Calendar (.ics)</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <p class="text-neutral-500 leading-relaxed">
          导出的标准 .ics 日历文件可一键导入到 iOS 日历、华为日历、小米日历、Outlook 或 Google Calendar 中，支持上课前闹钟推送提醒。
        </p>

        <div class="space-y-3">
          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-lg cursor-pointer">
            <div>
              <div class="font-medium text-neutral-900">学期课程</div>
              <div class="text-[11px] text-neutral-400">包含当前学期每周安排课程</div>
            </div>
            <input type="checkbox" checked disabled class="h-4 w-4 accent-neutral-900" />
          </label>

          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-lg cursor-pointer">
            <div>
              <div class="font-medium text-neutral-900">考试日程</div>
              <div class="text-[11px] text-neutral-400">包含已记录的期末与自定义考试</div>
            </div>
            <input v-model="exportIncludeExams" type="checkbox" class="h-4 w-4 accent-neutral-900" />
          </label>
        </div>

        <button class="w-full py-2.5 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800 flex items-center justify-center gap-1.5" @click="downloadICS">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span>下载 .ics 日历文件</span>
        </button>
      </div>
    </div>

    <!-- 11. 成绩出分监控设置 -->
    <div v-if="activeTool === 'grade_monitor'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">成绩出分监控</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Grade Release Alert & Notification</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <p class="text-neutral-500 leading-relaxed">
          期末出分季开启后，系统将在后台自动定期检测教务新出分数，并在第一时间向指定邮箱发送提醒。
        </p>

        <div class="space-y-3">
          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-lg cursor-pointer">
            <span class="text-neutral-800 font-medium">开启成绩出分监控</span>
            <input v-model="monitorEnabled" type="checkbox" class="h-4 w-4 accent-neutral-900" />
          </label>

          <div>
            <label class="block text-neutral-500 mb-1">接收通知邮箱</label>
            <input v-model="monitorEmail" placeholder="your_email@domain.com" class="w-full border border-[#E5E5E5] rounded px-3 py-2 bg-white" />
          </div>
        </div>

        <button class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="saveMonitor">
          保存监控设置
        </button>
      </div>
    </div>

  </div>
</template>
