import { useEffect, useMemo, useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { ApiClientError } from '@/lib/api/client'
import {
  createPreviewSession,
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
import { CitationSourceSheet } from './citation-source-sheet'
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

type AgentPreviewPanelProps = {
  agentId: string
  agentName?: string
  menuButtons?: string[]
  compact?: boolean
  /** 隐藏「重新开始」按钮（基础配置预览用） */
  hideReset?: boolean
  /** 变化时重新创建预览会话（如保存配置后刷新欢迎词） */
  refreshKey?: number | string
}

export function AgentPreviewPanel({
  agentId,
  agentName,
  menuButtons = [],
  compact,
  hideReset = false,
  refreshKey = 0,
}: AgentPreviewPanelProps) {
  const [session, setSession] = useState<CourseAgentSession | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState<string>()
  const [activeCitation, setActiveCitation] =
    useState<CourseAgentCitation | null>(null)
  const [citationSheetOpen, setCitationSheetOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setInitializing(true)
      setError(undefined)
      setSession(null)
      setInput('')
      try {
        const s = await createPreviewSession(agentId)
        if (!cancelled) setSession(s)
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
  }, [agentId, refreshKey])

  const uiMessages = useMemo(
    () => toUiMessages(session?.messages ?? []),
    [session?.messages]
  )

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

  const isTyping =
    loading &&
    !(
      uiMessages.length > 0 &&
      uiMessages[uiMessages.length - 1]?.role === 'assistant' &&
      (uiMessages[uiMessages.length - 1]?.content?.length ?? 0) > 0
    )

  return (
    <div className='flex min-h-0 flex-1 flex-col gap-3'>
      {!compact ? (
        <div className='flex flex-wrap items-center justify-between gap-3'>
          <div>
            <h2 className='text-lg font-semibold tracking-tight'>对话预览</h2>
            <p className='text-muted-foreground text-sm'>
              基于当前绑定的知识库与模型进行问答测试
            </p>
          </div>
          {!hideReset ? (
            <Button
              variant='outline'
              size='sm'
              disabled={loading || initializing}
              onClick={() => void handleReset()}
            >
              <RotateCcw className='mr-1 size-4' />
              重新开始
            </Button>
          ) : null}
        </div>
      ) : !hideReset ? (
        <div className='flex items-center justify-end'>
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
      ) : null}

      <Card className='flex min-h-0 flex-1 flex-col gap-0 overflow-hidden py-0'>
        <CardHeader className='gap-1 border-b py-4'>
          <CardTitle className='text-base'>{agentName ?? '对话测试'}</CardTitle>
          <CardDescription>保存配置后可在此验证回复效果</CardDescription>
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
          ) : (
            <ChatContainer className='min-h-0 flex-1'>
              {uiMessages.length === 0 && menuButtons.length > 0 ? (
                <PromptSuggestions
                  label='试试这些问题'
                  append={(m) => void sendText(m.content)}
                  suggestions={menuButtons}
                />
              ) : null}

              {uiMessages.length > 0 ? (
                <ChatMessages messages={uiMessages}>
                  <CourseAgentMessageList
                    messages={uiMessages}
                    isTyping={isTyping}
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
          )}
        </CardContent>
      </Card>

      <CitationSourceSheet
        citation={activeCitation}
        open={citationSheetOpen}
        onOpenChange={setCitationSheetOpen}
      />
    </div>
  )
}
