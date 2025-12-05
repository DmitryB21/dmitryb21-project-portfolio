/**
 * @file: videoStore.ts
 * @description: Zustand store для управления состоянием видео и обработки.
 * @dependencies: zustand
 * @created: 2025-01-XX
 */

import { create } from 'zustand'

export type ProcessingPhase = 'idle' | 'uploading' | 'transcribing' | 'ready'

export interface ProcessingState {
  phase: ProcessingPhase
  message?: string
}

interface VideoState {
  audioPath: string | null
  provider: string | null
  videoId: string | null
  videoTitle: string | null
  transcript: {
    id?: string
    text: string
    language: string
    model: string
    segments: Array<{ start: number; end: number; text: string }>
    durationSeconds?: number
  } | null
  summary: {
    id?: string
    title: string
    overview: string
    key_points: string[]
    quotes: Array<{ text: string; timestamp?: string }>
    recommendations: string[]
    tags: string[]
  } | null
  processing: ProcessingState
  setVideoSource: (params: { path: string; provider: string; videoId?: string | null; title?: string | null }) => void
  setTranscript: (transcript: VideoState['transcript']) => void
  setSummary: (summary: VideoState['summary']) => void
  setProcessing: (state: ProcessingState) => void
  reset: () => void
}

export const useVideoStore = create<VideoState>((set) => ({
  audioPath: null,
  provider: null,
  videoId: null,
  videoTitle: null,
  transcript: null,
  summary: null,
  processing: { phase: 'idle', message: 'Ожидание действий' },
  setVideoSource: ({ path, provider, videoId, title }) =>
    set({
      audioPath: path,
      provider,
      videoId: videoId ?? null,
      videoTitle: title ?? null,
    }),
  setTranscript: (transcript) => set({ transcript }),
  setSummary: (summary) => set({ summary }),
  setProcessing: (state) => set({ processing: state }),
  reset: () =>
    set({
      audioPath: null,
      provider: null,
      videoId: null,
      videoTitle: null,
      transcript: null,
      summary: null,
      processing: { phase: 'idle', message: 'Ожидание действий' },
    }),
}))

