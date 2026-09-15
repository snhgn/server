<script setup lang="ts">
import { ref } from 'vue'

const emailCopied = ref(false)

function copyEmail() {
  navigator.clipboard.writeText('hello@snhgn.me')
  emailCopied.value = true
  setTimeout(() => (emailCopied.value = false), 2000)
}
</script>

<template>
  <div class="py-14 sm:py-20">
    
    <header class="border-b border-[#E5E5E5]/60 pb-8 mb-12">
      <div class="font-mono text-xs text-neutral-400 uppercase tracking-widest mb-2">
        About snh<span class="text-amber-500 font-medium">g</span>n.
      </div>
      <h1 class="text-2xl font-light tracking-tight text-neutral-900 sm:text-3xl">
        Stay curious, keep building.
      </h1>
      <p class="mt-2 text-xs sm:text-sm text-neutral-500 font-sans leading-relaxed">
        个人简介、工程专注方向与数字空间节点信息
      </p>
    </header>

    <div class="grid gap-12 sm:grid-cols-3">
      
      <!-- Left 2 Cols: Overview & Engineering Focus -->
      <div class="sm:col-span-2 space-y-10 text-xs sm:text-sm leading-relaxed text-neutral-600 font-sans">
        
        <section>
          <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400 mb-3">
            Overview
          </h2>
          <p>
            电子信息工程方向。专注于嵌入式底层驱动开发、机器人运动控制、机器视觉伺服与私有化数字服务架构。
          </p>
          <p class="mt-3">
            喜欢从元器件、电路板、寄存器与通信总线开始，构建出具备实时控制与确定性响应能力的物理实体系统。同时通过自建物理 Linux 节点与 Cloudflare 网络通道，持续构建私有化生产力工具。
          </p>
        </section>

        <section class="pt-8 border-t border-[#E5E5E5]/60">
          <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400 mb-4">
            Areas of Focus
          </h2>
          <ul class="space-y-3 font-mono text-xs text-neutral-600">
            <li class="flex items-start gap-2">
              <span class="text-neutral-400 mt-0.5">·</span>
              <div>
                <strong class="text-neutral-900 font-medium">Embedded Systems:</strong>
                <span class="text-neutral-500 ml-1">STM32, FreeRTOS, CAN Bus, Sensor Fusion, Motor Driver</span>
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-neutral-400 mt-0.5">·</span>
              <div>
                <strong class="text-neutral-900 font-medium">Robotics & Vision:</strong>
                <span class="text-neutral-500 ml-1">Cascaded PID, Gimbal/Chassis Control, OpenCV Vision Servo</span>
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-neutral-400 mt-0.5">·</span>
              <div>
                <strong class="text-neutral-900 font-medium">AI & Knowledge Engines:</strong>
                <span class="text-neutral-500 ml-1">RAG Vector Store, Dual-Engine LLM Harness, Semantic Retrieval</span>
              </div>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-neutral-400 mt-0.5">·</span>
              <div>
                <strong class="text-neutral-900 font-medium">Self-Hosting & DevOps:</strong>
                <span class="text-neutral-500 ml-1">Ubuntu Server, Docker, Caddy, Cloudflare Tunnel, Automated Pipelines</span>
              </div>
            </li>
          </ul>
        </section>

        <section class="pt-8 border-t border-[#E5E5E5]/60">
          <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400 mb-3">
            Philosophy
          </h2>
          <p class="text-neutral-500 italic">
            “不把所有东西说满，不把所有空间填满，不把所有注意力都抢走。<br>
            留白，但不空；克制，但不弱；安静，但一直在构建。”
          </p>
        </section>

      </div>

      <!-- Right 1 Col: Channels & Node Telemetry -->
      <div class="space-y-10">
        
        <section>
          <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400 mb-3">
            Channels
          </h2>
          <div class="space-y-3 font-mono text-xs">
            <div class="flex items-center justify-between border-b border-[#E5E5E5]/60 pb-2">
              <span class="text-neutral-400">Email</span>
              <button
                type="button"
                class="text-neutral-900 hover:text-neutral-500 cursor-pointer transition-colors"
                @click="copyEmail"
              >
                {{ emailCopied ? 'Copied ✓' : 'hello@snhgn.me' }}
              </button>
            </div>
            <div class="flex items-center justify-between border-b border-[#E5E5E5]/60 pb-2">
              <span class="text-neutral-400">GitHub</span>
              <a
                href="https://github.com/snhgn"
                target="_blank"
                rel="noopener"
                class="text-neutral-900 hover:text-neutral-500 transition-colors"
              >
                github.com/snhgn ↗
              </a>
            </div>
            <div class="flex items-center justify-between border-b border-[#E5E5E5]/60 pb-2">
              <span class="text-neutral-400">Location</span>
              <span class="text-neutral-700">Beijing, China</span>
            </div>
          </div>
        </section>

        <section>
          <h2 class="font-mono text-xs font-medium uppercase tracking-widest text-neutral-400 mb-3">
            Node System
          </h2>
          <div class="space-y-2 font-mono text-xs text-neutral-500">
            <p>· Host: snhgn-primary (Ubuntu 22.04 LTS)</p>
            <p>· Network: Cloudflare Tunnel (Zero-Trust)</p>
            <p>· Core: FastAPI · Docker · Caddy</p>
          </div>
        </section>

      </div>

    </div>

  </div>
</template>
