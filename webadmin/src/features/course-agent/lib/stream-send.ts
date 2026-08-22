import type { Dispatch, SetStateAction } from 'react'
import type {
  CourseAgentMessage,
  CourseAgentSession,
  CourseAgentTraceEvent,
} from '../data/types'

type StreamSendFn = (
  sessionId: string,
  content: string,
  handlers: {
    onDelta?: (text: string) => void
    onTrace?: (event: CourseAgentTraceEvent) => void
    onDone?: (session: CourseAgentSession) => void
  }
) => Promise<CourseAgentSession>

function lastAssistantContent(messages: CourseAgentMessage[] | undefined) {
  if (!messages?.length) return ''
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i]?.role === 'assistant') return messages[i]?.content ?? ''
  }
  return ''
}

/** 服务端收尾会话若丢了刚流式出来的回复，保留本地已展示内容。 */
export function mergeStreamedSession(
  prev: CourseAgentSession | null,
  updated: CourseAgentSession
): CourseAgentSession {
  const serverText = lastAssistantContent(updated.messages)
  const localText = lastAssistantContent(prev?.messages)
  if (localText && localText.length > serverText.length) {
    const localMessages = prev?.messages ?? []
    return {
      ...updated,
      messages: localMessages.map((msg) =>
        msg.id.startsWith('local-')
          ? { ...msg, id: `${msg.id}-kept` }
          : msg
      ),
      title: updated.title || prev?.title || '新对话',
      updatedAt: updated.updatedAt || prev?.updatedAt || new Date().toISOString(),
      trace: updated.trace?.length ? updated.trace : prev?.trace,
    }
  }
  return {
    ...updated,
    trace: updated.trace?.length ? updated.trace : prev?.trace,
  }
}

/**
 * 乐观插入用户消息；收到首个 delta 时再插入助手气泡并追加内容；结束后用服务端会话覆盖。
 */
export async function sendWithStreaming(options: {
  session: CourseAgentSession
  content: string
  setSession: Dispatch<SetStateAction<CourseAgentSession | null>>
  streamFn: StreamSendFn
  onTrace?: (event: CourseAgentTraceEvent) => void
  onStreamDone?: (session: CourseAgentSession) => void
}): Promise<void> {
  const { session, content, setSession, streamFn, onTrace, onStreamDone } = options
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
    let mergedSession: CourseAgentSession | null = null
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
      onTrace: (event) => {
        onTrace?.(event)
      },
      onDone: (updated) => {
        setSession((prev) => {
          mergedSession = mergeStreamedSession(prev, updated)
          return mergedSession
        })
      },
    })
    if (mergedSession) onStreamDone?.(mergedSession)
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
