/**
 * @file: SummaryCard.tsx
 * @description: Компонент для отображения методички и генерации из транскрипта.
 * @dependencies: react, summaryService
 * @created: 2025-01-XX
 */

import { useEffect, useState } from 'react'
import { summaryService, SummaryRequest, SummaryResponse } from '../services/summaryService'

interface SummaryCardProps {
  transcriptText?: string
  videoTitle?: string
  videoId?: string | null
  summaryData?: SummaryResponse | null
  onSummaryComplete?: (result: SummaryResponse) => void
  onError?: (error: Error) => void
}

export function SummaryCard({
  transcriptText,
  videoTitle,
  videoId,
  summaryData,
  onSummaryComplete,
  onError,
}: SummaryCardProps) {
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<SummaryResponse | null>(summaryData ?? null)

  useEffect(() => {
    setSummary(summaryData ?? null)
  }, [summaryData])

  const handleGenerate = async () => {
    if (!transcriptText || !transcriptText.trim()) {
      onError?.(new Error('Transcript text is required'))
      return
    }

    setLoading(true)
    try {
      const request: SummaryRequest = {
        transcript_text: transcriptText,
        video_title: videoTitle,
        video_id: videoId ?? undefined,
      }

      const result = await summaryService.generateSummary(request)
      setSummary(result)
      onSummaryComplete?.(result)
    } catch (error) {
      onError?.(error as Error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4 text-gray-800">Методичка</h2>

      {transcriptText ? (
        <div className="space-y-4">
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="bg-purple-500 hover:bg-purple-600 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-md transition-colors"
          >
            {loading ? 'Генерация методички...' : 'Сгенерировать методичку'}
          </button>

      {summary && (
            <div className="mt-6 space-y-6">
              <div className="border-b pb-4">
                <h3 className="text-xl font-bold text-gray-800">{summary.structure.title}</h3>
                <p className="mt-2 text-gray-600">{summary.structure.overview}</p>
              </div>

              {summary.structure.key_points.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">Ключевые тезисы:</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {summary.structure.key_points.map((point, idx) => (
                      <li key={idx} className="text-gray-700">{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {summary.structure.quotes.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">Важные цитаты:</h4>
                  <div className="space-y-2">
                    {summary.structure.quotes.map((quote, idx) => (
                      <blockquote
                        key={idx}
                        className="border-l-4 border-blue-500 pl-4 py-2 bg-gray-50 italic text-gray-700"
                      >
                        {quote.timestamp && (
                          <span className="text-sm text-gray-500 mr-2">[{quote.timestamp}]</span>
                        )}
                        {quote.text}
                      </blockquote>
                    ))}
                  </div>
                </div>
              )}

              {summary.structure.recommendations.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">Рекомендации:</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {summary.structure.recommendations.map((rec, idx) => (
                      <li key={idx} className="text-gray-700">{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {summary.structure.tags.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">Теги:</h4>
                  <div className="flex flex-wrap gap-2">
                    {summary.structure.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="text-gray-500">Сначала выполните транскрибацию</p>
      )}
    </div>
  )
}

