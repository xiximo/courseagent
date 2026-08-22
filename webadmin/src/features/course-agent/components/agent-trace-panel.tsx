import { useEffect, useRef } from 'react'
import {
  Activity,
  Brain,
  CheckCircle2,
  GitBranch,
  MessageSquareText,
  Wrench,
} from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { CourseAgentTraceEvent } from '../data/types'

const TYPE_META: Record<
  CourseAgentTraceEvent['type'],
  { label: string; icon: typeof Brain; className: string }
> = {
  turn: {
    label: '本轮',
    icon: Activity,
    className: 'bg-sky-500/15 text-sky-700 dark:text-sky-300',
  },
  thinking: {
    label: '思考',
    icon: Brain,
    className: 'bg-violet-500/15 text-violet-700 dark:text-violet-300',
  },
  tool: {
    label: '工具',
    icon: Wrench,
    className: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  },
  tool_result: {
    label: '结果',
    icon: CheckCircle2,
    className: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  },
  reply: {
    label: '作答',
    icon: MessageSquareText,
    className: 'bg-primary/15 text-primary',
  },
  node: {
    label: '节点',
    icon: GitBranch,
    className: 'bg-slate-500/15 text-slate-700 dark:text-slate-300',
  },
}

function formatTime(iso: string) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

type AgentTracePanelProps = {
  events: CourseAgentTraceEvent[]
  running?: boolean
}

export function AgentTracePanel({ events, running }: AgentTracePanelProps) {
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [events.length, running])

  return (
    <aside className='flex h-full min-h-0 min-w-0 flex-col overflow-hidden border-t bg-muted/20 md:border-t-0 md:border-l'>
      <div className='flex shrink-0 items-center gap-2 border-b px-3 py-3'>
        <Activity className='text-muted-foreground size-4' />
        <div className='min-w-0'>
          <div className='text-sm font-medium'>运行轨迹</div>
          <div className='text-muted-foreground text-xs'>
            {running ? '正在思考与调用工具…' : '思考、工具调用与节点执行'}
          </div>
        </div>
      </div>
      <ScrollArea className='h-0 min-h-0 flex-1'>
        <div className='space-y-2 p-3'>
          {events.length === 0 && !running ? (
            <p className='text-muted-foreground py-8 text-center text-xs'>
              发送消息后，这里会展示模型思考与工具调用过程。
            </p>
          ) : null}
          {events.map((event) => {
            const meta = TYPE_META[event.type] ?? TYPE_META.thinking
            const Icon = meta.icon
            return (
              <div
                key={event.id}
                className='rounded-lg border bg-background px-2.5 py-2 shadow-xs'
              >
                <div className='flex items-start gap-2'>
                  <span
                    className={cn(
                      'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md',
                      meta.className
                    )}
                  >
                    <Icon className='size-3.5' />
                  </span>
                  <div className='min-w-0 flex-1'>
                    <div className='flex items-center justify-between gap-2'>
                      <span className='text-[11px] font-medium tracking-wide uppercase opacity-70'>
                        {meta.label}
                      </span>
                      <span className='text-muted-foreground text-[10px]'>
                        {formatTime(event.createdAt)}
                      </span>
                    </div>
                    <div className='mt-0.5 text-xs font-medium leading-snug'>
                      {event.title}
                      {event.status === 'running' ? (
                        <span className='text-muted-foreground ml-1 font-normal'>
                          …
                        </span>
                      ) : null}
                    </div>
                    {event.toolName ? (
                      <div className='text-muted-foreground mt-0.5 font-mono text-[10px]'>
                        {event.toolName}
                      </div>
                    ) : null}
                    {event.detail ? (
                      <pre className='bg-muted/60 mt-1.5 max-h-36 overflow-auto rounded-md px-2 py-1.5 text-[11px] leading-relaxed whitespace-pre-wrap break-words'>
                        {event.detail}
                      </pre>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
          {running && events.every((item) => item.status !== 'running') ? (
            <p className='text-muted-foreground px-1 py-2 text-xs'>等待模型响应…</p>
          ) : null}
          <div ref={endRef} />
        </div>
      </ScrollArea>
    </aside>
  )
}
