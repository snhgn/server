<script setup lang="ts">
import BrandWordmark from '@/components/BrandWordmark.vue'
</script>

<template>
  <footer class="border-t border-divider bg-surface-alt py-10 transition-colors">
    <div class="mx-auto flex w-full max-w-5xl flex-col items-start justify-between gap-4 px-4 sm:flex-row sm:items-center sm:px-6 md2-body2">

      <!-- Left: Signature Wordmark & Slogan -->
      <div class="flex flex-col items-start gap-1.5 sm:flex-row sm:items-center sm:gap-3">
        <BrandWordmark size="xs" :animated-dot="false" />
        <!-- 纯装饰性分隔符：读屏不该念「间隔号」，aria-hidden 把它移出无障碍树。
             但它仍然是「看得见的文字」，所以颜色要过 AA。footer 底是
             bg-surface-alt(#f1f3f4)，实测：
               divider(12%黑)  → 1.31:1   ✗
               ink-tertiary(38%黑) → 2.64:1 ✗  ← 之前误以为达标
               ink-secondary(60%黑) → 5.61:1 ✓（深色档 #303134 上 5.75:1）
             要过 4.5:1 最低需要约 54% 黑，但没有这一档，直接用 secondary。 -->
        <span class="hidden text-ink-secondary sm:inline" aria-hidden="true">·</span>
        <span class="text-ink-secondary md2-body1">Stay curious, keep building.</span>
      </div>

      <!-- Right: Copyright & Digital Space Anchor -->
      <div class="flex items-center gap-3 font-mono text-[11px] text-ink-secondary">
        <span>Digital Sanctuary</span>
        <span class="text-ink-secondary" aria-hidden="true">·</span>
        <span>© {{ new Date().getFullYear() }} snh<span class="font-medium text-accent-ink">g</span>n.</span>
      </div>

    </div>
  </footer>
</template>
