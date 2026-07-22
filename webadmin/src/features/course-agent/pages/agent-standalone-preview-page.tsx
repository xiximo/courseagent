import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ArrowLeft, GraduationCap, RotateCcw } from 'lucide-react'
import { ApiClientError } from '@/lib/api/client'
import {
  createPreviewSession,
  getCourseAgent,
  resetPreviewSession,
  sendPreviewMessageStream,
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

type AgentStandalonePreviewPageProps = {
  agentId: string
}

/** 管理端独立预览页：布局接近公开对话页，走 preview API（草稿也可测）。 */
export function AgentStandalonePreviewPage({
  agentId,
}: AgentStandalonePreviewPageProps) {
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
        const [cfg, s] = await Promise.all([
          getCourseAgent(agentId),
          createPreviewSession(agentId),
        ])
        if (cancelled) return
        setAgentName(cfg.name)
        const menu = cfg.conversation?.menuButtons
        if (menu?.length) setQuickActions(menu)
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
        streamFn: sendPreviewMessageStream,
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
      const updated = await resetPreviewSession(session.id)
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

  return (
    <div className='bg-background flex min-h-svh flex-col'>
      <header className='border-b'>
        <div className='mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3'>
          <div className='flex min-w-0 items-center gap-2'>
            <Button variant='ghost' size='sm' asChild className='shrink-0 px-2'>
              <Link
                to='/admin/course-agents/$agentId'
                params={{ agentId }}
              >
                <ArrowLeft className='size-4' />
                <span className='sr-only'>返回配置</span>
              </Link>
            </Button>
            <div className='bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-full'>
              <GraduationCap className='size-5' />
            </div>
            <div className='min-w-0'>
              <h1 className='truncate text-sm font-semibold'>{agentName}</h1>
              <p className='text-muted-foreground text-xs'>
                管理端预览 · 草稿/停用也可测（不计入客户线索）
              </p>
            </div>
          </div>
          <div className='flex shrink-0 items-center gap-2'>
            <Button variant='outline' size='sm' asChild>
              <Link to='/admin/course-agents'>返回列表</Link>
            </Button>
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
        </div>
        {session ? <AgentStatusBar state={session.state} /> : null}
      </header>

      <main className='mx-auto flex w-full max-w-3xl flex-1 flex-col p-4'>
        <Card className='flex min-h-[min(720px,calc(100svh-8rem))] flex-1 flex-col gap-0 overflow-hidden py-0'>
          <CardHeader className='gap-1 border-b py-4'>
            <CardTitle className='text-base'>课程咨询预览</CardTitle>
            <CardDescription>
              与公开页相同交互；此处使用预览会话，不影响正式访客线索
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
                正在初始化预览会话…
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
                      isTyping={
                        loading &&
                        !(
                          uiMessages.length > 0 &&
                          uiMessages[uiMessages.length - 1]?.role ===
                            'assistant' &&
                          (uiMessages[uiMessages.length - 1]?.content?.length ??
                            0) > 0
                        )
                      }
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
