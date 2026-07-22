import { useState, type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { motion } from 'framer-motion'
import { Ban, ChevronRight, Code2, Loader2, Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { MarkdownRenderer } from '@/components/ui/markdown-renderer'

const chatBubbleVariants = cva(
  // inline-block：按内容撑开宽度；避免 flex+w-fit 把中文压成一字/两字一行
  'group/message relative inline-block max-w-full rounded-lg px-3 py-2 text-sm leading-relaxed',
  {
    variants: {
      isUser: {
        true: 'bg-primary text-primary-foreground',
        false: 'bg-muted text-foreground',
      },
      animation: {
        none: '',
        slide: 'duration-300 animate-in fade-in-0',
        scale: 'duration-300 animate-in fade-in-0 zoom-in-75',
        fade: 'duration-500 animate-in fade-in-0',
      },
    },
    compoundVariants: [
      {
        isUser: true,
        animation: 'slide',
        class: 'slide-in-from-right',
      },
      {
        isUser: false,
        animation: 'slide',
        class: 'slide-in-from-left',
      },
      {
        isUser: true,
        animation: 'scale',
        class: 'origin-bottom-right',
      },
      {
        isUser: false,
        animation: 'scale',
        class: 'origin-bottom-left',
      },
    ],
  }
)

type Animation = VariantProps<typeof chatBubbleVariants>['animation']

interface PartialToolCall {
  state: 'partial-call'
  toolName: string
}

interface ToolCallState {
  state: 'call'
  toolName: string
}

interface ToolResult {
  state: 'result'
  toolName: string
  result: {
    __cancelled?: boolean
    [key: string]: unknown
  }
}

type ToolInvocation = PartialToolCall | ToolCallState | ToolResult

interface ReasoningPart {
  type: 'reasoning'
  reasoning: string
}

interface ToolInvocationPart {
  type: 'tool-invocation'
  toolInvocation: ToolInvocation
}

interface TextPart {
  type: 'text'
  text: string
}

type MessagePart = TextPart | ReasoningPart | ToolInvocationPart

export interface Message {
  id: string
  role: 'user' | 'assistant' | (string & {})
  content: string
  createdAt?: Date
  toolInvocations?: ToolInvocation[]
  parts?: MessagePart[]
}

export interface ChatMessageProps extends Message {
  showTimeStamp?: boolean
  animation?: Animation
  actions?: React.ReactNode
}

export function ChatMessage({
  role,
  content,
  createdAt,
  showTimeStamp = false,
  animation = 'none',
  actions,
  toolInvocations,
  parts,
}: ChatMessageProps) {
  const isUser = role === 'user'
  const formattedTime = createdAt?.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })

  const bubble = (body: ReactNode) => (
    <div className={cn(chatBubbleVariants({ isUser, animation }))}>
      {body}
      {actions ? (
        <div className='absolute -bottom-4 right-2 flex space-x-1 rounded-lg border bg-background p-1 text-foreground opacity-0 transition-opacity group-hover/message:opacity-100'>
          {actions}
        </div>
      ) : null}
    </div>
  )

  if (parts && parts.length > 0) {
    return (
      <>
        {parts.map((part, index) => {
          if (part.type === 'text') {
            return (
              <div
                className={cn(
                  'flex w-full',
                  isUser ? 'justify-end' : 'justify-start'
                )}
                key={`text-${index}`}
              >
                <div className='max-w-[min(100%,36rem)]'>
                  {bubble(
                    isUser ? (
                      <span className='whitespace-pre-wrap'>{part.text}</span>
                    ) : (
                      <MarkdownRenderer>{part.text}</MarkdownRenderer>
                    )
                  )}
                  {showTimeStamp && createdAt ? (
                    <time
                      dateTime={createdAt.toISOString()}
                      className={cn(
                        'mt-1 block px-1 text-xs opacity-50',
                        isUser && 'text-end'
                      )}
                    >
                      {formattedTime}
                    </time>
                  ) : null}
                </div>
              </div>
            )
          }
          if (part.type === 'reasoning') {
            return <ReasoningBlock key={`reasoning-${index}`} part={part} />
          }
          if (part.type === 'tool-invocation') {
            return (
              <ToolCallBlock
                key={`tool-${index}`}
                toolInvocations={[part.toolInvocation]}
              />
            )
          }
          return null
        })}
      </>
    )
  }

  if (toolInvocations && toolInvocations.length > 0) {
    return <ToolCallBlock toolInvocations={toolInvocations} />
  }

  return (
    <div
      className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}
    >
      <div className='max-w-[min(100%,36rem)]'>
        {bubble(
          isUser ? (
            <span className='whitespace-pre-wrap'>{content}</span>
          ) : (
            <MarkdownRenderer>{content}</MarkdownRenderer>
          )
        )}
        {showTimeStamp && createdAt ? (
          <time
            dateTime={createdAt.toISOString()}
            className={cn(
              'mt-1 block px-1 text-xs opacity-50',
              isUser && 'text-end'
            )}
          >
            {formattedTime}
          </time>
        ) : null}
      </div>
    </div>
  )
}

function ReasoningBlock({ part }: { part: ReasoningPart }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className='mb-2 flex flex-col items-start sm:max-w-[70%]'>
      <Collapsible
        open={isOpen}
        onOpenChange={setIsOpen}
        className='group w-full overflow-hidden rounded-lg border bg-muted/50'
      >
        <div className='flex items-center p-2'>
          <CollapsibleTrigger asChild>
            <button
              type='button'
              className='flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground'
            >
              <ChevronRight className='h-4 w-4 transition-transform group-data-[state=open]:rotate-90' />
              <span>思考过程</span>
            </button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent forceMount>
          <motion.div
            initial={false}
            animate={isOpen ? 'open' : 'closed'}
            variants={{
              open: { height: 'auto', opacity: 1 },
              closed: { height: 0, opacity: 0 },
            }}
            transition={{ duration: 0.3, ease: [0.04, 0.62, 0.23, 0.98] }}
            className='border-t'
          >
            <div className='p-2'>
              <div className='whitespace-pre-wrap text-xs'>{part.reasoning}</div>
            </div>
          </motion.div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

function ToolCallBlock({
  toolInvocations,
}: {
  toolInvocations?: ToolInvocation[]
}) {
  if (!toolInvocations?.length) return null

  return (
    <div className='flex flex-col items-start gap-2'>
      {toolInvocations.map((invocation, index) => {
        const isCancelled =
          invocation.state === 'result' &&
          invocation.result.__cancelled === true

        if (isCancelled) {
          return (
            <div
              key={index}
              className='flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm text-muted-foreground'
            >
              <Ban className='h-4 w-4' />
              <span>
                已取消 <span className='font-mono'>`{invocation.toolName}`</span>
              </span>
            </div>
          )
        }

        switch (invocation.state) {
          case 'partial-call':
          case 'call':
            return (
              <div
                key={index}
                className='flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm text-muted-foreground'
              >
                <Terminal className='h-4 w-4' />
                <span>
                  调用 <span className='font-mono'>`{invocation.toolName}`</span>
                  …
                </span>
                <Loader2 className='h-3 w-3 animate-spin' />
              </div>
            )
          case 'result':
            return (
              <div
                key={index}
                className='flex flex-col gap-1.5 rounded-lg border bg-muted/50 px-3 py-2 text-sm'
              >
                <div className='flex items-center gap-2 text-muted-foreground'>
                  <Code2 className='h-4 w-4' />
                  <span>
                    结果来自{' '}
                    <span className='font-mono'>`{invocation.toolName}`</span>
                  </span>
                </div>
                <pre className='overflow-x-auto whitespace-pre-wrap text-foreground'>
                  {JSON.stringify(invocation.result, null, 2)}
                </pre>
              </div>
            )
          default:
            return null
        }
      })}
    </div>
  )
}
