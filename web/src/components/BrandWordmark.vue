<script setup lang="ts">
import BrandSymbol from '@/components/BrandSymbol.vue'

withDefaults(
  defineProps<{
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'hero'
    animatedDot?: boolean
    withSymbol?: boolean
  }>(),
  {
    size: 'sm',
    animatedDot: true,
    withSymbol: true,
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
    />
    <span
      class="inline-flex items-baseline font-sans font-normal text-neutral-900 tracking-[0.28em]"
      :class="{
        'text-[11px]': size === 'xs',
        'text-xs': size === 'sm',
        'text-sm': size === 'md',
        'text-lg tracking-[0.3em]': size === 'lg',
        'text-2xl tracking-[0.32em] font-light': size === 'xl',
        'text-3xl sm:text-5xl tracking-[0.35em] font-light': size === 'hero',
      }"
    >
      <span>snh</span><span class="text-amber-500 font-semibold transition-colors duration-200">g</span><span>n</span>
      <span
        class="font-semibold text-neutral-900 transition-all duration-300"
        :class="{ 'group-hover:text-amber-500': animatedDot }"
      >.</span>
    </span>
  </span>
</template>
