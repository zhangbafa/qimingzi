<script setup lang="ts">
import { computed } from 'vue'
import type { DimensionScores } from '../types'

const props = defineProps<{
  dimensions: DimensionScores
}>()

const dimensions = computed(() => [
  { key: 'meaning', label: '寓意', value: props.dimensions.meaning },
  { key: 'tone', label: '音律', value: props.dimensions.tone },
  { key: 'style', label: '风格', value: props.dimensions.style },
  { key: 'readability', label: '易读', value: props.dimensions.readability },
  { key: 'length', label: '长度', value: props.dimensions.length },
  { key: 'repeat', label: '重复', value: props.dimensions.repeat },
  { key: 'ai', label: 'AI', value: props.dimensions.ai },
])

function scoreColor(v: number): string {
  if (v >= 0.8) return '#22c55e'
  if (v >= 0.6) return '#eab308'
  return '#ef4444'
}

function scoreLabel(v: number): string {
  if (v >= 0.8) return '优'
  if (v >= 0.6) return '良'
  return '一般'
}
</script>

<template>
  <div class="score-gauge">
    <div v-for="d in dimensions" :key="d.key" class="gauge-row">
      <span class="gauge-label">{{ d.label }}</span>
      <div class="gauge-track">
        <div
          class="gauge-fill"
          :style="{ width: `${d.value * 100}%`, backgroundColor: scoreColor(d.value) }"
        />
      </div>
      <span class="gauge-value" :style="{ color: scoreColor(d.value) }">
        {{ scoreLabel(d.value) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.score-gauge {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gauge-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gauge-label {
  width: 32px;
  font-size: 12px;
  color: #666;
  text-align: right;
  flex-shrink: 0;
}

.gauge-track {
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.gauge-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.gauge-value {
  width: 20px;
  font-size: 11px;
  font-weight: 600;
  text-align: center;
  flex-shrink: 0;
}
</style>
