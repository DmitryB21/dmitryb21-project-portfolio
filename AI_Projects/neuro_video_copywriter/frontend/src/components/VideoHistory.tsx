/**
 * @file: VideoHistory.tsx
 * @description: Список ранее загруженных видео с возможностью переиспользовать аудио.
 * @dependencies: react, videoService
 * @created: 2025-11-17
 */

import type { VideoHistoryItem } from '../services/videoService'

interface VideoHistoryProps {
  videos: VideoHistoryItem[]
  loading?: boolean
  onRefresh?: () => void
  onSelect?: (item: VideoHistoryItem) => void
  onDelete?: (item: VideoHistoryItem) => void
}

export function VideoHistory({ videos, loading = false, onRefresh, onSelect, onDelete }: VideoHistoryProps) {
  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-800">Сохранённые видео</h2>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="text-sm px-3 py-1 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          Обновить
        </button>
      </div>

      {videos.length === 0 ? (
        <p className="text-gray-500">Пока нет загруженных видео. Добавьте новое через форму выше.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">Название</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">Провайдер</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">Дата</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">Статус</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600">Артефакты</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-600" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {videos.map((video) => (
                <tr key={video.id}>
                  <td className="px-4 py-2">
                    <div className="font-medium text-gray-900">
                      {video.title || 'Без названия'}
                    </div>
                    <div className="text-xs text-gray-500 truncate max-w-xs">
                      {video.source_url}
                    </div>
                  </td>
                  <td className="px-4 py-2 capitalize">{video.provider}</td>
                  <td className="px-4 py-2 text-gray-600">
                    {new Date(video.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700">
                      {video.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-2 text-xs">
                      <span
                        className={`px-2 py-1 rounded-full ${
                          video.has_transcript ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        Транскрипт
                      </span>
                      <span
                        className={`px-2 py-1 rounded-full ${
                          video.has_summary ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        Методичка
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        disabled={!video.audio_path}
                        onClick={() => onSelect?.(video)}
                        className="text-sm px-3 py-1 rounded bg-green-500 text-white hover:bg-green-600 disabled:bg-gray-300"
                      >
                        Использовать
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete?.(video)}
                        className="text-sm px-3 py-1 rounded bg-red-500 text-white hover:bg-red-600"
                      >
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}


