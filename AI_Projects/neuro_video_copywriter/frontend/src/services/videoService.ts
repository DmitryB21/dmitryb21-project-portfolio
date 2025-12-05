/**
 * @file: videoService.ts
 * @description: Сервис для работы с видео API.
 * @dependencies: api.ts
 * @created: 2025-01-XX
 */

import { apiClient } from './api'

export interface VideoExtractRequest {
  video_url: string
  provider?: 'auto' | 'youtube' | 'vk' | 'rutube'
  request_id?: string
  options?: {
    audio_format?: string
    sample_rate?: number
  }
  metadata?: Record<string, any>
}

export interface VideoExtractResponse {
  video_id?: string
  audio_path: string
  provider: string
  metadata: Record<string, any>
}

export interface VideoHistoryItem {
  id: string
  title?: string | null
  source_url: string
  provider: string
  status: string
  audio_path?: string | null
  created_at: string
  has_transcript: boolean
  has_summary: boolean
}

export interface VideoListResponse {
  items: VideoHistoryItem[]
}

export interface StoredTranscript {
  id: string
  language: string
  text: string
  model?: string
  created_at: string
  segments: Array<{ start: number; end: number; text: string }>
}

export interface StoredSummary {
  id: string
  title: string
  structure: {
    title: string
    overview: string
    key_points: string[]
    quotes: Array<{ text: string; timestamp?: string }>
    recommendations: string[]
    tags: string[]
  }
  model?: string
  created_at: string
}

export interface VideoDetailResponse {
  id: string
  title?: string | null
  source_url: string
  provider: string
  status: string
  audio_path?: string | null
  created_at: string
  transcript?: StoredTranscript | null
  summary?: StoredSummary | null
}

export const videoService = {
  /**
   * Загружает видео и извлекает аудио.
   */
  async extractAudio(request: VideoExtractRequest): Promise<VideoExtractResponse> {
    return apiClient.post<VideoExtractResponse>('/api/video/extract', request)
  },

  /**
   * Возвращает историю загруженных видео.
   */
  async listVideos(limit = 50): Promise<VideoListResponse> {
    return apiClient.get<VideoListResponse>('/api/videos', { params: { limit } })
  },

  /**
   * Возвращает детальную информацию по видео.
   */
  async getVideoDetail(videoId: string): Promise<VideoDetailResponse> {
    return apiClient.get<VideoDetailResponse>(`/api/videos/${videoId}`)
  },

  /**
   * Удаляет видео и связанные данные.
   */
  async deleteVideo(videoId: string): Promise<void> {
    await apiClient.delete(`/api/videos/${videoId}`)
  },
}

