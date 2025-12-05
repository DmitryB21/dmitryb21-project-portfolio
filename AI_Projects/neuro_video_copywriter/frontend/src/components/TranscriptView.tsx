/**
 * @file: TranscriptView.tsx
 * @description: Компонент для отображения транскрипта и выбора режима транскрибации.
 * @dependencies: react, transcriptionService
 * @created: 2025-01-XX
 */

import { useEffect, useState } from 'react'
import { transcriptionService, TranscribeRequest, TranscribeResponse } from '../services/transcriptionService'
import type { ProcessingState } from '../store/videoStore'

interface TranscriptViewProps {
  audioPath?: string
  videoId?: string | null
  transcriptData?: TranscribeResponse | null
  onTranscriptComplete?: (result: TranscribeResponse) => void
  onError?: (error: Error) => void
  onStatusChange?: (state: ProcessingState) => void
}

export function TranscriptView({
  audioPath,
  videoId,
  transcriptData,
  onTranscriptComplete,
  onError,
  onStatusChange,
}: TranscriptViewProps) {
  const [mode, setMode] = useState<'local' | 'online'>('local')
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<TranscribeResponse | null>(transcriptData ?? null)

  useEffect(() => {
    setTranscript(transcriptData ?? null)
  }, [transcriptData])

  const handleTranscribe = async () => {
    if (!audioPath) {
      onError?.(new Error('Audio path is required'))
      return
    }

    setLoading(true)
    onStatusChange?.({ phase: 'transcribing', message: 'Выполняем транскрибацию аудио...' })
    setStatusMessage('Транскрибируем аудио...')
    try {
      const request: TranscribeRequest = {
        audio_path: audioPath,
        mode,
        video_id: videoId ?? undefined,
      }

      const result = mode === 'local'
        ? await transcriptionService.transcribeLocal(request)
        : await transcriptionService.transcribeOnline(request)

      onTranscriptComplete?.(result)
      onStatusChange?.({ phase: 'ready', message: 'Транскрипт готов' })
      setStatusMessage('Транскрибация завершена')
    } catch (error) {
      onError?.(error as Error)
      onStatusChange?.({ phase: 'idle', message: 'Ошибка транскрибации' })
      setStatusMessage('Не удалось выполнить транскрибацию')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4 text-gray-800">Транскрибация</h2>

      {audioPath ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Режим транскрибации
            </label>
            <div className="flex gap-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="local"
                  checked={mode === 'local'}
                  onChange={(e) => setMode(e.target.value as 'local')}
                  className="mr-2"
                  disabled={loading}
                />
                Локальный (Whisper)
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="online"
                  checked={mode === 'online'}
                  onChange={(e) => setMode(e.target.value as 'online')}
                  className="mr-2"
                  disabled={loading}
                />
                Онлайн (OpenAI API)
              </label>
            </div>
          </div>

          <button
            onClick={handleTranscribe}
            disabled={loading}
            className="bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-md transition-colors"
          >
            {loading ? 'Транскрибирование...' : 'Начать транскрибацию'}
          </button>

          {statusMessage && (
            <p className="text-sm text-gray-600">{statusMessage}</p>
          )}

          {transcript && (
            <div className="mt-6 p-4 bg-gray-50 rounded-md">
              <div className="mb-4">
                <span className="text-sm text-gray-600">Язык: </span>
                <span className="font-semibold">{transcript.language}</span>
                <span className="text-sm text-gray-600 ml-4">Модель: </span>
                <span className="font-semibold">{transcript.model}</span>
                {transcript.duration_seconds && (
                  <>
                    <span className="text-sm text-gray-600 ml-4">Длительность: </span>
                    <span className="font-semibold">
                      {Math.floor(transcript.duration_seconds / 60)}:
                      {Math.floor(transcript.duration_seconds % 60).toString().padStart(2, '0')}
                    </span>
                  </>
                )}
              </div>
              <div className="prose max-w-none">
                <p className="whitespace-pre-wrap text-gray-800">{transcript.text}</p>
              </div>
              {transcript.segments.length > 0 && (
                <div className="mt-4">
                  <h3 className="font-semibold mb-2">Сегменты:</h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {transcript.segments.map((segment, idx) => (
                      <div key={idx} className="text-sm p-2 bg-white rounded border">
                        <span className="text-gray-500">
                          {Math.floor(segment.start / 60)}:
                          {Math.floor(segment.start % 60).toString().padStart(2, '0')}
                        </span>
                        <span className="ml-2">{segment.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="text-gray-500">Сначала загрузите видео и извлеките аудио</p>
      )}
    </div>
  )
}

