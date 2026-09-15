<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const { username, role } = useAuth()
const memoryEnabled = ref(true)
const loading = ref(false)
const saving = ref(false)
const savedMsg = ref('')

async function loadSettings() {
  loading.value = true
  try {
    const data = await api.get('/api/settings')
    memoryEnabled.value = !!data.memory_enabled
  } catch {
    // default enabled
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  savedMsg.value = ''
  try {
    await api.put('/api/settings', { memory_enabled: memoryEnabled.value })
    savedMsg.value = 'Saved ✓'
    setTimeout(() => (savedMsg.value = ''), 2000)
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="py-14 sm:py-20">
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-10">
      <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
        User Preferences
      </div>
      <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
        Account Settings
      </h1>
      <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans">
        账户身份凭证与 AI 对话偏好设置
      </p>
    </header>

    <div class="max-w-xl space-y-8">
      <!-- Profile Section -->
      <section>
        <h2 class="font-mono text-xs uppercase tracking-widest text-neutral-400 mb-3">
          Account Profile
        </h2>
        <div class="divide-y divide-[#E5E5E5]/60 border-t border-b border-[#E5E5E5]/60 font-mono text-xs">
          <div class="flex items-center justify-between py-3.5">
            <span class="text-neutral-500 font-sans">Username</span>
            <span class="font-medium text-neutral-900">{{ username }}</span>
          </div>
          <div class="flex items-center justify-between py-3.5">
            <span class="text-neutral-500 font-sans">Role</span>
            <span class="text-neutral-900 uppercase font-medium">{{ role }}</span>
          </div>
          <div class="flex items-center justify-between py-3.5">
            <span class="text-neutral-500 font-sans">Session Status</span>
            <span class="flex items-center gap-1.5 text-neutral-800">
              <span class="h-1.5 w-1.5 rounded-full bg-neutral-900" />
              <span>Session Active</span>
            </span>
          </div>
        </div>
      </section>

      <!-- AI Preferences Section -->
      <section>
        <h2 class="font-mono text-xs uppercase tracking-widest text-neutral-400 mb-3">
          AI Preferences
        </h2>

        <div class="border-t border-b border-[#E5E5E5]/60 py-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-xs font-medium text-neutral-900 font-sans">长期对话记忆 (Long-term Memory)</p>
              <p class="mt-1 text-xs text-neutral-500 leading-relaxed font-sans">
                在对话过程中自动归纳偏好与关键工程上下文，以便在后续会话中无缝调用。
              </p>
            </div>

            <!-- Minimal Switch -->
            <button
              type="button"
              class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors cursor-pointer"
              :class="memoryEnabled ? 'bg-neutral-900' : 'bg-neutral-200'"
              @click="memoryEnabled = !memoryEnabled"
            >
              <span
                class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
                :class="memoryEnabled ? 'translate-x-4.5' : 'translate-x-0.5'"
              />
            </button>
          </div>
        </div>

        <div class="mt-6 flex items-center gap-3">
          <button
            type="button"
            :disabled="saving"
            class="font-mono text-xs px-4 py-2 bg-neutral-900 text-white rounded font-normal hover:bg-neutral-800 disabled:opacity-50 transition-colors cursor-pointer"
            @click="save"
          >
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
          <span v-if="savedMsg" class="font-mono text-xs text-neutral-900 font-medium">
            {{ savedMsg }}
          </span>
        </div>
      </section>
    </div>
  </div>
</template>