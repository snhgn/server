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
  <div class="flex min-h-[calc(100vh-14rem)] items-center justify-center py-16 px-4 sm:px-6">
    <div class="w-full max-w-sm rounded-lg border border-[#E5E5E5]/80 bg-white p-8 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
      
      <!-- Brand Header -->
      <div class="flex flex-col items-center text-center mb-8">
        <BrandWordmark size="md" />
        <p class="mt-2.5 font-mono text-[11px] text-neutral-400">
          Digital Space Authentication
        </p>
      </div>

      <form class="space-y-4" @submit.prevent="handleLogin">
        <div>
          <label class="block font-mono text-[11px] uppercase tracking-widest text-neutral-400 mb-1.5">
            Username
          </label>
          <input
            v-model="username"
            type="text"
            required
            autocomplete="username"
            placeholder="admin"
            class="w-full rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-xs font-mono text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-900 focus:bg-white focus:outline-none transition-colors"
          />
        </div>

        <div>
          <label class="block font-mono text-[11px] uppercase tracking-widest text-neutral-400 mb-1.5">
            Password
          </label>
          <input
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            placeholder="••••••••"
            class="w-full rounded border border-[#E5E5E5] bg-[#FAFAFA] px-3 py-2 text-xs font-mono text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-900 focus:bg-white focus:outline-none transition-colors"
          />
        </div>

        <div v-if="errorMsg" class="rounded bg-red-50/70 border border-red-100 p-2 font-mono text-[11px] text-red-600">
          {{ errorMsg }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded bg-neutral-900 py-2.5 font-mono text-xs text-white hover:bg-neutral-800 disabled:opacity-50 transition-colors cursor-pointer"
        >
          {{ loading ? 'Authenticating...' : 'Enter Workspace' }}
        </button>
      </form>

      <div class="mt-8 text-center border-t border-neutral-100 pt-4 font-mono text-[10px] text-neutral-400">
        Host Node: snhgn-primary
      </div>
    </div>
  </div>
</template>