<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import Footer from '@/components/Footer.vue'

const route = useRoute()
const fullScreen = computed(() => !!route.meta.fullScreen)
const isStandalone = computed(() => !!route.meta.standalone)
const isApp = computed(() => {
  if (typeof window === 'undefined') return false
  return route.query.app === '1' || navigator.userAgent.includes('SnhgnScheduleAndroid')
})
</script>

<template>
  <!-- App Mode (One-screen Zero-scroll full container for Android App) -->
  <div v-if="isApp" class="h-[100dvh] w-full overflow-hidden bg-[#FAFAFA] dark:bg-[#0A0B0D] text-[#111111] dark:text-neutral-100 antialiased selection:bg-neutral-200 selection:text-neutral-900">
    <router-view />
  </div>

  <!-- Full Screen Mode (e.g. /ai Workspace) -->
  <router-view v-else-if="fullScreen" />

  <!-- Standalone Mode (e.g. /schedule: no navbar/links to other pages, but keeps Footer logo) -->
  <div v-else-if="isStandalone" class="flex min-h-screen flex-col bg-[#FAFAFA] text-[#111111] antialiased selection:bg-neutral-200 selection:text-neutral-900 overflow-x-hidden">
    <main class="mx-auto w-full max-w-4xl flex-1 px-4 sm:px-6">
      <router-view />
    </main>
    <Footer />
  </div>

  <!-- Standard Digital Space Layout with Navbar & Footer -->
  <div v-else class="flex min-h-screen flex-col bg-[#FAFAFA] text-[#111111] antialiased selection:bg-neutral-200 selection:text-neutral-900 overflow-x-hidden">
    <Navbar />
    <main class="mx-auto w-full max-w-4xl flex-1 px-4 sm:px-6">
      <router-view />
    </main>
    <Footer />
  </div>
</template>