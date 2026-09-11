import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ApiClientError } from '@/lib/api/client'
import {
  createCourseAgentSession,
  getCourseAgentSession,
  getPublicAgentConfig,
  sendCourseAgentMessageStream,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { Button } from '@/components/ui/button'
import { ChatContainer, ChatForm, ChatMessages } from '@/components/ui/chat'
import { MessageInput } from '@/components/ui/message-input'
import { CitationSourceSheet } from './citation-source-sheet'
import { AgentTracePanel } from './agent-trace-panel'
import {
  CourseAgentMessageList,
  type CourseAgentUiMessage,
} from './course-agent-message-list'
import {
  COURSE_AGENT_MAX_INPUT_CHARS,
  isInputTooLong,
} from '../lib/input-limits'
import { sendWithStreaming } from '../lib/stream-send'
import type {
  CourseAgentCitation,
  CourseAgentMessage,
  CourseAgentSession,
  CourseAgentTraceEvent,
} from '../data/types'

const COURSE_BRANCH_ACTIONS = new Set([
  '学生课程',
  '教师培训',
  '平台服务',
  '查看所有课程',
  '了解报名方式',
])

const DRAFT_SESSION_ID = 'draft'

function sanitizeActions(actions?: string[]) {
  return (actions ?? []).filter((item) => !COURSE_BRANCH_ACTIONS.has(item))
}

function buildDraftSession(
  agentId: string,
  welcome: string,
  menuButtons: string[]
): CourseAgentSession {
  const now = new Date().toISOString()
  const live = sanitizeActions(menuButtons)
  return {
    id: DRAFT_SESSION_ID,
    agentId,
    title: '新对话',
    messages: welcome.trim()
      ? [
          {
            id: 'local-welcome',
            role: 'assistant',
            content: welcome,
            createdAt: now,
            quickActions: live.length ? live : undefined,
          },
        ]
      : [],
    state: {
      step: 'welcome',
      role: null,
      constraints: {},
      recommendedCourses: [],
    },
    trace: [],
    createdAt: now,
    updatedAt: now,
  }
}

function isDraftSession(session: CourseAgentSession | null) {
  return !session || session.id === DRAFT_SESSION_ID
}

/** 仅新会话（尚无用户消息）使用当前配置的快捷问题与欢迎语。 */
function applyLiveConversation(
  messages: CourseAgentUiMessage[],
  liveMenu: string[],
  liveWelcome?: string
): CourseAgentUiMessage[] {
  if (!messages.length) return messages
  const hasUser = messages.some((item) => item.role === 'user')
  if (hasUser) {
    return messages.map((item) =>
      item.role === 'assistant' ? { ...item, quickActions: undefined } : item
    )
  }
  const live = sanitizeActions(liveMenu)
  let lastAssistantIndex = -1
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i]?.role === 'assistant') {
      lastAssistantIndex = i
      break
    }
  }
  if (lastAssistantIndex < 0) return messages
  const liveWelcomeText = liveWelcome?.trim()
  if (!live.length && !liveWelcomeText) return messages
  return messages.map((item, index) => {
    if (index !== lastAssistantIndex) return item
    return {
      ...item,
      content: liveWelcomeText || item.content,
      quickActions: live.length ? live : item.quickActions,
    }
  })
}

function toUiMessages(messages: CourseAgentMessage[]): CourseAgentUiMessage[] {
  return messages.map((msg) => {
    const created = new Date(msg.createdAt)
    return {
      id: msg.id,
      role: msg.role,
      content: msg.content,
      createdAt: Number.isNaN(created.getTime()) ? undefined : created,
      citations: msg.citations,
      quickActions: sanitizeActions(msg.quickActions),
      pending: msg.id.startsWith('local-'),
    }
  })
}

type AgentChatSessionProps = {
  agentId: string
  sessionId: string | null
  showTrace?: boolean
  onAgentName?: (name: string) => void
  onSessionCreated?: (session: CourseAgentSession) => void
  onSessionMeta?: (meta: {
    id: string
    title: string
    updatedAt: string
  }) => void
}

export function AgentChatSession({
  agentId,
  sessionId,
  showTrace = false,
  onAgentName,
  onSessionCreated,
  onSessionMeta,
}: AgentChatSessionProps) {
  const [session, setSession] = useState<CourseAgentSession | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState<string>()
  const [traceEvents, setTraceEvents] = useState<CourseAgentTraceEvent[]>([])
  const [liveMenuButtons, setLiveMenuButtons] = useState<string[]>([])
  const [liveWelcome, setLiveWelcome] = useState('')
  const [activeCitation, setActiveCitation] =
    useState<CourseAgentCitation | null>(null)
  const [citationSheetOpen, setCitationSheetOpen] = useState(false)
  const onAgentNameRef = useRef(onAgentName)
  const onSessionMetaRef = useRef(onSessionMeta)
  const onSessionCreatedRef = useRef(onSessionCreated)
  onAgentNameRef.current = onAgentName
  onSessionMetaRef.current = onSessionMeta
  onSessionCreatedRef.current = onSessionCreated

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setInitializing(true)
      setError(undefined)
      setInput('')
      try {
        const pub = await getPublicAgentConfig(agentId)
        if (cancelled) return
        onAgentNameRef.current?.(pub.name)
        const menu = sanitizeActions(pub.menuButtons)
        const welcome = pub.welcomeMessage ?? ''
        setLiveMenuButtons(menu)
        setLiveWelcome(welcome)
        if (!sessionId) {
          const draft = buildDraftSession(agentId, welcome, menu)
          setSession(draft)
          setTraceEvents([])
          return
        }
        const loaded = await getCourseAgentSession(sessionId)
        if (cancelled) return
        setSession(loaded)
        setTraceEvents(loaded.trace ?? [])
        onSessionMetaRef.current?.({
          id: loaded.id,
          title: loaded.title,
          updatedAt: loaded.updatedAt,
        })
      } catch (e) {
        if (!cancelled) {
          setSession(null)
          setTraceEvents([])
          setError(e instanceof ApiClientError ? e.message : '加载失败')
        }
      } finally {
        if (!cancelled) setInitializing(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [agentId, sessionId])

  const uiMessages = useMemo(
    () =>
      applyLiveConversation(
        toUiMessages(session?.messages ?? []),
        liveMenuButtons,
        liveWelcome
      ),
    [session?.messages, liveMenuButtons, liveWelcome]
  )

  const lastAssistant = [...uiMessages].reverse().find((m) => m.role === 'assistant')
  const actions = lastAssistant?.quickActions ?? []

  const sendText = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading || !session) return
    if (isInputTooLong(trimmed)) {
      setError(
        `输入过长，请精简后重新发送（限 ${COURSE_AGENT_MAX_INPUT_CHARS} 字）。`
      )
      return
    }
    setLoading(true)
    setError(undefined)
    setInput('')

    try {
      let current = session
      if (isDraftSession(current)) {
        const created = await createCourseAgentSession(agentId)
        current = created
        setSession(created)
      }
      await sendWithStreaming({
        session: current,
        content: trimmed,
        setSession,
        streamFn: sendCourseAgentMessageStream,
        onTrace: (event) => {
          setTraceEvents((prev) =>
            prev.some((item) => item.id === event.id) ? prev : [...prev, event]
          )
        },
        onStreamDone: (updated) => {
          if (updated.trace?.length) setTraceEvents(updated.trace)
          if (!sessionId) {
            onSessionCreatedRef.current?.(updated)
          }
        },
      })
    } catch (e) {
      if (e instanceof ApiClientError && e.code === 'QUOTA_EXCEEDED') {
        setError('已用完，请升级')
      } else {
        setError(e instanceof ApiClientError ? e.message : '发送失败，请稍后重试')
      }
      setInput(trimmed)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!session || isDraftSession(session)) return
    onSessionMetaRef.current?.({
      id: session.id,
      title: session.title,
      updatedAt: session.updatedAt,
    })
  }, [session?.id, session?.title, session?.updatedAt])

  const isTyping =
    loading &&
    !(
      uiMessages.length > 0 &&
      uiMessages[uiMessages.length - 1]?.role === 'assistant' &&
      (uiMessages[uiMessages.length - 1]?.content?.length ?? 0) > 0
    )

  return (
    <div className='flex h-full min-h-0 flex-1 flex-col overflow-hidden'>
      <div
        className={
          showTrace
            ? 'grid h-full min-h-0 flex-1 overflow-hidden grid-rows-[minmax(0,1fr)_minmax(180px,32%)] md:grid-rows-none md:grid-cols-[minmax(0,1fr)_300px]'
            : 'flex h-full min-h-0 flex-1 flex-col overflow-hidden'
        }
      >
        <div className='flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-4'>
        {error ? (
          <div className='mb-3 space-y-2'>
            <AppErrorAlert message={error} />
            {error.includes('请升级') ? (
              <Button asChild size='sm'>
                <Link to='/plans' search={{ pay: undefined }}>
                  前往套餐页升级
                </Link>
              </Button>
            ) : null}
          </div>
        ) : null}
        {initializing ? (
          <p className='text-muted-foreground py-8 text-center text-sm'>
            正在加载会话…
          </p>
        ) : session ? (
          <ChatContainer className='min-h-0 h-full flex-1 overflow-hidden'>
            {uiMessages.length > 0 ? (
              <ChatMessages messages={uiMessages}>
                <CourseAgentMessageList
                  messages={uiMessages}
                  isTyping={loading || isTyping}
                  actionsDisabled={loading}
                  onQuickAction={
                    actions.length > 0
                      ? (label) => void sendText(label)
                      : undefined
                  }
                  onOpenCitation={(citation) => {
                    setActiveCitation(citation)
                    setCitationSheetOpen(true)
                  }}
                />
              </ChatMessages>
            ) : (
              <p className='text-muted-foreground py-8 text-center text-sm'>
                开始提问吧。
              </p>
            )}

            <ChatForm
              className='mt-auto'
              isPending={loading}
              handleSubmit={(e) => {
                e?.preventDefault?.()
                void sendText(input)
              }}
            >
              {() => (
                <MessageInput
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  isGenerating={loading}
                  maxLength={COURSE_AGENT_MAX_INPUT_CHARS}
                  placeholder='请输入您的问题…'
                />
              )}
            </ChatForm>
          </ChatContainer>
        ) : (
          <p className='text-muted-foreground py-8 text-center text-sm'>
            会话未建立。请确认该智能体已正式发布后重试。
          </p>
        )}
      </div>

      {showTrace ? (
        <AgentTracePanel events={traceEvents} running={loading} />
      ) : null}
      </div>

      <CitationSourceSheet
        citation={activeCitation}
        open={citationSheetOpen}
        onOpenChange={setCitationSheetOpen}
      />
    </div>
  )
}
