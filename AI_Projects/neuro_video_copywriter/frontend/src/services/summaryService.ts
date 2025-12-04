/**
 * @file: summaryService.ts
 * @description: Сервис для работы с генерацией методички API.
 * @dependencies: api.ts
 * @created: 2025-01-XX
 */

import { apiClient } from './api'

export interface SummaryQuote {
  text: string
  timestamp?: string
}

export interface SummaryStructure {
  title: string
  overview: string
  key_points: string[]
  quotes: SummaryQuote[]
  recommendations: string[]
  tags: string[]
}

export interface SummaryRequest {
  transcript_text: string
  video_title?: string
  video_id?: string
  options?: {
    model?: string
    temperature?: number
    max_tokens?: number
    language?: string
  }
}

export interface SummaryResponse {
  structure: SummaryStructure
  model: string
  summary_id?: string
}

export const summaryService = {
  /**
   * Генерирует методичку из транскрипта.
   */
  async generateSummary(request: SummaryRequest): Promise<SummaryResponse> {
    return apiClient.post<SummaryResponse>('/api/summary', request)
  },
}

