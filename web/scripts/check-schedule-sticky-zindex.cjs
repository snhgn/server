#!/usr/bin/env node
/**
 * check-schedule-sticky-zindex.cjs
 *
 * 常驻静态检查：课表页“吸顶节次时间列”与“课程卡片”的层级不变量。
 *
 * 背景（2026-10-12 修复）：
 *   课表格横向滚动时（移动端整周视图会自动 scrollToToday 横滑到当天），
 *   课程卡片会滑过吸顶的“节次/时间”列。若卡片 z-index >= 吸顶列 z-index，
 *   卡片就会盖住时间（修复前两者都是 z-10，卡片在 DOM 中更靠后 → 画在时间上面）。
 *
 * 不变量：
 *   1. 每个 `sticky left-0 z-*` 吸顶单元格，其 z-index 必须严格大于
 *      课程卡片冲突堆叠的最大 z-index；
 *   2. 卡片堆叠 z-index 表达式 `10 + Math.min(c.stackIndex, K)` 的上限
 *      (10 + K) 必须严格小于最小吸顶 z-index。
 *
 * 用法：node check-schedule-sticky-zindex.cjs [ScheduleView.vue 路径]
 * 退出码：0 = 通过；1 = 发现违反不变量的问题
 */

const fs = require('fs')
const path = require('path')

const target = process.argv[2] || path.join(__dirname, '..', 'src', 'views', 'ScheduleView.vue')

if (!fs.existsSync(target)) {
  console.error(`[FAIL] 找不到文件: ${target}`)
  process.exit(1)
}

const src = fs.readFileSync(target, 'utf8')
const problems = []

// ---- 1. 收集吸顶单元格的 z-index（sticky left-0 z-<n>）----
const stickyZ = []
const stickyRe = /class="[^"]*\bsticky\s+left-0\s+z-(\d+)\b[^"]*"/g
let m
while ((m = stickyRe.exec(src)) !== null) {
  const line = src.slice(0, m.index).split('\n').length
  stickyZ.push({ z: Number(m[1]), line })
}
if (stickyZ.length === 0) {
  problems.push('未找到任何 `sticky left-0 z-*` 吸顶单元格（课表时间列应吸顶且带 z-index）')
}

// ---- 2. 解析课程卡片冲突堆叠的 z-index 上限 ----
// 形如: zIndex: 10 + Math.min(c.stackIndex, 19),
const stackRe = /zIndex:\s*(\d+)\s*\+\s*Math\.min\(\s*c\.stackIndex\s*,\s*(\d+)\s*\)/g
const stackCaps = []
while ((m = stackRe.exec(src)) !== null) {
  const line = src.slice(0, m.index).split('\n').length
  stackCaps.push({ base: Number(m[1]), cap: Number(m[2]), max: Number(m[1]) + Number(m[2]), line })
}
if (stackCaps.length === 0) {
  problems.push('未找到卡片堆叠 z-index 表达式 `zIndex: 10 + Math.min(c.stackIndex, K)`（应存在且有上限）')
}

const minSticky = stickyZ.length ? Math.min(...stickyZ.map((s) => s.z)) : Infinity
const maxCard = stackCaps.length ? Math.max(...stackCaps.map((s) => s.max)) : -Infinity

for (const s of stickyZ) {
  if (s.z <= maxCard) {
    problems.push(
      `L${s.line}: 吸顶单元格 z-${s.z} 不高于卡片堆叠上限 z-${maxCard}，横滑时卡片会盖住节次时间`
    )
  }
}

// ---- 3. 报告 ----
console.log(`[check-schedule-sticky-zindex] ${target}`)
console.log(`  吸顶节次时间列 z-index: ${stickyZ.map((s) => `z-${s.z}(L${s.line})`).join(', ') || '无'}`)
console.log(`  课程卡片堆叠 z-index 上限: ${stackCaps.map((s) => `z-${s.max}(L${s.line})`).join(', ') || '无'}`)

if (problems.length > 0) {
  console.error(`\n[FAIL] 发现 ${problems.length} 个层级问题：`)
  for (const p of problems) console.error('  - ' + p)
  process.exit(1)
}

console.log(`\n[PASS] 吸顶时间列 (min z-${minSticky}) 始终位于课程卡片 (max z-${maxCard}) 之上，横滑不会遮挡时间`)
process.exit(0)
