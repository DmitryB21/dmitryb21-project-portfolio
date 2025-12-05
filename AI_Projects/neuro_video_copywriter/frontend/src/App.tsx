/**
 * @file: App.tsx
 * @description: Главный компонент приложения с интеграцией всех сервисов.
 * @dependencies: react, components, services
 * @created: 2025-01-XX
 */

import { useCallback, useEffect, useState } from 'react'
import { ErrorDisplay } from './components/ErrorDisplay'
import { VideoInput } from './components/VideoInput'
import { TranscriptView } from './components/TranscriptView'
import { SummaryCard } from './components/SummaryCard'
import { ChatAssistant } from './components/ChatAssistant'
import { ProcessingStatus } from './components/ProcessingStatus'
import { VideoHistory } from './components/VideoHistory'
import { useVideoStore } from './store/videoStore'
import type { TranscribeResponse } from './services/transcriptionService'
import type { SummaryResponse } from './services/summaryService'
import type { VideoHistoryItem, VideoExtractResponse } from './services/videoService'
import { videoService } from './services/videoService'

function App() {
  const {
    audioPath,
    videoId,
    transcript,
    summary,
    processing,
    setVideoSource,
    setTranscript,
    setSummary,
    setProcessing,
    reset,
  } = useVideoStore()
  const [error, setError] = useState<Error | null>(null)
  const [history, setHistory] = useState<VideoHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const handleError = useCallback((err: Error) => {
    setError(err)
    console.error('Error:', err)
  }, [])

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const response = await videoService.listVideos()
      setHistory(response.items)
    } catch (err) {
      handleError(err as Error)
    } finally {
      setHistoryLoading(false)
    }
  }, [handleError])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const handleExtractComplete = (result: VideoExtractResponse) => {
    setVideoSource({
      path: result.audio_path,
      provider: result.provider,
      videoId: result.video_id ?? null,
      title: typeof result.metadata?.title === 'string' ? result.metadata.title : null,
    })
    loadHistory()
    setError(null)
  }

  const handleTranscriptComplete = (result: TranscribeResponse) => {
    setTranscript({
      id: result.transcript_id ?? undefined,
      text: result.text,
      language: result.language,
      model: result.model,
      segments: result.segments,
      durationSeconds: result.duration_seconds,
    })
    loadHistory()
    setError(null)
  }

  const handleSummaryComplete = (result: SummaryResponse) => {
    setSummary({
      id: result.summary_id ?? undefined,
      title: result.structure.title,
      overview: result.structure.overview,
      key_points: result.structure.key_points,
      quotes: result.structure.quotes,
      recommendations: result.structure.recommendations,
      tags: result.structure.tags,
    })
    setError(null)
  }

  const handleHistorySelect = useCallback(
    async (video: VideoHistoryItem) => {
      if (!video.audio_path) {
        handleError(new Error('У записи отсутствует путь к аудиофайлу'))
        return
      }
      setVideoSource({
        path: video.audio_path,
        provider: video.provider,
        videoId: video.id,
        title: video.title ?? null,
      })
      setProcessing({
        phase: 'transcribing',
        message: 'Загружаем сохранённые данные...',
      })
      try {
        const details = await videoService.getVideoDetail(video.id)
        if (details.transcript) {
          setTranscript({
            id: details.transcript.id,
            text: details.transcript.text,
            language: details.transcript.language,
            model: details.transcript.model ?? 'unknown',
            segments: details.transcript.segments,
          })
        } else {
          setTranscript(null)
        }

        if (details.summary) {
          setSummary({
            id: details.summary.id,
            title: details.summary.structure.title,
            overview: details.summary.structure.overview,
            key_points: details.summary.structure.key_points,
            quotes: details.summary.structure.quotes,
            recommendations: details.summary.structure.recommendations,
            tags: details.summary.structure.tags,
          })
        } else {
          setSummary(null)
        }

        setProcessing({
          phase: 'ready',
          message: `Загружены сохранённые данные${video.title ? `: ${video.title}` : ''}`,
        })
        setError(null)
      } catch (err) {
        handleError(err as Error)
        setProcessing({
          phase: 'idle',
          message: 'Не удалось загрузить сохранённые данные',
        })
      }
    },
    [handleError, setProcessing, setSummary, setTranscript, setVideoSource],
  )

  const handleDeleteVideo = useCallback(
    async (video: VideoHistoryItem) => {
      const confirmed = window.confirm(`Удалить запись "${video.title || video.source_url}" и связанные данные?`)
      if (!confirmed) {
        return
      }
      try {
        await videoService.deleteVideo(video.id)
        if (videoId === video.id) {
          reset()
        }
        await loadHistory()
        setProcessing({ phase: 'idle', message: 'Видео удалено' })
      } catch (err) {
        handleError(err as Error)
      }
    },
    [handleError, loadHistory, reset, setProcessing, videoId],
  )

  const transcriptViewData = transcript
    ? {
        text: transcript.text,
        language: transcript.language,
        model: transcript.model,
        segments: transcript.segments,
        duration_seconds: transcript.durationSeconds,
        transcript_id: transcript.id,
      }
    : null

  const summaryCardData = summary
    ? {
        structure: {
          title: summary.title,
          overview: summary.overview,
          key_points: summary.key_points,
          quotes: summary.quotes,
          recommendations: summary.recommendations,
          tags: summary.tags,
        },
        model: 'stored',
        summary_id: summary.id,
      }
    : null

  return (
    <div className="min-h-screen bg-gray-100 py-8">
      <div className="container mx-auto px-4">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">
            Neuro Video Copywriter
          </h1>
          <p className="text-gray-600">
            Обработка видео, транскрибация и AI-функционал
          </p>
        </header>

        {error && (
          <div className="max-w-4xl mx-auto mb-6">
            <ErrorDisplay error={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <div className="mb-6">
          <ProcessingStatus state={processing} />
        </div>

        <div className="space-y-8">
          {/* Шаг 1: Загрузка видео */}
          <VideoInput
            onExtractComplete={handleExtractComplete}
            onError={handleError}
            onStatusChange={setProcessing}
            onHistoryRefresh={loadHistory}
          />

          {/* История загрузок */}
          <VideoHistory
            videos={history}
            loading={historyLoading}
            onRefresh={loadHistory}
            onSelect={handleHistorySelect}
            onDelete={handleDeleteVideo}
          />

          {/* Шаг 2: Транскрибация */}
          {audioPath && (
            <TranscriptView
              audioPath={audioPath}
              videoId={videoId}
              transcriptData={transcriptViewData}
              onTranscriptComplete={handleTranscriptComplete}
              onError={handleError}
              onStatusChange={setProcessing}
            />
          )}

          {/* Шаг 3: Методичка */}
          {transcript && (
            <SummaryCard
              transcriptText={transcript.text}
              videoTitle={transcript ? transcript.text : undefined}
              videoId={videoId ?? undefined}
              summaryData={summaryCardData}
              onSummaryComplete={handleSummaryComplete}
              onError={handleError}
            />
          )}

          {/* Шаг 4: Чат-консультант */}
          {transcript && (
            <ChatAssistant videoId={videoId ?? undefined} onError={handleError} />
          )}
        </div>
      </div>
    </div>
  )
}

export default App
