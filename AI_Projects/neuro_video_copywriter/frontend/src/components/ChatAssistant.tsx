/**
 * @file: ChatAssistant.tsx
 * @description: Компонент чат-консультанта с контекстом лекции.
 * @dependencies: react, chatService
 * @created: 2025-01-XX
 */

import { useState } from 'react'
import { chatService, ChatRequest, ChatResponse } from '../services/chatService'

interface ChatAssistantProps {
  videoId?: string
  onError?: (error: Error) => void
}

export function ChatAssistant({ videoId, onError }: ChatAssistantProps) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Array<{ question: string; answer: string; sources?: any[] }>>([])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || loading) return

    const userQuestion = question
    setQuestion('')
    setLoading(true)

    // Добавляем вопрос пользователя
    setMessages((prev) => [...prev, { question: userQuestion, answer: '' }])

    try {
      const request: ChatRequest = {
        question: userQuestion,
        video_id: videoId,
        top_k: 5,
        language: 'ru',
      }

      const response = await chatService.askQuestion(request)

      // Обновляем последнее сообщение с ответом
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          question: userQuestion,
          answer: response.answer,
          sources: response.sources,
        }
        return updated
      })
    } catch (error) {
      onError?.(error as Error)
      // Удаляем последнее сообщение при ошибке
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-md flex flex-col h-[600px]">
      <h2 className="text-2xl font-bold mb-4 text-gray-800">Чат-консультант</h2>

      <div className="flex-1 overflow-y-auto mb-4 space-y-4">
        {messages.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            Задайте вопрос о содержании лекции
          </p>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className="space-y-2">
              <div className="bg-blue-50 p-3 rounded-md">
                <p className="font-semibold text-blue-800 mb-1">Вы:</p>
                <p className="text-gray-800">{msg.question}</p>
              </div>
              {msg.answer && (
                <div className="bg-green-50 p-3 rounded-md">
                  <p className="font-semibold text-green-800 mb-1">Консультант:</p>
                  <p className="text-gray-800 whitespace-pre-wrap">{msg.answer}</p>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2 text-xs text-gray-600">
                      <p className="font-semibold">Источники:</p>
                      {msg.sources.map((source, sidx) => (
                        <div key={sidx} className="mt-1 p-2 bg-white rounded border">
                          {source.timestamp && (
                            <span className="text-gray-500">[{source.timestamp}] </span>
                          )}
                          <span className="text-gray-700">{source.text.substring(0, 100)}...</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
        {loading && (
          <div className="bg-gray-50 p-3 rounded-md">
            <p className="text-gray-500 italic">Думаю...</p>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Задайте вопрос о лекции..."
          className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-md transition-colors"
        >
          Отправить
        </button>
      </form>
    </div>
  )
}

