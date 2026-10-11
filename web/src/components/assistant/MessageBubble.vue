<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import 'highlight.js/styles/github.css'
import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import python from 'highlight.js/lib/languages/python'
import ruby from 'highlight.js/lib/languages/ruby'
import rust from 'highlight.js/lib/languages/rust'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const hljsLanguages: Record<string, unknown> = {
  bash, c, cpp, css, go, java, javascript, json, markdown,
  php, python, ruby, rust, sql, typescript, xml, yaml,
}
for (const [name, lang] of Object.entries(hljsLanguages)) {
  hljs.registerLanguage(name, lang as any)
}

interface Source {
  content: string
  category?: string
}
interface FileMeta {
  id: string
  filename: string
  file_type: 'image' | 'text' | 'code' | 'unknown'
  file_size: number
  size_label?: string
  status?: string
}

interface Props {
  role: 'user' | 'assistant'
  text: string
  sources?: Source[]
  provider?: string
  files?: FileMeta[]
  streaming?: boolean
  statusSteps?: string[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'add-to-knowledge', file: FileMeta): void
}>()

const showThinking = ref(true)
const copied = ref(false)

// ---- Markdown Renderer ----
marked.setOptions({
  breaks: true,
  gfm: true,
})

// ---- 输出净化 ----
// 消息正文来自 AI 生成结果、RAG 知识库片段与会话历史，均属不可信输入，
// 且最终以 v-html 注入 DOM。marked 默认原样透传原始 HTML 与任意协议链接，
// 因此必须在此处收口：HTML 转义 + 链接协议白名单。
const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (c) => HTML_ESCAPES[c])
}

// 允许：http(s) / mailto / 站内相对与锚点 / 内联图片 data URI
// 拒绝：javascript:、vbscript:、data:text/html 等可执行或伪装协议
const SAFE_URL = /^(?:https?:\/\/|mailto:|#|\/|\.{1,2}\/|data:image\/(?:png|jpe?g|gif|webp|avif);base64,)/i

function safeUrl(href: unknown): string {
  const raw = String(href ?? '').trim()
  if (!raw) return ''
  // 先剔除控制字符与空白，防止 "java\nscript:" 这类绕过
  const compact = raw.replace(/[\u0000-\u001F\u007F-\u009F\s]/g, '')
  return SAFE_URL.test(compact) ? compact : ''
}

const renderer = new marked.Renderer()
// 原始 HTML 一律按文本呈现（<img onerror=…> 等不再被执行）
renderer.html = function (token: any): string {
  return escapeHtml(token?.text)
}
renderer.link = function (token: any): string {
  const href = safeUrl(token?.href)
  const text = escapeHtml(token?.text ?? token?.href ?? '')
  if (!href) return text
  const title = token?.title ? ` title="${escapeHtml(token.title)}"` : ''
  return `<a href="${escapeHtml(href)}"${title} target="_blank" rel="noopener noreferrer nofollow">${text}</a>`
}
renderer.image = function (token: any): string {
  const href = safeUrl(token?.href)
  if (!href) return escapeHtml(token?.text ?? '')
  const title = token?.title ? ` title="${escapeHtml(token.title)}"` : ''
  return `<img src="${escapeHtml(href)}" alt="${escapeHtml(token?.text ?? '')}"${title} loading="lazy" />`
}
renderer.code = function ({ text, lang }: { text: string; lang?: string | undefined }): string {
  // 本项目用的是 highlight.js/lib/core：它只带已注册语言，不含内置的 plaintext。
  // 早期实现对「未标注语言 / 未注册语言」的围栏一律传 language='plaintext'，
  // hljs 会抛 Unknown language → 整条消息的渲染被打回 catch，用户看到的是 markdown 源码。
  // 未知语言直接输出转义后的纯文本，不再走 hljs。
  const known = !!(lang && hljs.getLanguage(lang))
  const highlighted = known
    ? hljs.highlight(text, { language: lang as string, ignoreIllegals: true }).value
    : escapeHtml(text)
  // lang 由模型输出可控，必须转义后再拼进 HTML
  const langLabel = escapeHtml(known ? (lang as string) : 'text')
  const safeLanguage = escapeHtml(known ? (lang as string) : 'plaintext')
  return (
    `<div class="my-3 rounded-lg border border-[#E5E5E5] bg-[#F8F9FA] overflow-hidden">` +
    `<div class="flex items-center justify-between border-b border-[#E5E5E5] bg-white px-3 py-1.5 font-mono text-[11px] text-neutral-500">` +
    `<span class="text-neutral-700 font-medium">${langLabel}</span>` +
    `<button type="button" class="text-neutral-400 hover:text-neutral-900 cursor-pointer transition-colors" data-copy-code>Copy</button>` +
    `</div>` +
    `<pre class="p-3 text-xs leading-relaxed font-mono overflow-x-auto text-neutral-900"><code class="hljs language-${safeLanguage}">${highlighted}</code></pre>` +
    `</div>`
  )
}

// LaTeX Support
marked.use({
  extensions: [
    {
      name: 'inlineMath',
      level: 'inline',
      start(src: string) {
        const m = /(?:^|[^$])\$(?=\S)/.exec(src)
        if (!m) return undefined
        return m.index + m[0].length - 1
      },
      tokenizer(src: string) {
        const match = /^\$([^\s$][^$]*?[^\s$])\$(?!\$)/.exec(src)
        if (match) return { type: 'inlineMath', raw: match[0], math: match[1] }
        return undefined
      },
      renderer(token: any) {
        try {
          return katex.renderToString(token.math, { throwOnError: false })
        } catch {
          return token.raw
        }
      },
    },
    {
      name: 'blockMath',
      level: 'block',
      start(src: string) {
        return src.indexOf('$$') < 0 ? undefined : src.indexOf('$$')
      },
      tokenizer(src: string) {
        const match = /^\$\$([\s\S]+?)\$\$/.exec(src)
        if (match) return { type: 'blockMath', raw: match[0], math: match[1] }
        return undefined
      },
      renderer(token: any) {
        try {
          return `<div class="my-3 overflow-x-auto text-center">${katex.renderToString(token.math, {
            displayMode: true,
            throwOnError: false,
          })}</div>`
        } catch {
          return token.raw
        }
      },
    },
  ],
})

const html = computed(() => {
  if (props.role === 'user') return ''
  if (!props.text) return ''
  try {
    return marked.parse(props.text, { renderer, async: false }) as string
  } catch {
    // 兜底：渲染失败时也必须转义后再交给 v-html，否则原始文本里的标签会被当 HTML 执行
    return escapeHtml(props.text)
  }
})

const showSources = computed(
  () => props.role === 'assistant' && props.sources && props.sources.length > 0,
)
const showFiles = computed(() => props.files && props.files.length > 0)

async function copyText(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // fallback
  }
}

function onArticleClick(e: MouseEvent) {
  const btn = (e.target as HTMLElement).closest('[data-copy-code]') as HTMLElement | null
  if (!btn) return
  const pre = btn.closest('.my-3')?.querySelector('pre')
  if (pre) {
    copyText(pre.textContent || '')
    const old = btn.textContent
    btn.textContent = 'Copied ✓'
    setTimeout(() => (btn.textContent = old), 1400)
  }
}

function formatSize(f: FileMeta): string {
  if (f.size_label) return f.size_label
  const n = f.file_size
  if (n < 1024) return `${n}B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`
  return `${(n / 1024 / 1024).toFixed(2)}MB`
}
</script>

<template>
  <!-- User Message: Right Aligned -->
  <div v-if="role === 'user'" class="flex flex-col items-end">
    <!-- Attached Files -->
    <div v-if="showFiles" class="mb-1.5 flex max-w-[85%] flex-col items-end gap-1.5">
      <div
        v-for="f in files"
        :key="f.id"
        class="flex items-center gap-2 rounded border border-[#E5E5E5] bg-white px-2.5 py-1 text-xs text-neutral-700 font-mono shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
      >
        <span class="max-w-[180px] truncate font-medium text-[11px]">{{ f.filename }}</span>
        <span class="font-mono text-[10px] text-neutral-400">({{ formatSize(f) }})</span>
      </div>
    </div>

    <!-- Bubble -->
    <div class="max-w-[85%] whitespace-pre-wrap break-words rounded-lg border border-[#E5E5E5] bg-white px-4 py-2.5 text-xs sm:text-sm leading-relaxed text-neutral-900 shadow-[0_1px_2px_rgba(0,0,0,0.02)] font-sans sm:max-w-[75%]">
      {{ text }}
    </div>
  </div>

  <!-- Assistant Message: Stream Flow -->
  <div v-else class="flex items-start gap-3.5">
    
    <!-- Signature Mark Indicator -->
    <div class="flex h-5 w-5 flex-none items-center justify-center rounded-full bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 mt-1 shrink-0 font-mono text-[10px]" title="snhgn.">
      <span>.</span>
    </div>

    <!-- Message Content Area -->
    <div class="min-w-0 flex-1">
      
      <!-- Early Status & Thinking Steps Accordion -->
      <div v-if="statusSteps && statusSteps.length > 0" class="mb-3">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded border border-[#E5E5E5] bg-white px-2 py-1 font-mono text-[11px] text-neutral-600 hover:text-neutral-900 transition-colors cursor-pointer"
          @click="showThinking = !showThinking"
        >
          <span v-if="streaming && !text" class="inline-block h-1.5 w-1.5 animate-ping rounded-full bg-neutral-900 dark:bg-emerald-400" />
          <span>Thinking ({{ statusSteps.length }} steps)</span>
          <span class="text-[9px] text-neutral-400">{{ showThinking ? '▲' : '▼' }}</span>
        </button>

        <div v-if="showThinking" class="mt-2 rounded border border-[#E5E5E5] bg-[#FAFAFA] p-3 font-mono text-[11px] text-neutral-600 space-y-1.5">
          <div v-for="(step, idx) in statusSteps" :key="idx" class="flex items-center gap-2">
            <span class="text-neutral-400">·</span>
            <span>{{ step }}</span>
          </div>
          <div v-if="streaming && !text" class="flex items-center gap-2 text-neutral-400">
            <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-900 dark:bg-emerald-400" />
            <span>Processing stream...</span>
          </div>
        </div>
      </div>

      <!-- Markdown Output -->
      <article
        v-if="text"
        class="prose prose-neutral max-w-none text-xs sm:text-sm leading-relaxed text-neutral-900"
        @click="onArticleClick"
        v-html="html"
      />

      <!-- Streaming Cursor -->
      <span
        v-if="streaming && text"
        class="ml-0.5 inline-block h-3.5 w-1 rounded-full bg-neutral-900 dark:bg-white align-middle animate-pulse"
      />

      <!-- Sources & Citations -->
      <div v-if="showSources" class="mt-4 border-t border-[#E5E5E5]/70 pt-2 font-mono text-xs">
        <span class="text-[11px] text-neutral-400 font-sans">知识库引用：</span>
        <div class="mt-1.5 flex flex-wrap gap-1.5">
          <div
            v-for="(s, idx) in sources"
            :key="idx"
            class="rounded border border-[#E5E5E5] bg-white px-2 py-0.5 text-[11px] text-neutral-600 max-w-sm truncate"
          >
            [{{ idx + 1 }}] {{ s.category ? `[${s.category}] ` : '' }}{{ s.content.slice(0, 35) }}...
          </div>
        </div>
      </div>

    </div>
  </div>
</template>