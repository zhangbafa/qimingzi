<script setup lang="ts">
import type { NameResult as NameResultType } from '../types'
import ScoreGauge from './ScoreGauge.vue'

defineProps<{
  result: NameResultType
  index: number
}>()

const emit = defineEmits<{
  (e: 'regenerate'): void
}>()

function totalColor(score: number): string {
  if (score >= 80) return '#22c55e'
  if (score >= 65) return '#eab308'
  return '#ef4444'
}
</script>

<template>
  <div class="name-result" :style="{ animationDelay: `${index * 0.1}s` }">
    <div class="name-header">
      <div class="name-display">
        <span class="name-text">{{ result.name }}</span>
        <span class="name-pinyin">{{ result.pinyin.join(' ') }}</span>
      </div>
      <div class="score-badge" :style="{ backgroundColor: totalColor(result.score) }">
        {{ result.score }}
      </div>
    </div>

    <div v-if="result.meaning" class="name-meaning">
      {{ result.meaning }}
    </div>

    <div v-if="result.story" class="name-story">
      {{ result.story }}
    </div>

    <ScoreGauge :dimensions="result.dimensions" />
  </div>
</template>

<style scoped>
.name-result {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  animation: slideUp 0.3s ease both;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.name-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.name-display {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name-text {
  font-size: 24px;
  font-weight: 700;
  color: #111;
  letter-spacing: 2px;
}

.name-pinyin {
  font-size: 12px;
  color: #999;
}

.score-badge {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.name-meaning,
.name-story {
  font-size: 13px;
  color: #555;
  line-height: 1.5;
  margin-bottom: 8px;
  padding: 8px 10px;
  background: #f9fafb;
  border-radius: 8px;
}
</style>
