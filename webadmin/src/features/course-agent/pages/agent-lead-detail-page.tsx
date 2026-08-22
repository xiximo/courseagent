import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteAdminSessionRecord,
  getAdminSessionRecord,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import {
  CourseAgentMessageList,
  type CourseAgentUiMessage,
} from '../components/course-agent-message-list'
import { CitationSourceSheet } from '../components/citation-source-sheet'
import type {
  AdminSessionDetail,
  CourseAgentCitation,
} from '../data/types'

function formatTime(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

type AgentLeadDetailPageProps = {
  leadId: string
}

export function AgentLeadDetailPage({ leadId }: AgentLeadDetailPageProps) {
  const sessionId = leadId
  const navigate = useNavigate()
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [record, setRecord] = useState<AdminSessionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [activeCitation, setActiveCitation] =
    useState<CourseAgentCitation | null>(null)
  const [citationSheetOpen, setCitationSheetOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setError(undefined)
      try {
        const detail = await getAdminSessionRecord(sessionId)
        if (!cancelled) setRecord(detail)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiClientError ? e.message : '加载会话记录失败')
          setRecord(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [sessionId])

  const uiMessages: CourseAgentUiMessage[] = useMemo(() => {
    if (!record) return []
    return record.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: new Date(m.createdAt),
      citations: m.citations,
    }))
  }, [record])

  const handleDeleteConfirm = async () => {
    setDeleting(true)
    try {
      await deleteAdminSessionRecord(sessionId)
      toast.success('会话已删除')
      setConfirmOpen(false)
      void navigate({ to: '/admin/course-agents/leads' })
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return <p className='text-muted-foreground'>加载中…</p>
  }

  if (error) {
    return <AppErrorAlert message={error} />
  }

  if (!record) {
    return <p className='text-muted-foreground'>会话不存在</p>
  }

  return (
    <div className='flex flex-col gap-4'>
      <div className='flex flex-wrap items-center gap-3'>
        <Button asChild variant='ghost' size='sm'>
          <Link to='/admin/course-agents/leads'>
            <ArrowLeft className='mr-1 size-4' />
            返回列表
          </Link>
        </Button>
        <div className='min-w-0 flex-1'>
          <h2 className='truncate text-2xl font-bold tracking-tight'>
            {record.title || '新对话'}
          </h2>
          <p className='text-muted-foreground text-sm'>
            {record.agentName} · {record.fullName}（@{record.username}）
          </p>
        </div>
        {record.personaLabel ? (
          <Badge variant='secondary'>{record.personaLabel}</Badge>
        ) : null}
        {canConfig ? (
          <Button
            type='button'
            variant='outline'
            size='sm'
            className='text-destructive hover:text-destructive'
            onClick={() => setConfirmOpen(true)}
          >
            <Trash2 className='mr-1 size-4' />
            删除
          </Button>
        ) : null}
      </div>

      <div className='grid gap-3 rounded-md border p-4 text-sm sm:grid-cols-2 lg:grid-cols-3'>
        <div>
          <div className='text-muted-foreground'>用户</div>
          <div>
            {record.fullName}
            <span className='text-muted-foreground ml-1 font-mono text-xs'>
              @{record.username}
            </span>
          </div>
        </div>
        <div>
          <div className='text-muted-foreground'>Agent</div>
          <div>{record.agentName}</div>
        </div>
        <div>
          <div className='text-muted-foreground'>消息数</div>
          <div>{record.messages.length}</div>
        </div>
        <div>
          <div className='text-muted-foreground'>创建时间</div>
          <div>{formatTime(record.createdAt)}</div>
        </div>
        <div>
          <div className='text-muted-foreground'>更新时间</div>
          <div>{formatTime(record.updatedAt)}</div>
        </div>
      </div>

      <div className='rounded-md border p-4'>
        <h3 className='mb-4 font-semibold'>
          对话过程（{record.messages.length} 条）
        </h3>
        {uiMessages.length === 0 ? (
          <p className='text-muted-foreground text-sm'>暂无消息</p>
        ) : (
          <CourseAgentMessageList
            messages={uiMessages}
            onOpenCitation={(c) => {
              setActiveCitation(c)
              setCitationSheetOpen(true)
            }}
          />
        )}
      </div>

      <CitationSourceSheet
        citation={activeCitation}
        open={citationSheetOpen}
        onOpenChange={setCitationSheetOpen}
      />

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          if (!open && !deleting) setConfirmOpen(false)
        }}
        title='删除会话记录'
        desc={
          <>
            确定删除「{record.title || '新对话'}」吗？对话内容将一并删除，且不可恢复。
          </>
        }
        cancelBtnText='取消'
        confirmText='删除'
        destructive
        isLoading={deleting}
        handleConfirm={() => void handleDeleteConfirm()}
      />
    </div>
  )
}
