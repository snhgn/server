<script setup lang="ts">
import BrandWordmark from '@/components/BrandWordmark.vue'
</script>

<template>
  <footer class="border-t border-[#E5E5E5]/60 bg-[#FAFAFA] py-12 transition-colors">
    <div class="mx-auto flex w-full max-w-4xl flex-col items-start justify-between gap-4 px-4 font-mono text-[11px] text-neutral-400 sm:flex-row sm:items-center sm:px-6">
      
      <!-- Left: Signature Wordmark & Slogan -->
      <div class="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3">
        <BrandWordmark size="xs" :animated-dot="false" />
        <span class="hidden sm:inline text-neutral-300">·</span>
        <span class="text-neutral-500 font-sans tracking-tight text-xs">Stay curious, keep building.</span>
      </div>

      <!-- Right: Copyright & Digital Space Anchor -->
      <div class="flex items-center gap-3 text-neutral-400 font-mono">
        <span>Digital Sanctuary</span>
        <span class="text-neutral-300">·</span>
        <span class="text-neutral-500">© {{ new Date().getFullYear() }} snh<span class="text-amber-500 font-medium">g</span>n.</span>
      </div>

    </div>
  </footer>
</template>
