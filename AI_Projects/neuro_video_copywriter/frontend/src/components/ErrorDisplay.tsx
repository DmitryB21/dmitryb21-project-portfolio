/**
 * @file: ErrorDisplay.tsx
 * @description: Компонент для отображения ошибок.
 * @dependencies: react
 * @created: 2025-01-XX
 */

interface ErrorDisplayProps {
  error: Error | string
  onDismiss?: () => void
}

export function ErrorDisplay({ error, onDismiss }: ErrorDisplayProps) {
  const message = typeof error === 'string' ? error : error.message

  return (
    <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md mb-4 flex justify-between items-start">
      <div>
        <p className="font-semibold">Ошибка</p>
        <p className="text-sm">{message}</p>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-red-600 hover:text-red-800 font-bold text-xl"
        >
          ×
        </button>
      )}
    </div>
  )
}

