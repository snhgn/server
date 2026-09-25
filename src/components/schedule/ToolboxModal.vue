<script setup lang="ts">
import { ref } from 'vue'

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
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'openCalendar'): void
  (e: 'logout'): void
  (e: 'updateBg', bg: { url: string; opacity: number; blur: number }): void
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
const themeMode = ref(localStorage.getItem('bjfu-theme-mode') || 'auto')

function saveAppearance() {
  localStorage.setItem('bjfu-show-weekend', String(showWeekend.value))
  localStorage.setItem('bjfu-theme-mode', themeMode.value)
  activeTool.value = 'none'
}

// ================= 自定义考试 =================
interface CustomExam {
  id: string
  name: string
  date: string
  time: string
  room: string
  seat: string
}
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

// ================= 导出 ICS 日历 (纯前端完全可用) =================
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

  // 考试导出
  if (exportIncludeExams.value) {
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

// ================= 好友与共享 =================
interface Friend {
  name: string
  studentId: string
}
const friends = ref<Friend[]>([])
try {
  friends.value = JSON.parse(localStorage.getItem('bjfu-friends') || '[]')
} catch {}
const newFriendName = ref('')
const newFriendId = ref('')

function addFriend() {
  if (!newFriendName.value.trim() || !newFriendId.value.trim()) {
    showAlert('请填写好友姓名和学号')
    return
  }
  friends.value.push({
    name: newFriendName.value.trim(),
    studentId: newFriendId.value.trim(),
  })
  localStorage.setItem('bjfu-friends', JSON.stringify(friends.value))
  newFriendName.value = ''
  newFriendId.value = ''
}

function removeFriend(idx: number) {
  friends.value.splice(idx, 1)
  localStorage.setItem('bjfu-friends', JSON.stringify(friends.value))
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
      <div class="w-full max-w-xl rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">成绩查询</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Academic Grades & GPA Analysis</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="rounded-lg bg-amber-50/70 border border-amber-200/60 p-3 text-[11px] text-amber-800 flex items-center justify-between">
          <span>提示：教务成绩抓取接口开发中，已预留数据表结构与查询界面。</span>
          <button class="px-2.5 py-1 bg-amber-600 text-white rounded text-[11px] cursor-pointer hover:bg-amber-700">刷新成绩</button>
        </div>

        <div class="grid grid-cols-3 gap-3 font-mono text-center">
          <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-3">
            <div class="text-xs text-neutral-400">平均绩点 (GPA)</div>
            <div class="text-xl font-bold text-neutral-900 mt-1">3.68</div>
          </div>
          <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-3">
            <div class="text-xs text-neutral-400">加权平均分</div>
            <div class="text-xl font-bold text-neutral-900 mt-1">87.5</div>
          </div>
          <div class="rounded-lg border border-neutral-100 bg-[#FAFAFA] p-3">
            <div class="text-xs text-neutral-400">已修总学分</div>
            <div class="text-xl font-bold text-neutral-900 mt-1">42.5</div>
          </div>
        </div>

        <div class="border border-[#E5E5E5] rounded-lg overflow-hidden">
          <table class="w-full text-left text-xs font-mono">
            <thead class="bg-[#FAFAFA] border-b border-[#E5E5E5] text-neutral-500">
              <tr>
                <th class="p-2.5 font-normal">课程名称</th>
                <th class="p-2.5 font-normal">性质</th>
                <th class="p-2.5 font-normal">学分</th>
                <th class="p-2.5 font-normal">成绩</th>
                <th class="p-2.5 font-normal">绩点</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-neutral-100">
              <tr>
                <td class="p-2.5 font-sans font-medium text-neutral-900">高等数学 A1</td>
                <td class="p-2.5 text-neutral-500">必修</td>
                <td class="p-2.5">5.0</td>
                <td class="p-2.5 font-semibold text-neutral-900">92</td>
                <td class="p-2.5">4.0</td>
              </tr>
              <tr>
                <td class="p-2.5 font-sans font-medium text-neutral-900">大学物理 B1</td>
                <td class="p-2.5 text-neutral-500">必修</td>
                <td class="p-2.5">4.0</td>
                <td class="p-2.5 font-semibold text-neutral-900">88</td>
                <td class="p-2.5">3.7</td>
              </tr>
              <tr>
                <td class="p-2.5 font-sans font-medium text-neutral-900">C语言程序设计</td>
                <td class="p-2.5 text-neutral-500">必修</td>
                <td class="p-2.5">3.5</td>
                <td class="p-2.5 font-semibold text-neutral-900">95</td>
                <td class="p-2.5">4.0</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 2. 考试安排弹窗 -->
    <div v-if="activeTool === 'exams'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">考试安排</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Exam Schedule & Countdown</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="flex items-center justify-between">
          <span class="text-xs text-neutral-500">当前学期考试日程</span>
          <button
            class="px-2.5 py-1 text-xs border border-[#E5E5E5] rounded hover:border-neutral-400 bg-white cursor-pointer"
            @click="showAddExamForm = !showAddExamForm"
          >
            {{ showAddExamForm ? '收起表单' : '+ 添加自定义考试' }}
          </button>
        </div>

        <!-- 添加考试表单 -->
        <div v-if="showAddExamForm" class="p-4 border border-[#E5E5E5] rounded-lg bg-[#FAFAFA] space-y-3 text-xs">
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

        <!-- 考试列表 -->
        <div class="space-y-2">
          <div v-if="!customExams.length" class="text-center py-8 text-neutral-400 text-xs">
            暂无考试安排，点击上方按钮可手动添加或等待教务脚本上线自动拉取
          </div>
          <div
            v-for="e in customExams"
            :key="e.id"
            class="flex items-center justify-between p-3.5 border border-[#E5E5E5] rounded-lg bg-[#FAFAFA]"
          >
            <div>
              <div class="font-medium text-neutral-900 text-sm font-sans">{{ e.name }}</div>
              <div class="text-xs text-neutral-500 mt-1 font-mono">
                {{ e.date }} · {{ e.time }} · {{ e.room }} · 座位: {{ e.seat }}
              </div>
            </div>
            <button class="text-neutral-400 hover:text-red-600 text-xs cursor-pointer p-1" @click="removeCustomExam(e.id)">
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. 培养方案弹窗 -->
    <div v-if="activeTool === 'training'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">培养方案</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Curriculum & Graduation Requirements</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="space-y-3 text-xs">
          <div>
            <div class="flex justify-between text-neutral-600 mb-1">
              <span>通识必修课</span>
              <span class="font-mono">24 / 28 学分 (85%)</span>
            </div>
            <div class="w-full bg-neutral-100 rounded-full h-2">
              <div class="bg-neutral-900 h-2 rounded-full" style="width: 85%" />
            </div>
          </div>

          <div>
            <div class="flex justify-between text-neutral-600 mb-1">
              <span>学科基础课</span>
              <span class="font-mono">18 / 22 学分 (81%)</span>
            </div>
            <div class="w-full bg-neutral-100 rounded-full h-2">
              <div class="bg-neutral-900 h-2 rounded-full" style="width: 81%" />
            </div>
          </div>

          <div>
            <div class="flex justify-between text-neutral-600 mb-1">
              <span>专业核心课</span>
              <span class="font-mono">28 / 36 学分 (77%)</span>
            </div>
            <div class="w-full bg-neutral-100 rounded-full h-2">
              <div class="bg-neutral-900 h-2 rounded-full" style="width: 77%" />
            </div>
          </div>

          <div>
            <div class="flex justify-between text-neutral-600 mb-1">
              <span>专业选修课与实践</span>
              <span class="font-mono">12 / 16 学分 (75%)</span>
            </div>
            <div class="w-full bg-neutral-100 rounded-full h-2">
              <div class="bg-neutral-900 h-2 rounded-full" style="width: 75%" />
            </div>
          </div>
        </div>

        <div class="pt-3 border-t border-neutral-100 flex justify-end">
          <button class="px-3 py-1.5 border border-[#E5E5E5] rounded text-xs hover:border-neutral-400 cursor-pointer" @click="showAlert('培养方案刷新脚本对接中')">
            刷新培养方案
          </button>
        </div>
      </div>
    </div>

    <!-- 4. 教室查询弹窗 -->
    <div v-if="activeTool === 'classroom'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">空闲教室查询</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Available Study Classrooms</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-neutral-500 mb-1">校区</label>
            <select class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white">
              <option>学院路主校区</option>
              <option>学清路校区</option>
            </select>
          </div>
          <div>
            <label class="block text-neutral-500 mb-1">教学楼</label>
            <select class="w-full border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white">
              <option>第二教学楼</option>
              <option>第一教学楼</option>
              <option>学研中心</option>
              <option>主楼</option>
            </select>
          </div>
        </div>

        <button class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="showAlert('教室实时占用抓取脚本对接中')">
          查询空闲教室
        </button>

        <div class="border border-[#E5E5E5] rounded-lg p-3 bg-[#FAFAFA] space-y-2">
          <div class="flex justify-between items-center text-neutral-800">
            <span class="font-medium">二教 203 (120 座)</span>
            <span class="text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded text-[11px]">当前空闲</span>
          </div>
          <div class="flex justify-between items-center text-neutral-800">
            <span class="font-medium">二教 305 (80 座)</span>
            <span class="text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded text-[11px]">当前空闲</span>
          </div>
          <div class="flex justify-between items-center text-neutral-800">
            <span class="font-medium">学研 A0201 (200 座)</span>
            <span class="text-amber-600 bg-amber-50 px-2 py-0.5 rounded text-[11px]">下节有课</span>
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

    <!-- 6. 共享课表 / 好友列表弹窗 -->
    <div v-if="activeTool === 'share_friends'" class="fixed inset-0 z-60 flex items-center justify-center bg-black/50 p-4" @click.self="activeTool = 'none'">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl border border-[#E5E5E5] space-y-4 max-h-[85vh] overflow-y-auto text-xs">
        <div class="flex items-center justify-between border-b border-neutral-100 pb-3">
          <div>
            <h3 class="text-base font-medium text-neutral-900 font-sans">好友与共享课表</h3>
            <p class="text-[11px] text-neutral-400 font-mono">Friend Timetables & Binding</p>
          </div>
          <button class="text-neutral-400 hover:text-neutral-900 cursor-pointer" @click="activeTool = 'none'">✕</button>
        </div>

        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-2">
            <input v-model="newFriendName" placeholder="好友备注 (例如: 张三)" class="border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
            <input v-model="newFriendId" placeholder="好友学号" class="border border-[#E5E5E5] rounded px-2.5 py-1.5 bg-white" />
          </div>
          <button class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="addFriend">
            + 添加好友绑定
          </button>
        </div>

        <div class="divide-y divide-neutral-100 border border-[#E5E5E5] rounded-lg">
          <div v-if="!friends.length" class="text-center py-6 text-neutral-400">
            暂无已绑定的好友
          </div>
          <div v-for="(f, idx) in friends" :key="f.studentId" class="flex items-center justify-between p-3 bg-white">
            <div>
              <span class="font-medium text-neutral-900">{{ f.name }}</span>
              <span class="font-mono text-neutral-400 text-[11px] ml-2">({{ f.studentId }})</span>
            </div>
            <div class="flex items-center gap-2">
              <a :href="`/schedule?user=${f.studentId}`" target="_blank" class="text-neutral-600 hover:text-neutral-950 underline">
                查看课表 →
              </a>
              <button class="text-neutral-400 hover:text-red-600 cursor-pointer" @click="removeFriend(idx)">
                ✕
              </button>
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
          <div>
            <label class="block text-neutral-600 mb-1.5">主题模式</label>
            <div class="grid grid-cols-3 gap-2">
              <button
                class="py-2 border rounded text-center cursor-pointer transition-colors"
                :class="themeMode === 'auto' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-[#E5E5E5] text-neutral-700'"
                @click="themeMode = 'auto'"
              >
                跟随系统
              </button>
              <button
                class="py-2 border rounded text-center cursor-pointer transition-colors"
                :class="themeMode === 'light' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-[#E5E5E5] text-neutral-700'"
                @click="themeMode = 'light'"
              >
                浅色模式
              </button>
              <button
                class="py-2 border rounded text-center cursor-pointer transition-colors"
                :class="themeMode === 'dark' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-[#E5E5E5] text-neutral-700'"
                @click="themeMode = 'dark'"
              >
                深色模式
              </button>
            </div>
          </div>

          <label class="flex items-center justify-between p-3 border border-[#E5E5E5] rounded-lg cursor-pointer">
            <span class="text-neutral-800">课表显示周末 (周六与周日)</span>
            <input v-model="showWeekend" type="checkbox" class="h-4 w-4 accent-neutral-900" />
          </label>

          <button class="w-full py-2 bg-neutral-900 text-white rounded cursor-pointer hover:bg-neutral-800" @click="saveAppearance">
            保存外观偏好
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
