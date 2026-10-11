/**
 * 验证脚本：直接取 MessageBubble.vue 中「净化 + renderer」的真实源码，
 * 用 TypeScript 转译后在 Node 里跑一遍，确认恶意输入被正确净化。
 */
const fs = require('fs')
const ts = require('typescript')
const { marked } = require('marked')
const hljs = require('highlight.js/lib/core')

const VUE = 'src/components/assistant/MessageBubble.vue'
const src = fs.readFileSync(VUE, 'utf8')

const start = src.indexOf('// ---- 输出净化 ----')
const end = src.indexOf('// LaTeX Support')
if (start === -1 || end === -1) {
  console.error('未能定位净化代码段')
  process.exit(1)
}
const snippet = src.slice(start, end)
console.log('—— 取到的真实源码片段（' + snippet.split('\n').length + ' 行）——')

const wrapped = `(function (marked, hljs) {\n${snippet}\n return renderer;\n})`
const js = ts.transpileModule(wrapped, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText

const renderer = eval(js)(marked, hljs)

marked.setOptions({ breaks: true, gfm: true })

const CASES = [
  ['裸 HTML img onerror', '正常段落\n\n<img src=x onerror="alert(1)">'],
  ['裸 script 标签', '<script>alert(2)<\\/script>'],
  ['javascript: 链接', '[点我](javascript:alert(1))'],
  ['换行绕过 javascript:', '[点我](java\nscript:alert(1))'],
  ['data:text/html 链接', '[x](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)'],
  ['图片 onerror', '![alt](x" onerror="alert(1))'],
  ['代码围栏语言注入', '```<img src=x onerror=alert(1)>\nprint(1)\n```'],
  ['正常 markdown', '**加粗** 与 `代码`\n\n[官网](https://snhgn.me/about)'],
]

let failed = 0
for (const [name, input] of CASES) {
  const out = marked.parse(input, { renderer, async: false })
  const dangerous =
    /onerror\s*=|onload\s*=|javascript:|<script/i.test(out) && !/&lt;|&quot;/.test(out)
  // 更精确：原始可执行片段是否以「活的 HTML」形式出现
  const liveOnerror = /<img[^>]*\sonerror\s*=/i.test(out)
  const liveScript = /<script/i.test(out)
  const liveJsHref = /href\s*=\s*"javascript:/i.test(out)
  const bad = liveOnerror || liveScript || liveJsHref
  if (bad) failed++
  console.log(`\n[${bad ? '❌ 仍有风险' : '✅ 已净化'}] ${name}`)
  console.log('  输入 : ' + JSON.stringify(input))
  console.log('  输出 : ' + out.replace(/\n/g, '\\n'))
}

console.log('\n结果：' + (failed === 0 ? '全部净化 ✅' : `${failed} 条仍有风险 ❌`))
process.exit(failed === 0 ? 0 : 1)
