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
  <div class="py-10 sm:py-14">

    <header class="mb-8">
      <div class="md2-overline">About snh<span class="text-accent-ink">g</span>n.</div>
      <h1 class="md2-h2 mt-1 text-on-surface">Stay curious, keep building.</h1>
      <p class="mt-2 text-ink-secondary md2-body1">
        个人简介、工程专注方向与数字空间节点信息
      </p>
    </header>

    <div class="grid gap-4 lg:grid-cols-3">

      <!-- Left 2 Cols: Overview & Engineering Focus -->
      <div class="lg:col-span-2 space-y-4">

        <section class="md2-card p-5 sm:p-6">
          <h2 class="md2-section-title mb-3">Overview</h2>
          <div class="space-y-3 text-ink-secondary md2-body1">
            <p>
              电子信息工程方向。专注于嵌入式底层驱动开发、机器人运动控制、机器视觉伺服与私有化数字服务架构。
            </p>
            <p>
              喜欢从元器件、电路板、寄存器与通信总线开始，构建出具备实时控制与确定性响应能力的物理实体系统。同时通过自建物理 Linux 节点与 Cloudflare 网络通道，持续构建私有化生产力工具。
            </p>
          </div>
        </section>

        <section class="md2-card p-5 sm:p-6">
          <h2 class="md2-section-title mb-4">Areas of Focus</h2>
          <div class="md2-list -mx-5 -mb-5 sm:-mx-6 sm:-mb-6">
            <div
              v-for="area in [
                { k: 'Embedded Systems', v: 'STM32, FreeRTOS, CAN Bus, Sensor Fusion, Motor Driver', a: 'blue' },
                { k: 'Robotics & Vision', v: 'Cascaded PID, Gimbal/Chassis Control, OpenCV Vision Servo', a: 'red' },
                { k: 'AI & Knowledge Engines', v: 'RAG Vector Store, Dual-Engine LLM Harness, Semantic Retrieval', a: 'green' },
                { k: 'Self-Hosting & DevOps', v: 'Ubuntu Server, Docker, Caddy, Cloudflare Tunnel, Automated Pipelines', a: 'yellow' },
              ]"
              :key="area.k"
              :data-accent="area.a"
              class="md2-list-item items-start"
            >
              <div class="md2-accent-rail">
                <div class="md2-list-item__title font-medium">{{ area.k }}</div>
                <div class="md2-list-item__sub">{{ area.v }}</div>
              </div>
            </div>
          </div>
        </section>

        <section class="md2-card p-5 sm:p-6">
          <h2 class="md2-section-title mb-3">Philosophy</h2>
          <blockquote
            class="md2-accent-quad pl-4 text-ink-secondary md2-body1"
          >
            “不把所有东西说满，不把所有空间填满，不把所有注意力都抢走。<br>
            留白，但不空；克制，但不弱；安静，但一直在构建。”
          </blockquote>
        </section>

      </div>

      <!-- Right 1 Col: Channels & Node Telemetry -->
      <div class="space-y-4">

        <section class="md2-card p-5">
          <h2 class="md2-section-title mb-2">Channels</h2>
          <div class="md2-list -mx-5 -mb-5">
            <div class="md2-list-item justify-between">
              <span class="md2-list-item__sub">Email</span>
              <button
                type="button"
                class="md2-btn md2-btn--sentence h-8 min-w-0 px-2 font-mono md2-body2"
                @click="copyEmail"
              >
                {{ emailCopied ? '已复制 ✓' : 'hello@snhgn.me' }}
              </button>
            </div>
            <div class="md2-divider" />
            <div class="md2-list-item justify-between">
              <span class="md2-list-item__sub">GitHub</span>
              <a
                href="https://github.com/snhgn"
                target="_blank"
                rel="noopener"
                class="md2-btn md2-btn--sentence h-8 min-w-0 px-2 md2-body2"
              >
                github.com/snhgn ↗
              </a>
            </div>
            <div class="md2-divider" />
            <div class="md2-list-item justify-between">
              <span class="md2-list-item__sub">Location</span>
              <span class="md2-list-item__title">Beijing, China</span>
            </div>
          </div>
        </section>

        <section class="md2-card p-5">
          <h2 class="md2-section-title mb-3">Node System</h2>
          <div class="space-y-2 font-mono md2-caption text-ink-secondary">
            <p>· Host: snhgn-primary (Ubuntu 22.04 LTS)</p>
            <p>· Network: Cloudflare Tunnel (Zero-Trust)</p>
            <p>· Core: FastAPI · Docker · Caddy</p>
          </div>
        </section>

      </div>

    </div>

  </div>
</template>
