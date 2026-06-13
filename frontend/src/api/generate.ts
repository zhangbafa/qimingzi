import type { GenerationConfig, GenerationResponse } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

export async function generateNames(config: GenerationConfig): Promise<GenerationResponse> {
  const res = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(
      Array.isArray(err.detail) ? err.detail.map((e: { msg: string }) => e.msg).join('; ') : err.detail
    )
  }

  return res.json()
}

export enum LoadingState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Error = 'error',
}
