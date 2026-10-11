<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const { username, role } = useAuth()
const memoryEnabled = ref(true)
const loading = ref(false)
const saving = ref(false)
const savedMsg = ref('')
const errorMsg = ref('')

// 用户设置由 ai-service 承载，网关侧统一前缀为 /api/ai/settings
// （曾误用 /api/settings，网关无此路由 → 404，读取与保存都会静默失败）
const SETTINGS_PATH = '/api/ai/settings'

async function loadSettings() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await api.get(SETTINGS_PATH)
    memoryEnabled.value = !!data.memory_enabled
  } catch {
    // 读取失败时保留默认开启，并显式告知用户，避免开关显示与实际不一致
    errorMsg.value = '偏好读取失败，显示的可能不是服务端当前设置'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  savedMsg.value = ''
  errorMsg.value = ''
  try {
    await api.put(SETTINGS_PATH, { memory_enabled: memoryEnabled.value })
    savedMsg.value = '已保存 ✓'
    setTimeout(() => (savedMsg.value = ''), 2000)
  } catch (e: any) {
    errorMsg.value = e?.message || '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="py-10 sm:py-14">
    <header class="mb-8">
      <div class="md2-overline">User Preferences</div>
      <h1 class="md2-h2 mt-1 text-on-surface">Account Settings</h1>
      <p class="mt-2 text-ink-secondary md2-body1">
        账户身份凭证与 AI 对话偏好设置
      </p>
    </header>

    <div class="max-w-2xl space-y-4">
      <!-- Profile Section -->
      <section class="md2-card p-5">
        <h2 class="md2-section-title mb-1">Account Profile</h2>
        <div class="md2-list -mx-5 -mb-5">
          <div class="md2-list-item justify-between">
            <span class="md2-list-item__sub">Username</span>
            <span class="md2-list-item__title font-medium">{{ username }}</span>
          </div>
          <div class="md2-divider" />
          <div class="md2-list-item justify-between">
            <span class="md2-list-item__sub">Role</span>
            <span class="md2-list-item__title font-medium uppercase">{{ role }}</span>
          </div>
          <div class="md2-divider" />
          <div class="md2-list-item justify-between">
            <span class="md2-list-item__sub">Session Status</span>
            <span class="md2-list-item__title flex items-center gap-2">
              <span class="h-2 w-2 rounded-full bg-success" />
              Session Active
            </span>
          </div>
        </div>
      </section>

      <!-- AI Preferences Section -->
      <section class="md2-card p-5">
        <h2 class="md2-section-title mb-1">AI Preferences</h2>

        <div class="md2-list -mx-5">
          <div class="md2-list-item justify-between gap-6">
            <div>
              <p class="md2-body1 font-medium">长期对话记忆 (Long-term Memory)</p>
              <p class="mt-1 text-ink-secondary md2-body2">
                在对话过程中自动归纳偏好与关键工程上下文，以便在后续会话中无缝调用。
              </p>
            </div>

            <!-- MD2 Switch -->
            <button
              type="button"
              role="switch"
              class="md2-switch"
              :aria-checked="memoryEnabled"
              :aria-label="'长期对话记忆'"
              @click="memoryEnabled = !memoryEnabled"
            >
              <span class="md2-switch__thumb" />
            </button>
          </div>
        </div>

        <div class="mt-4 flex items-center gap-3 border-t border-divider pt-4">
          <button
            type="button"
            :disabled="saving"
            class="md2-btn md2-btn--contained md2-btn--sentence !h-10 px-6"
            @click="save"
          >
            {{ saving ? '保存中...' : '保存修改' }}
          </button>
          <span
            v-if="savedMsg"
            class="md2-body2 font-medium"
            style="color: var(--md2-success);"
          >
            {{ savedMsg }}
          </span>
          <span
            v-if="errorMsg"
            class="md2-body2 font-medium"
            role="alert"
            style="color: var(--md2-error);"
          >
            {{ errorMsg }}
          </span>
        </div>
      </section>
    </div>
  </div>
</template>
