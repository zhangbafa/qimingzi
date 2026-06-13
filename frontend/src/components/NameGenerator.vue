<script setup lang="ts">
import { reactive } from 'vue'
import { NAME_TYPES, STYLES, INDUSTRIES, GENDERS } from '../types'
import type { NameType } from '../types'

const emit = defineEmits<{
  (e: 'generate', config: {
    name_type: NameType
    surname?: string
    count: number
    gender?: 'M' | 'F' | 'N'
    style?: string[]
    industry?: string[]
  }): void
}>()

const form = reactive({
  nameType: 'person' as NameType,
  surname: '',
  count: 3,
  gender: 'N' as 'M' | 'F' | 'N',
  styles: [] as string[],
  industries: [] as string[],
})

function toggleStyle(val: string) {
  const i = form.styles.indexOf(val)
  if (i >= 0) form.styles.splice(i, 1)
  else if (form.styles.length < 3) form.styles.push(val)
}

function toggleIndustry(val: string) {
  const i = form.industries.indexOf(val)
  if (i >= 0) form.industries.splice(i, 1)
  else form.industries.push(val)
}

function submit() {
  emit('generate', {
    name_type: form.nameType,
    surname: form.surname ? form.surname.trim() : undefined,
    count: form.count,
    gender: form.gender === 'N' ? undefined : form.gender,
    style: form.styles.length ? form.styles : undefined,
    industry: form.nameType !== 'person' && form.industries.length ? form.industries : undefined,
  })
}

function onSurnameInput(e: Event) {
  const el = e.target as HTMLInputElement
  form.surname = el.value.replace(/[^\u4e00-\u9fff]/g, '').slice(0, 2)
}

const countOptions = [1, 3, 5, 10]
</script>

<template>
  <div class="generator">
    <h1 class="title">起名</h1>
    <p class="subtitle">智能中文命名系统</p>

    <div class="form-group">
      <label class="form-label">命名类型</label>
      <div class="chip-group">
        <button
          v-for="t in NAME_TYPES"
          :key="t.value"
          class="chip"
          :class="{ active: form.nameType === t.value }"
          @click="form.nameType = t.value"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <div v-if="form.nameType === 'person'" class="form-group">
      <label class="form-label">性别倾向</label>
      <div class="chip-group">
        <button
          v-for="g in GENDERS"
          :key="g.value"
          class="chip"
          :class="{ active: form.gender === g.value }"
          @click="form.gender = g.value"
        >
          {{ g.label }}
        </button>
      </div>
    </div>

    <div v-if="form.nameType === 'person'" class="form-group">
      <label class="form-label">姓氏 (可选)</label>
      <input
        class="surname-input"
        type="text"
        :value="form.surname"
        @input="onSurnameInput"
        placeholder="输入姓氏，如：张、王、李"
        maxlength="2"
      />
      <p v-if="form.surname" class="surname-hint">
        生成的名字将包含姓氏：<strong>{{ form.surname }}___</strong>
      </p>
    </div>

    <div class="form-group">
      <label class="form-label">风格 (可选 {{ form.styles.length }}/3)</label>
      <div class="chip-group">
        <button
          v-for="s in STYLES"
          :key="s.value"
          class="chip"
          :class="{ active: form.styles.includes(s.value) }"
          @click="toggleStyle(s.value)"
        >
          {{ s.label }}
        </button>
      </div>
    </div>

    <div v-if="form.nameType !== 'person'" class="form-group">
      <label class="form-label">行业 (可选)</label>
      <div class="chip-group">
        <button
          v-for="ind in INDUSTRIES"
          :key="ind.value"
          class="chip"
          :class="{ active: form.industries.includes(ind.value) }"
          @click="toggleIndustry(ind.value)"
        >
          {{ ind.label }}
        </button>
      </div>
    </div>

    <div class="form-group">
      <label class="form-label">生成数量</label>
      <div class="chip-group">
        <button
          v-for="n in countOptions"
          :key="n"
          class="chip"
          :class="{ active: form.count === n }"
          @click="form.count = n"
        >
          {{ n }} 个
        </button>
      </div>
    </div>

    <button class="generate-btn" @click="submit">
      开始起名
    </button>
  </div>
</template>

<style scoped>
.generator {
  padding: 24px 16px;
  max-width: 400px;
  margin: 0 auto;
}

.title {
  font-size: 28px;
  font-weight: 800;
  text-align: center;
  color: #111;
  margin: 0 0 2px;
  letter-spacing: 4px;
}

.subtitle {
  text-align: center;
  font-size: 13px;
  color: #999;
  margin: 0 0 28px;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 6px 14px;
  border: 1.5px solid #e5e7eb;
  border-radius: 20px;
  background: white;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
  -webkit-tap-highlight-color: transparent;
}

.chip.active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #3b82f6;
  font-weight: 600;
}

.surname-input {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid #e5e7eb;
  border-radius: 10px;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s;
  letter-spacing: 2px;
}

.surname-input:focus {
  border-color: #3b82f6;
}

.surname-input::placeholder {
  color: #bbb;
  font-size: 13px;
  letter-spacing: 0;
}

.surname-hint {
  font-size: 12px;
  color: #999;
  margin-top: 6px;
}

.generate-btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  color: white;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
  letter-spacing: 2px;
  margin-top: 8px;
}

.generate-btn:active {
  opacity: 0.8;
}
</style>
