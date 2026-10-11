/**
 * 复现脚本：检查 views/*.vue 中 onMounted 回调里是否存在「提前 return 跳过后续注册」。
 *
 * 做法（纯静态、括号感知）：
 *   1. 定位 onMounted(...) 回调体
 *   2. 在回调体的**顶层**（大括号深度 == 1）扫描语句首 token
 *   3. 若存在顶层 return，且其行号早于某些副作用注册（setInterval / addEventListener），
 *      则这些副作用在正常路径下永远不会执行。
 */
const fs = require('fs')
const path = require('path')

const file = process.argv[2]
const src = fs.readFileSync(file, 'utf8')
const lines = src.split(/\r?\n/)

function lineOf(idx) {
  return src.slice(0, idx).split(/\r?\n/).length
}

// 扫描器：跳过字符串/模板串/注释，返回某开括号的匹配闭括号索引
function matchClose(text, openIdx) {
  const pairs = { '(': ')', '[': ']', '{': '}' }
  const open = text[openIdx]
  const close = pairs[open]
  const stack = [close]
  let i = openIdx + 1
  while (i < text.length) {
    const ch = text[i]
    if (ch === '"' || ch === "'" || ch === '`') {
      i = skipString(text, i)
      continue
    }
    if (ch === '/' && text[i + 1] === '/') {
      const nl = text.indexOf('\n', i)
      i = nl === -1 ? text.length : nl
      continue
    }
    if (ch === '/' && text[i + 1] === '*') {
      const end = text.indexOf('*/', i + 2)
      i = end === -1 ? text.length : end + 2
      continue
    }
    if (ch === '(' || ch === '[' || ch === '{') {
      stack.push(pairs[ch])
    } else if (ch === ')' || ch === ']' || ch === '}') {
      stack.pop()
      if (stack.length === 0) return i
    }
    i++
  }
  return -1
}

function skipString(text, i) {
  const quote = text[i]
  i++
  while (i < text.length) {
    if (text[i] === '\\') { i += 2; continue }
    if (text[i] === quote) return i + 1
    i++
  }
  return i
}

let found = false
let searchFrom = 0
while (true) {
  const at = src.indexOf('onMounted(', searchFrom)
  if (at === -1) break
  const open = src.indexOf('(', at)
  const close = matchClose(src, open)
  if (close === -1) break
  const bodyStart = src.indexOf('{', open)   // 回调体 '{'
  const bodyEnd = matchClose(src, bodyStart)
  const body = src.slice(bodyStart + 1, bodyEnd)

  const bodyStartLine = lineOf(bodyStart)
  const bodyEndLine = lineOf(bodyEnd)

  // 扫描 body：找出「不在嵌套函数定义内」的 return 语句所在行
  // （async 回调里任何一层块的 return 都会终止整个回调）
  const topReturns = []
  const sideEffects = []
  let fnDepth = -1 // 进入回调体本身算 0
  let i = 0
  while (i < body.length) {
    const ch = body[i]
    if (ch === '"' || ch === "'" || ch === '`') { i = skipString(body, i); continue }
    if (ch === '/' && body[i + 1] === '/') {
      const nl = body.indexOf('\n', i)
      i = nl === -1 ? body.length : nl
      continue
    }
    if (ch === '/' && body[i + 1] === '*') {
      const end = body.indexOf('*/', i + 2)
      i = end === -1 ? body.length : end + 2
      continue
    }
    if (ch === '{') { fnDepth++; i++; continue }
    if (ch === '}') { fnDepth--; i++; continue }
    // 检测嵌套函数定义（其内部的 return 不属于本回调）
    if (/\bfunction\b/.test(body.slice(i, i + 9)) && /^function\b/.test(body.slice(i))) {
      const brace = body.indexOf('{', i)
      i = brace === -1 ? i + 8 : matchClose(body, brace) + 1
      continue
    }
    if (/\breturn\b/.test(body.slice(i, i + 7)) && /^return\b/.test(body.slice(i))) {
      const ln = lineOf(bodyStart + 1 + i)
      const prev = body.slice(Math.max(0, i - 40), i)
      if (!/\breturn[a-zA-Z0-9_]$/.test(prev) && fnDepth >= 0) {
        topReturns.push({ line: ln, head: lines[ln - 1].trim() })
      }
      i += 6
      continue
    }
    i++
  }

  for (let ln = bodyStartLine; ln <= bodyEndLine; ln++) {
    const t = lines[ln - 1].trim()
    if (/\b(setInterval|addEventListener)\s*\(/.test(t) && !/function/.test(t)) {
      sideEffects.push({ line: ln, head: t })
    }
  }

  if (topReturns.length && sideEffects.length) {
    found = true
    console.log(`\n[${path.basename(file)}] onMounted 回调体：第 ${bodyStartLine} ~ ${bodyEndLine} 行`)
    console.log('  顶层 return（提前退出点）:')
    for (const r of topReturns) console.log(`    行 ${r.line}: ${r.head}`)
    console.log('  副作用注册:')
    for (const s of sideEffects) console.log(`    行 ${s.line}: ${s.head}`)
    const blocked = sideEffects.filter((s) => topReturns.some((r) => r.line < s.line))
    if (blocked.length) {
      console.log('  ❌ 以下注册位于所有顶层 return 之后，正常路径下不会执行:')
      for (const s of blocked) console.log(`    行 ${s.line}: ${s.head}`)
    } else {
      console.log('  ✅ 未发现被 return 阻断的注册')
    }
  }
  searchFrom = close + 1
}

if (!found) console.log(`[${path.basename(file)}] 未发现 onMounted 早退问题`)
