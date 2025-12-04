/**
 * @file: ProcessingStatus.tsx
 * @description: Компонент отображения статуса обработки (загрузка, транскрибация).
 * @dependencies: react, store/videoStore
 * @created: 2025-11-17
 */

import type { ProcessingState } from '../store/videoStore'

const phaseLabels: Record<ProcessingState['phase'], string> = {
  idle: 'Ожидание действий',
  uploading: 'Загрузка видео',
  transcribing: 'Транскрибация',
  ready: 'Готово',
}

interface ProcessingStatusProps {
  state: ProcessingState
}

export function ProcessingStatus({ state }: ProcessingStatusProps) {
  const label = phaseLabels[state.phase] ?? 'Статус'
  const message = state.message ?? ''

  return (
    <div className="w-full max-w-2xl mx-auto p-4 bg-blue-50 border border-blue-100 rounded-lg shadow-sm">
      <div className="flex items-center gap-3">
        <div
          className={`h-3 w-3 rounded-full ${
            state.phase === 'ready'
              ? 'bg-green-500 animate-pulse'
              : state.phase === 'idle'
                ? 'bg-gray-400'
                : 'bg-blue-500 animate-pulse'
          }`}
        />
        <div>
          <p className="text-sm font-semibold text-blue-900">{label}</p>
          {message && <p className="text-xs text-blue-700 mt-1">{message}</p>}
        </div>
      </div>
    </div>
  )
}


