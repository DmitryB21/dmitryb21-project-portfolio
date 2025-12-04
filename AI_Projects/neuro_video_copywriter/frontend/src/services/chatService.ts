/**
 * @file: chatService.ts
 * @description: Сервис для работы с чат-консультантом API.
 * @dependencies: api.ts
 * @created: 2025-01-XX
 */

import { apiClient } from './api'

export interface ChatRequest {
  question: string
  video_id?: string
  top_k?: number
  language?: string
}

export interface ChatSource {
  text: string
  score: number
  video_id?: string
  transcript_id?: string
  timestamp?: string
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  model: string
}

export const chatService = {
  /**
   * Отправляет вопрос чат-консультанту.
   */
  async askQuestion(request: ChatRequest): Promise<ChatResponse> {
    return apiClient.post<ChatResponse>('/api/chat', request)
  },
}

