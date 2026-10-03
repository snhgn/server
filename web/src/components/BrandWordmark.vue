<script setup lang="ts">
import BrandSymbol from '@/components/BrandSymbol.vue'

withDefaults(
  defineProps<{
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero'
    animatedDot?: boolean
    withSymbol?: boolean
    /* on-primary：放在 MD2 实心 app bar 上时用。
       本站 app bar 是浅黄底 + 深字（#fbbf05 上白字只有 1.71:1，深字
       #3e2f00 是 7.79:1），所以这一态整枚字标转深色。
       层级改由 font-semibold 的 g 和圆点承担 —— 任何彩色 accent 压在
       黄色上都达不到 AA（黄 1.71:1、红 2.28:1、蓝 1.34:1），一律不用。 */
    tone?: 'default' | 'on-primary'
  }>(),
  {
    size: 'sm',
    animatedDot: true,
    withSymbol: true,
    tone: 'default',
  }
)
</script>

<template>
  <span class="inline-flex items-center select-none transition-colors duration-200"
    :class="{
      'gap-1.5': size === 'xs' || size === 'sm',
      'gap-2': size === 'md',
      'gap-2.5': size === 'lg' || size === 'xl',
      'gap-3.5': size === 'hero',
    }"
  >
    <BrandSymbol
      v-if="withSymbol"
      :size="size === 'hero' ? 32 : size === 'xl' ? 22 : size === 'lg' ? 18 : size === 'md' ? 16 : size === 'sm' ? 14 : 12"
      :animated="animatedDot"
      :color="tone === 'on-primary' ? 'var(--md2-on-primary)' : 'currentColor'"
      :dot-color="tone === 'on-primary' ? 'var(--md2-on-primary)' : 'var(--md2-accent-ink)'"
    />
    <span
      class="inline-flex items-baseline font-sans font-medium transition-colors"
      :style="tone === 'on-primary' ? { color: 'var(--md2-on-primary)' } : { color: 'var(--md2-on-surface)' }"
      :class="[
        {
          'text-[11px] tracking-[0.28em]': size === 'xs',
          'text-xs tracking-[0.28em]': size === 'sm',
          'text-sm tracking-[0.28em]': size === 'md',
          'text-lg tracking-[0.3em]': size === 'lg',
          'text-2xl tracking-[0.32em] font-normal': size === 'xl',
          'text-3xl sm:text-5xl tracking-[0.35em] font-light': size === 'hero',
        },
      ]"
    >
      <span>snh</span><span
        class="font-semibold transition-colors duration-200"
        :class="tone === 'on-primary' ? '' : 'text-accent-ink'"
      >g</span><span>n</span>
      <span
        class="font-semibold transition-all duration-300"
        :class="[
          tone === 'on-primary' ? 'opacity-60 group-hover:opacity-100' : 'group-hover:text-accent-ink',
          animatedDot ? '' : '',
        ]"
      >.</span>
    </span>
  </span>
</template>
