import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { MessageSquare, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteCourseAgentSession,
  getPublicAgentConfig,
  listCourseAgentSessions,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Main } from '@/components/layout/main'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { AgentChatSession } from '../components/agent-chat-session'
import type {
  CourseAgentSession,
  CourseAgentSessionSummary,
} from '../data/types'

const STORAGE_PREFIX = 'course-agent-chat-session:'

type AdminAgentChatPageProps = {
  agentId: string
}

function readStoredSessionId(agentId: string, userId: string | undefined) {
  try {
    return localStorage.getItem(`${STORAGE_PREFIX}${userId ?? 'anon'}:${agentId}`)
  } catch {
    return null
  }
}

function writeStoredSessionId(
  agentId: string,
  userId: string | undefined,
  sessionId: string | null
) {
  try {
    const key = `${STORAGE_PREFIX}${userId ?? 'anon'}:${agentId}`
    if (sessionId) localStorage.setItem(key, sessionId)
    else localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

function formatSessionTime(iso: string) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function AdminAgentChatPage({ agentId }: AdminAgentChatPageProps) {
  const userId = useAuthStore((s) => s.auth.user?.id)
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [agentName, setAgentName] = useState('智能体')
  const [sessions, setSessions] = useState<CourseAgentSessionSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [error, setError] = useState<string>()
  const [deleteTarget, setDeleteTarget] = useState<CourseAgentSessionSummary | null>(
    null
  )
  const [deleting, setDeleting] = useState(false)

  const selectSession = useCallback(
    (sessionId: string) => {
      setSelectedId(sessionId)
      writeStoredSessionId(agentId, userId, sessionId)
    },
    [agentId, userId]
  )

  const ensureSessions = useCallback(async () => {
    setLoadingList(true)
    setError(undefined)
    try {
      const [pub, list] = await Promise.all([
        getPublicAgentConfig(agentId),
        listCourseAgentSessions(agentId),
      ])
      setAgentName(pub.name)
      let next = list
      setSessions(next)
      const stored = readStoredSessionId(agentId, userId)
      const preferred =
        (stored && next.find((item) => item.id === stored)?.id) || next[0]?.id || null
      if (preferred) selectSession(preferred)
      else {
        setSelectedId(null)
        writeStoredSessionId(agentId, userId, null)
      }
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载会话失败')
    } finally {
      setLoadingList(false)
    }
  }, [agentId, selectSession, userId])

  useEffect(() => {
    void ensureSessions()
  }, [ensureSessions])

  const handleNewSession = () => {
    setSelectedId(null)
    writeStoredSessionId(agentId, userId, null)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteCourseAgentSession(deleteTarget.id)
      const remaining = sessions.filter((item) => item.id !== deleteTarget.id)
      setSessions(remaining)
      setDeleteTarget(null)
      if (selectedId === deleteTarget.id) {
        if (remaining[0]) {
          selectSession(remaining[0].id)
        } else {
          setSelectedId(null)
          writeStoredSessionId(agentId, userId, null)
        }
      }
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <AppPageHeader />
      <Main className='flex min-h-0 flex-1 flex-col gap-4 overflow-hidden' fluid fixed>
        <div className='flex shrink-0 flex-wrap items-center justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>{agentName}</h1>
            <p className='text-muted-foreground text-sm'>直接提问，可在左侧管理会话，右侧查看运行轨迹</p>
          </div>
          {canConfig ? (
            <Button variant='outline' size='sm' asChild>
              <Link to='/admin/course-agents/$agentId' params={{ agentId }}>
                前往配置
              </Link>
            </Button>
          ) : null}
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        <div className='grid min-h-0 flex-1 overflow-hidden rounded-xl border bg-card grid-rows-[minmax(160px,28%)_minmax(0,1fr)] md:grid-rows-none md:grid-cols-[260px_minmax(0,1fr)]'>
          <aside className='flex h-full min-h-0 flex-col overflow-hidden border-b md:border-b-0 md:border-r'>
            <div className='flex shrink-0 items-center justify-between gap-2 border-b px-3 py-3'>
              <div className='flex items-center gap-2 text-sm font-medium'>
                <MessageSquare className='size-4' />
                会话
              </div>
              <Button
                size='sm'
                variant='outline'
                disabled={loadingList}
                onClick={handleNewSession}
              >
                <Plus className='size-3.5' />
                新对话
              </Button>
            </div>
            <ScrollArea className='h-0 min-h-0 flex-1'>
              {loadingList ? (
                <p className='text-muted-foreground px-3 py-6 text-sm'>加载中…</p>
              ) : (
                <ul className='p-2'>
                  {selectedId === null ? (
                    <li>
                      <div className='bg-primary/10 text-primary rounded-md px-2 py-2'>
                        <div className='truncate text-sm font-medium'>新对话</div>
                        <div className='text-muted-foreground mt-0.5 text-xs'>
                          提问后才会保存
                        </div>
                      </div>
                    </li>
                  ) : null}
                  {sessions.map((item) => (
                    <li key={item.id}>
                      <div
                        className={cn(
                          'group flex items-start gap-1 rounded-md px-2 py-2',
                          selectedId === item.id
                            ? 'bg-primary/10 text-primary'
                            : 'hover:bg-muted/70'
                        )}
                      >
                        <button
                          type='button'
                          className='min-w-0 flex-1 text-left'
                          onClick={() => selectSession(item.id)}
                        >
                          <div className='truncate text-sm font-medium'>
                            {item.title || '新对话'}
                          </div>
                          <div className='text-muted-foreground mt-0.5 text-xs'>
                            {formatSessionTime(item.updatedAt)}
                          </div>
                        </button>
                        <Button
                          type='button'
                          size='icon'
                          variant='ghost'
                          className='text-muted-foreground hover:text-destructive size-7 opacity-0 group-hover:opacity-100'
                          onClick={() => setDeleteTarget(item)}
                        >
                          <Trash2 className='size-3.5' />
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </ScrollArea>
          </aside>

          <div className='flex h-full min-h-0 min-w-0 flex-col overflow-hidden'>
            {loadingList ? (
              <p className='text-muted-foreground py-16 text-center text-sm'>
                正在准备会话…
              </p>
            ) : (
              <AgentChatSession
                key={selectedId ?? 'draft'}
                agentId={agentId}
                sessionId={selectedId}
                showTrace
                onAgentName={setAgentName}
                onSessionCreated={(created: CourseAgentSession) => {
                  const summary: CourseAgentSessionSummary = {
                    id: created.id,
                    agentId: created.agentId,
                    title: created.title,
                    createdAt: created.createdAt,
                    updatedAt: created.updatedAt,
                  }
                  setSessions((list) => [
                    summary,
                    ...list.filter((item) => item.id !== summary.id),
                  ])
                  selectSession(created.id)
                }}
                onSessionMeta={(meta) => {
                  setSessions((list) => {
                    const index = list.findIndex((item) => item.id === meta.id)
                    if (index < 0) return list
                    const current = list[index]
                    if (
                      current.title === meta.title &&
                      current.updatedAt === meta.updatedAt
                    ) {
                      return list
                    }
                    const next = [...list]
                    next[index] = {
                      ...current,
                      title: meta.title,
                      updatedAt: meta.updatedAt,
                    }
                    return next
                  })
                }}
              />
            )}
          </div>
        </div>
      </Main>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除会话'
        desc={
          deleteTarget
            ? `确定删除「${deleteTarget.title || '新对话'}」吗？删除后不可恢复。`
            : ''
        }
        cancelBtnText='取消'
        confirmText='删除'
        destructive
        isLoading={deleting}
        handleConfirm={() => void handleDeleteConfirm()}
      />
    </>
  )
}
