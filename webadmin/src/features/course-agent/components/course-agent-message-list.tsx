import { Button } from '@/components/ui/button'
import { ChatMessage, type Message } from '@/components/ui/chat-message'
import { TypingIndicator } from '@/components/ui/typing-indicator'
import { cn } from '@/lib/utils'
import { MessageCitationLinks } from './message-citation-links'
import type { CourseAgentCitation } from '../data/types'

export type CourseAgentUiMessage = Message & {
  citations?: CourseAgentCitation[]
  quickActions?: string[]
  /** 本地乐观消息，尚未得到服务端确认 */
  pending?: boolean
}

type CourseAgentMessageListProps = {
  messages: CourseAgentUiMessage[]
  isTyping?: boolean
  actionsDisabled?: boolean
  /** 仅在最后一条助手消息下展示快捷按钮（避免历史气泡堆满按钮） */
  showActionsOnLatestOnly?: boolean
  onQuickAction?: (label: string) => void
  onOpenCitation: (citation: CourseAgentCitation) => void
}

export function CourseAgentMessageList({
  messages,
  isTyping = false,
  actionsDisabled = false,
  showActionsOnLatestOnly = true,
  onQuickAction,
  onOpenCitation,
}: CourseAgentMessageListProps) {
  let lastAssistantIndex = -1
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i]?.role === 'assistant') {
      lastAssistantIndex = i
      break
    }
  }

  return (
    <div className='space-y-4 overflow-visible'>
      {messages.map((message, index) => {
        const showActions =
          message.role === 'assistant' &&
          Boolean(message.quickActions?.length) &&
          Boolean(onQuickAction) &&
          (!showActionsOnLatestOnly || index === lastAssistantIndex)

        return (
          <div
            key={message.id}
            className={cn('w-full', message.pending && 'opacity-80')}
          >
            <ChatMessage showTimeStamp animation='none' {...message} />
            {message.role === 'assistant' && message.citations?.length ? (
              <div className='mt-1 flex justify-start'>
                <div className='bg-muted/50 max-w-[min(100%,36rem)] rounded-lg px-3 pb-2'>
                  <MessageCitationLinks
                    citations={message.citations}
                    onOpenCitation={onOpenCitation}
                  />
                </div>
              </div>
            ) : null}
            {showActions ? (
              <div className='mt-2 flex max-w-[min(100%,36rem)] flex-wrap gap-2'>
                {message.quickActions!.map((label) => (
                  <Button
                    key={label}
                    type='button'
                    variant='secondary'
                    size='sm'
                    disabled={actionsDisabled}
                    onClick={() => onQuickAction?.(label)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            ) : null}
          </div>
        )
      })}
      {isTyping ? <TypingIndicator /> : null}
    </div>
  )
}
