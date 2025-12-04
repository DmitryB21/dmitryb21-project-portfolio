/**
 * @file: VideoInput.tsx
 * @description: Компонент для ввода URL видео и выбора провайдера.
 * @dependencies: react, videoService
 * @created: 2025-01-XX
 */

import { useState } from 'react'
import { videoService, VideoExtractRequest, VideoExtractResponse } from '../services/videoService'
import type { ProcessingState } from '../store/videoStore'

interface VideoInputProps {
  onExtractComplete?: (result: VideoExtractResponse) => void
  onError?: (error: Error) => void
  onStatusChange?: (state: ProcessingState) => void
  onHistoryRefresh?: () => void
}

export function VideoInput({ onExtractComplete, onError, onStatusChange, onHistoryRefresh }: VideoInputProps) {
  const [url, setUrl] = useState('')
  const [provider, setProvider] = useState<'auto' | 'youtube' | 'vk' | 'rutube'>('auto')
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    onStatusChange?.({ phase: 'uploading', message: 'Загрузка видео и извлечение аудио...' })
    setStatusMessage('Загружаем и сохраняем аудио...')
    try {
      const request: VideoExtractRequest = {
        video_url: url,
        provider,
      }
      const result = await videoService.extractAudio(request)
      onExtractComplete?.(result)
      onHistoryRefresh?.()
      onStatusChange?.({ phase: 'ready', message: 'Аудио извлечено. Можно запускать транскрибацию.' })
      setStatusMessage('Аудио успешно извлечено')
      setUrl('') // Очищаем поле после успешной загрузки
    } catch (error) {
      onError?.(error as Error)
      onStatusChange?.({ phase: 'idle', message: 'Ошибка загрузки видео' })
      setStatusMessage('Не удалось загрузить видео')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4 text-gray-800">Загрузка видео</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="video-url" className="block text-sm font-medium text-gray-700 mb-2">
            URL видео
          </label>
          <input
            id="video-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
            disabled={loading}
          />
        </div>

        <div>
          <label htmlFor="provider" className="block text-sm font-medium text-gray-700 mb-2">
            Провайдер
          </label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as any)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          >
            <option value="auto">Автоопределение</option>
            <option value="youtube">YouTube</option>
            <option value="vk">VK</option>
            <option value="rutube">RuTube</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-md transition-colors"
        >
          {loading ? 'Загрузка...' : 'Загрузить и извлечь аудио'}
        </button>

        {statusMessage && (
          <p className="text-sm text-gray-600 text-center">{statusMessage}</p>
        )}
      </form>
    </div>
  )
}

