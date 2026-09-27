export interface Course {
  name: string
  day: 1 | 2 | 3 | 4 | 5 | 6 | 7
  start: number
  end: number
  location: string
  teacher?: string
}

export interface Schedule {
  title: string
  weeks: string
  courses: Course[]
}

/** 个人课表（模拟数据） */
export const schedule: Schedule = {
  title: '个人课表',
  weeks: '2026 秋季学期',
  courses: [
    { name: '大学语文', day: 1, start: 3, end: 4, location: '一教213', teacher: '盖琳' },
    { name: '高等数学', day: 1, start: 5, end: 6, location: '二教305', teacher: '王明' },
    { name: '大学物理', day: 2, start: 1, end: 2, location: '理科楼210', teacher: '李华' },
    { name: '电路分析', day: 2, start: 3, end: 4, location: '实验楼B302', teacher: '张伟' },
    { name: '大学英语', day: 3, start: 1, end: 2, location: '外语楼101', teacher: 'Sarah' },
    { name: '程序设计', day: 3, start: 3, end: 4, location: '机房305', teacher: '陈立' },
    { name: '体育', day: 4, start: 5, end: 6, location: '田径场', teacher: '刘洋' },
    { name: '数字电子技术', day: 5, start: 1, end: 2, location: '实验楼B201', teacher: '赵强' },
    { name: '信号与系统', day: 5, start: 3, end: 4, location: '理科楼305', teacher: '孙丽' },
  ],
}

export const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/** 一天的节次（可按需扩展） */
export const periodSlots = [
  { start: 1, end: 2 },
  { start: 3, end: 4 },
  { start: 5, end: 6 },
  { start: 7, end: 8 },
]
