<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number | string
    animated?: boolean
    color?: string
    dotColor?: string
  }>(),
  {
    size: 16,
    animated: false,
    color: 'currentColor',
    dotColor: '#EAB308',
  }
)
</script>

<template>
  <!-- Minimalist Personal Signature Crosshair Mark -->
  <span
    class="relative inline-flex items-center justify-center shrink-0 select-none leading-none"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      class="transition-transform duration-300 ease-out"
      :class="{ 'group-hover:rotate-90 group-hover:scale-110': animated }"
    >
      <line x1="12" y1="3" x2="12" y2="21" :stroke="color" stroke-width="2.2" stroke-linecap="round" />
      <line x1="3" y1="12" x2="21" y2="12" :stroke="color" stroke-width="2.2" stroke-linecap="round" />
      <circle cx="12" cy="12" r="2.8" :fill="dotColor" />
      <circle cx="12" cy="12" r="1.1" fill="white" />
    </svg>
  </span>
</template>
