<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/stores/auth'
import BrandWordmark from '@/components/BrandWordmark.vue'

const { login } = useAuth()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const errorMsg = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  errorMsg.value = ''
  try {
    await login(username.value, password.value)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    errorMsg.value = e.message || '登录失败，请检查用户名或密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-[calc(100vh-14rem)] items-center justify-center px-4 py-12 sm:px-6">
    <div class="md2-card md2-accent-quad-top w-full max-w-sm p-6 sm:p-8">

      <!-- Brand Header -->
      <div class="mb-6 flex flex-col items-center text-center">
        <BrandWordmark size="md" />
        <p class="mt-2 md2-caption text-ink-secondary">
          Digital Space Authentication
        </p>
      </div>

      <form class="space-y-5" @submit.prevent="handleLogin">
        <div class="md2-field">
          <label class="md2-field-label" for="login-username">用户名</label>
          <input
            id="login-username"
            v-model="username"
            type="text"
            required
            autocomplete="username"
            placeholder="admin"
            class="md2-input font-mono"
          />
        </div>

        <div class="md2-field">
          <label class="md2-field-label" for="login-password">密码</label>
          <input
            id="login-password"
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            placeholder="••••••••"
            class="md2-input font-mono"
          />
        </div>

        <div
          v-if="errorMsg"
          class="rounded px-3 py-2 md2-body2"
          style="background-color: var(--md2-error-container); color: var(--md2-on-error-container);"
          role="alert"
        >
          {{ errorMsg }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="md2-btn md2-btn--contained md2-btn--sentence w-full !h-11"
        >
          {{ loading ? '正在验证...' : '进入工作区' }}
        </button>
      </form>

      <div class="mt-6 border-t border-divider pt-4 text-center font-mono text-[10px] text-ink-secondary">
        Host Node: snhgn-primary
      </div>
    </div>
  </div>
</template>