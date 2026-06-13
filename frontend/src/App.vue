<script setup lang="ts">
import { ref, shallowRef } from 'vue'
import NameGenerator from './components/NameGenerator.vue'
import NameResult from './components/NameResult.vue'
import { generateNames } from './api/generate'
import type { GenerationConfig, NameResult as NameResultType } from './types'

const state = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
const errorMsg = ref('')
const results = shallowRef<NameResultType[]>([])
const meta = shallowRef<{ total_candidates: number; generation_ms: number; ai_ms: number } | null>(null)

async function handleGenerate(config: GenerationConfig) {
  state.value = 'loading'
  errorMsg.value = ''
  results.value = []
  meta.value = null

  try {
    const resp = await generateNames(config)
    results.value = resp.names
    meta.value = resp.meta
    state.value = 'success'
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '请求失败'
    state.value = 'error'
  }
}

function back() {
  state.value = 'idle'
  results.value = []
  meta.value = null
}

function exportCSV() {
  const rows = results.value.map((r, i) => [
    i + 1, r.name, r.pinyin.join(' '), r.score,
    r.dimensions.meaning, r.dimensions.tone, r.dimensions.style,
    r.dimensions.readability, r.dimensions.length, r.dimensions.repeat,
    `"${(r.meaning || '').replace(/"/g, '""')}"`,
  ])

  const header = '序号,名字,拼音,总分,寓意,音律,风格,易读,长度,重复,AI解释'
  const csv = '\uFEFF' + [header, ...rows.map(r => r.join(','))].join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `起名结果_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="app">
    <template v-if="state === 'idle'">
      <NameGenerator @generate="handleGenerate" />
    </template>

    <template v-else>
      <div class="results-header">
        <button class="back-btn" @click="back">← 返回</button>
        <span v-if="meta" class="meta-info">
          从 {{ meta.total_candidates }} 个候选中选出
          <span v-if="meta.ai_ms > 0"> · AI 解释 {{ meta.ai_ms }}ms</span>
        </span>
        <button v-if="state === 'success' && results.length" class="export-btn" @click="exportCSV">
          导出 CSV
        </button>
      </div>

      <div v-if="state === 'loading'" class="loading-state">
        <div class="spinner" />
        <p>正在生成名字...</p>
      </div>

      <div v-else-if="state === 'error'" class="error-state">
        <p>{{ errorMsg }}</p>
        <button class="retry-btn" @click="back">重新设置</button>
      </div>

      <div v-else-if="state === 'success'" class="results-list">
        <div v-if="!results.length" class="empty-state">
          <p>没有找到符合条件的结果</p>
          <button class="retry-btn" @click="back">调整参数</button>
        </div>
        <NameResult
          v-for="(r, i) in results"
          :key="r.name + i"
          :result="r"
          :index="i"
        />
      </div>
    </template>
  </div>
</template>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  background: #f5f5f7;
  color: #111;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app {
  min-height: 100dvh;
  max-width: 480px;
  margin: 0 auto;
  background: #f5f5f7;
}
</style>

<style scoped>
.results-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  position: sticky;
  top: 0;
  background: #f5f5f7;
  z-index: 10;
}

.back-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: white;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.export-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: #22c55e;
  font-size: 13px;
  color: white;
  cursor: pointer;
  white-space: nowrap;
}

.meta-info {
  font-size: 12px;
  color: #999;
  flex: 1;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 16px;
  color: #999;
  gap: 16px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  text-align: center;
  padding: 40px 16px;
  color: #ef4444;
}

.retry-btn {
  margin-top: 12px;
  padding: 8px 24px;
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: white;
  font-size: 14px;
  cursor: pointer;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px 24px;
}

.empty-state {
  text-align: center;
  padding: 40px 16px;
  color: #999;
}
</style>
