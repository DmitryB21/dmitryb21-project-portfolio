/**
 * @file: transcriptionService.ts
 * @description: Сервис для работы с транскрибацией API.
 * @dependencies: api.ts
 * @created: 2025-01-XX
 */

import { apiClient } from './api'

export interface TranscriptionSegment {
  start: number
  end: number
  text: string
}

export interface TranscribeRequest {
  audio_path: string
  mode?: 'local' | 'online'
  local_options?: {
    model?: string
    language?: string
    task?: string
    temperature?: number
  }
  api_options?: {
    model?: string
    language?: string
    prompt?: string
    response_format?: string
    temperature?: number
  }
  video_id?: string
}

export interface TranscribeResponse {
  text: string
  language: string
  segments: TranscriptionSegment[]
  model: string
  duration_seconds?: number
  transcript_id?: string
}

export const transcriptionService = {
  /**
   * Локальная транскрибация через Whisper.
   */
  async transcribeLocal(request: TranscribeRequest): Promise<TranscribeResponse> {
    return apiClient.post<TranscribeResponse>(
      '/api/transcribe/local',
      {
        ...request,
        mode: 'local',
      },
      {
        timeout: 1200000, // 20 минут для больших файлов
      }
    )
  },

  /**
   * Транскрибация через OpenAI API.
   */
  async transcribeOnline(request: TranscribeRequest): Promise<TranscribeResponse> {
    return apiClient.post<TranscribeResponse>(
      '/api/transcribe/online',
      {
        ...request,
        mode: 'online',
      },
      {
        timeout: 1200000, // 20 минут для больших файлов и chunking
      }
    )
  },
}

