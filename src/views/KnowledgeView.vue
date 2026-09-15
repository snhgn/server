<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api'

interface MemoryItem {
  id?: number
  category: string
  key: string
  value: string
  updated_at?: string
}

const memories = ref<MemoryItem[]>([])
const loading = ref(true)
const search = ref('')
const selectedCategory = ref('ALL')

const categories = computed(() => {
  const set = new Set<string>()
  memories.value.forEach((m) => {
    if (m.category) set.add(m.category)
  })
  return ['ALL', ...Array.from(set)]
})

const filteredMemories = computed(() => {
  let list = memories.value
  if (selectedCategory.value !== 'ALL') {
    list = list.filter((m) => m.category === selectedCategory.value)
  }
  const q = search.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (m) =>
        m.key.toLowerCase().includes(q) ||
        m.value.toLowerCase().includes(q) ||
        m.category.toLowerCase().includes(q),
    )
  }
  return list
})

async function load() {
  loading.value = true
  try {
    const res = await api.get('/api/ai/memory')
    memories.value = res.memories || []
  } catch {
    memories.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="py-14 sm:py-20">
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div>
        <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
          Memory & RAG Store
        </div>
        <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
          Knowledge & Memory
        </h1>
        <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans">
          AI 助手沉淀的偏好设定与长期记忆语义条目
        </p>
      </div>

      <div class="flex items-center gap-2 font-mono text-xs">
        <button
          type="button"
          :disabled="loading"
          class="px-3 py-1 bg-neutral-900 text-white rounded font-normal hover:bg-neutral-800 disabled:opacity-50 transition-colors cursor-pointer"
          @click="load"
        >
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>
    </header>

    <!-- Filters & Search -->
    <div class="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono text-xs">
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="c in categories"
          :key="c"
          type="button"
          class="rounded px-2.5 py-1 text-xs transition-colors cursor-pointer"
          :class="selectedCategory === c ? 'bg-neutral-900 text-white' : 'border border-[#E5E5E5] bg-white text-neutral-600 hover:bg-[#FAFAFA]'"
          @click="selectedCategory = c"
        >
          {{ c }}
        </button>
      </div>

      <input
        v-model="search"
        type="text"
        placeholder="搜索记忆条目..."
        class="rounded border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-neutral-900 focus:border-neutral-900 focus:outline-none w-full sm:max-w-xs transition-colors font-sans"
      />
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="py-16 text-center text-xs font-mono text-neutral-400">
      Loading memory entries...
    </div>

    <!-- Empty State -->
    <div v-else-if="!filteredMemories.length" class="py-16 text-center text-xs font-mono text-neutral-400">
      No memory entries found.
    </div>

    <!-- List -->
    <div v-else class="divide-y divide-[#E5E5E5]/60 border-t border-b border-[#E5E5E5]/60">
      <div
        v-for="m in filteredMemories"
        :key="m.id || (m.category + '-' + m.key)"
        class="py-5"
      >
        <div class="flex items-baseline justify-between gap-2 font-mono text-xs">
          <div class="flex items-center gap-2">
            <span class="rounded bg-white border border-[#E5E5E5] px-1.5 py-0.5 text-[10px] font-medium text-neutral-700">
              {{ m.category }}
            </span>
            <span class="font-medium text-neutral-900">{{ m.key }}</span>
          </div>
          <span class="text-neutral-400 text-[11px]">{{ m.updated_at || '—' }}</span>
        </div>

        <p class="mt-2 text-xs sm:text-sm text-neutral-600 leading-relaxed font-sans">
          {{ m.value }}
        </p>
      </div>
    </div>
  </div>
</template>