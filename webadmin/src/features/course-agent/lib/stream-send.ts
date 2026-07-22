import type { Dispatch, SetStateAction } from 'react'
import type { CourseAgentMessage, CourseAgentSession } from '../data/types'

type StreamSendFn = (
  sessionId: string,
  content: string,
  handlers: {
    onDelta?: (text: string) => void
    onDone?: (session: CourseAgentSession) => void
  }
) => Promise<CourseAgentSession>

/**
 * 乐观插入用户消息；收到首个 delta 时再插入助手气泡并追加内容；结束后用服务端会话覆盖。
 */
export async function sendWithStreaming(options: {
  session: CourseAgentSession
  content: string
  setSession: Dispatch<SetStateAction<CourseAgentSession | null>>
  streamFn: StreamSendFn
}): Promise<void> {
  const { session, content, setSession, streamFn } = options
  const userId = `local-user-${Date.now()}`
  const assistantId = `local-assistant-${Date.now()}`
  const now = new Date().toISOString()
  let assistantCreated = false

  const optimisticUser: CourseAgentMessage = {
    id: userId,
    role: 'user',
    content,
    createdAt: now,
  }

  setSession((prev) =>
    prev
      ? {
          ...prev,
          messages: [...prev.messages, optimisticUser],
        }
      : prev
  )

  const ensureAssistant = () => {
    if (assistantCreated) return
    assistantCreated = true
    const optimisticAssistant: CourseAgentMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
    }
    setSession((prev) =>
      prev
        ? {
            ...prev,
            messages: [...prev.messages, optimisticAssistant],
          }
        : prev
    )
  }

  try {
    await streamFn(session.id, content, {
      onDelta: (text) => {
        ensureAssistant()
        setSession((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === assistantId
                ? { ...m, content: `${m.content}${text}` }
                : m
            ),
          }
        })
      },
      onDone: (updated) => {
        setSession(updated)
      },
    })
  } catch (e) {
    setSession((prev) =>
      prev
        ? {
            ...prev,
            messages: prev.messages.filter(
              (m) => m.id !== userId && m.id !== assistantId
            ),
          }
        : prev
    )
    throw e
  }
}
