import { useEffect, useMemo, useState } from 'react'
import { getRouteApi } from '@tanstack/react-router'
import { GraduationCap, RotateCcw } from 'lucide-react'
import { ApiClientError } from '@/lib/api/client'
import {
  createCourseAgentSession,
  getPublicAgentConfig,
  resetCourseAgentSession,
  sendCourseAgentMessageStream,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  ChatContainer,
  ChatForm,
  ChatMessages,
} from '@/components/ui/chat'
import { MessageInput } from '@/components/ui/message-input'
import { PromptSuggestions } from '@/components/ui/prompt-suggestions'
import { AgentStatusBar } from '../components/agent-status-bar'
import { CitationSourceSheet } from '../components/citation-source-sheet'
import {
  CourseAgentMessageList,
  type CourseAgentUiMessage,
} from '../components/course-agent-message-list'
import {
  COURSE_AGENT_MAX_INPUT_CHARS,
  isInputTooLong,
} from '../lib/input-limits'
import { sendWithStreaming } from '../lib/stream-send'
import type {
  CourseAgentCitation,
  CourseAgentMessage,
  CourseAgentSession,
} from '../data/types'

const route = getRouteApi('/chat/$agentId')

function toUiMessages(messages: CourseAgentMessage[]): CourseAgentUiMessage[] {
  return messages.map((msg) => ({
    id: msg.id,
    role: msg.role,
    content: msg.content,
    createdAt: new Date(msg.createdAt),
    citations: msg.citations,
    quickActions: msg.quickActions,
    pending: msg.id.startsWith('local-'),
  }))
}

export function PublicChatPage() {
  const { agentId } = route.useParams()
  const [agentName, setAgentName] = useState('Agent')
  const [session, setSession] = useState<CourseAgentSession | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState<string>()
  const [quickActions, setQuickActions] = useState<string[]>([
    '学生课程',
    '教师培训',
    '平台服务',
  ])
  const [activeCitation, setActiveCitation] =
    useState<CourseAgentCitation | null>(null)
  const [citationSheetOpen, setCitationSheetOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setInitializing(true)
      setError(undefined)
      try {
        const pub = await getPublicAgentConfig(agentId)
        if (cancelled) return
        setAgentName(pub.name)
        setQuickActions(pub.menuButtons)
        const s = await createCourseAgentSession(agentId)
        if (cancelled) return
        setSession(s)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiClientError ? e.message : '加载失败')
        }
      } finally {
        if (!cancelled) setInitializing(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [agentId])

  const uiMessages = useMemo(
    () => toUiMessages(session?.messages ?? []),
    [session?.messages]
  )

  const lastAssistant = [...(session?.messages ?? [])]
    .reverse()
    .find((m) => m.role === 'assistant')
  const actions = lastAssistant?.quickActions ?? quickActions

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
      await sendWithStreaming({
        session,
        content: trimmed,
        setSession,
        streamFn: sendCourseAgentMessageStream,
      })
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '发送失败，请稍后重试')
      setInput(trimmed)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    if (!session || loading) return
    setLoading(true)
    setError(undefined)
    try {
      const updated = await resetCourseAgentSession(session.id)
      setSession(updated)
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '重置失败')
    } finally {
      setLoading(false)
    }
  }

  const openCitation = (citation: CourseAgentCitation) => {
    setActiveCitation(citation)
    setCitationSheetOpen(true)
  }

  const isTyping =
    loading &&
    !(
      uiMessages.length > 0 &&
      uiMessages[uiMessages.length - 1]?.role === 'assistant' &&
      (uiMessages[uiMessages.length - 1]?.content?.length ?? 0) > 0
    )

  return (
    <div className='bg-background flex min-h-svh flex-col'>
      <header className='border-b'>
        <div className='mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3'>
          <div className='flex items-center gap-2'>
            <div className='bg-primary/10 text-primary flex size-9 items-center justify-center rounded-full'>
              <GraduationCap className='size-5' />
            </div>
            <div>
              <h1 className='text-sm font-semibold'>{agentName}</h1>
              <p className='text-muted-foreground text-xs'>
                AI 教育中心 · 无需登录即可咨询
              </p>
            </div>
          </div>
          <Button
            variant='outline'
            size='sm'
            disabled={loading || initializing}
            onClick={() => void handleReset()}
          >
            <RotateCcw className='mr-1 size-4' />
            重新开始
          </Button>
        </div>
        {session ? <AgentStatusBar state={session.state} /> : null}
      </header>

      <main className='mx-auto flex w-full max-w-3xl flex-1 flex-col p-4'>
        <Card className='flex min-h-[min(720px,calc(100svh-8rem))] flex-1 flex-col gap-0 overflow-hidden py-0'>
          <CardHeader className='gap-1 border-b py-4'>
            <CardTitle className='text-base'>课程咨询</CardTitle>
            <CardDescription>
              状态机驱动 · 知识库 RAG · 引用可点击溯源
            </CardDescription>
          </CardHeader>
          <CardContent className='flex min-h-0 flex-1 flex-col overflow-hidden p-4'>
            {error ? (
              <div className='mb-3'>
                <AppErrorAlert message={error} />
              </div>
            ) : null}
            {initializing ? (
              <p className='text-muted-foreground py-8 text-center text-sm'>
                正在连接顾问…
              </p>
            ) : session ? (
              <ChatContainer className='min-h-0 flex-1'>
                {uiMessages.length === 0 && actions.length > 0 ? (
                  <PromptSuggestions
                    label='试试这些问题'
                    append={(m) => void sendText(m.content)}
                    suggestions={actions}
                  />
                ) : null}

                {uiMessages.length > 0 ? (
                  <ChatMessages messages={uiMessages}>
                    <CourseAgentMessageList
                      messages={uiMessages}
                      isTyping={loading || isTyping}
                      actionsDisabled={loading}
                      onQuickAction={(label) => void sendText(label)}
                      onOpenCitation={openCitation}
                    />
                  </ChatMessages>
                ) : null}

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
                会话未建立，请刷新页面重试。
              </p>
            )}
          </CardContent>
        </Card>
      </main>

      <CitationSourceSheet
        citation={activeCitation}
        open={citationSheetOpen}
        onOpenChange={setCitationSheetOpen}
      />
    </div>
  )
}
