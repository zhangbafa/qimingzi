export type NameType = 'person' | 'company' | 'brand' | 'product'

export interface GenerationConfig {
  name_type: NameType
  surname?: string
  count?: number
  gender?: 'M' | 'F' | 'N'
  style?: string[]
  industry?: string[]
}

export interface DimensionScores {
  meaning: number
  tone: number
  style: number
  readability: number
  length: number
  repeat: number
  ai: number
}

export interface NameResult {
  name: string
  chars: string[]
  pinyin: string[]
  score: number
  dimensions: DimensionScores
  meaning: string
  story: string
}

export interface GenerationResponse {
  names: NameResult[]
  meta: {
    total_candidates: number
    generation_ms: number
    ai_ms: number
  }
}

export interface ApiError {
  detail: string | { msg: string }[]
}

export const NAME_TYPES: { value: NameType; label: string }[] = [
  { value: 'person', label: '人名' },
  { value: 'company', label: '公司名' },
  { value: 'brand', label: '品牌名' },
  { value: 'product', label: '产品名' },
]

export const STYLES: { value: string; label: string }[] = [
  { value: 'modern', label: '现代' },
  { value: 'chinese', label: '国风' },
  { value: 'tech', label: '科技' },
  { value: 'luxury', label: '奢华' },
  { value: 'minimal', label: '简约' },
  { value: 'literary', label: '文雅' },
  { value: 'natural', label: '自然' },
  { value: 'vibrant', label: '活力' },
]

export const INDUSTRIES: { value: string; label: string }[] = [
  { value: 'technology', label: '科技' },
  { value: 'ai', label: '人工智能' },
  { value: 'internet', label: '互联网' },
  { value: 'finance', label: '金融' },
  { value: 'education', label: '教育' },
  { value: 'medical', label: '医疗' },
  { value: 'culture', label: '文化传媒' },
  { value: 'environment', label: '环保能源' },
  { value: 'general', label: '综合' },
]

export const GENDERS: { value: 'M' | 'F' | 'N'; label: string }[] = [
  { value: 'M', label: '男' },
  { value: 'F', label: '女' },
  { value: 'N', label: '不限' },
]
