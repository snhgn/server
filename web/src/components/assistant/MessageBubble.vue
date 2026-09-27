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

const renderer = new marked.Renderer()
renderer.code = function ({ text, lang }: { text: string; lang?: string | undefined }): string {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(text, { language, ignoreIllegals: true }).value
  const langLabel = lang && hljs.getLanguage(lang) ? lang : 'text'
  return (
    `<div class="my-3 rounded-lg border border-[#E5E5E5] bg-[#F8F9FA] overflow-hidden">` +
    `<div class="flex items-center justify-between border-b border-[#E5E5E5] bg-white px-3 py-1.5 font-mono text-[11px] text-neutral-500">` +
    `<span class="text-neutral-700 font-medium">${langLabel}</span>` +
    `<button type="button" class="text-neutral-400 hover:text-neutral-900 cursor-pointer transition-colors" data-copy-code>Copy</button>` +
    `</div>` +
    `<pre class="p-3 text-xs leading-relaxed font-mono overflow-x-auto text-neutral-900"><code class="hljs language-${language}">${highlighted}</code></pre>` +
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
    return props.text
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