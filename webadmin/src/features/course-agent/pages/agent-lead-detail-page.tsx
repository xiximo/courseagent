import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteCourseAgentLead,
  getCourseAgentLead,
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
  CourseAgentCitation,
  CourseAgentLeadDetail,
} from '../data/types'

function roleLabel(role: string | null | undefined) {
  switch (role) {
    case 'student':
      return '学生'
    case 'teacher':
      return '教师'
    case 'org':
      return '机构'
    default:
      return role || '未识别'
  }
}

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
  const navigate = useNavigate()
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [lead, setLead] = useState<CourseAgentLeadDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [activeCitation, setActiveCitation] =
    useState<CourseAgentCitation | null>(null)
  const [citationSheetOpen, setCitationSheetOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(undefined)
      try {
        const detail = await getCourseAgentLead(leadId)
        if (!cancelled) setLead(detail)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiClientError ? e.message : '加载线索详情失败')
          setLead(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [leadId])

  const uiMessages: CourseAgentUiMessage[] = useMemo(() => {
    if (!lead) return []
    return lead.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: new Date(m.createdAt),
      citations: m.citations,
    }))
  }, [lead])

  const handleDeleteConfirm = async () => {
    setDeleting(true)
    try {
      const result = await deleteCourseAgentLead(leadId)
      toast.success(result.message || '线索已删除')
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

  if (!lead) {
    return <p className='text-muted-foreground'>线索不存在</p>
  }

  const constraints = lead.profile?.constraints || {}

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
            {lead.title}
          </h2>
          <p className='text-muted-foreground text-sm'>
            {lead.agentName} · 第 {lead.consultationIndex} 次咨询
          </p>
        </div>
        <Badge variant={lead.status === 'open' ? 'default' : 'secondary'}>
          {lead.status === 'open' ? '进行中' : '已结束'}
        </Badge>
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
          <div className='text-muted-foreground'>访客 IP</div>
          <div className='font-mono'>{lead.clientIp || '—'}</div>
        </div>
        <div>
          <div className='text-muted-foreground'>身份</div>
          <div>{roleLabel(lead.role)}</div>
        </div>
        <div>
          <div className='text-muted-foreground'>开始 / 结束</div>
          <div>
            {formatTime(lead.startedAt)}
            {lead.endedAt ? ` → ${formatTime(lead.endedAt)}` : ''}
          </div>
        </div>
        <div>
          <div className='text-muted-foreground'>城市 / 日期</div>
          <div>
            {[constraints.city, constraints.date].filter(Boolean).join(' · ') ||
              '—'}
          </div>
        </div>
        <div>
          <div className='text-muted-foreground'>形式 / 目标</div>
          <div>
            {[constraints.format, constraints.goal].filter(Boolean).join(' · ') ||
              '—'}
          </div>
        </div>
        <div>
          <div className='text-muted-foreground'>来源</div>
          <div className='truncate' title={lead.origin || undefined}>
            {lead.origin || '—'}
          </div>
        </div>
        {lead.userAgent ? (
          <div className='sm:col-span-2 lg:col-span-3'>
            <div className='text-muted-foreground'>User-Agent</div>
            <div className='text-muted-foreground break-all text-xs'>
              {lead.userAgent}
            </div>
          </div>
        ) : null}
      </div>

      <div className='rounded-md border p-4'>
        <h3 className='mb-4 font-semibold'>对话过程（{lead.messageCount} 条）</h3>
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
        title='删除客户线索'
        desc={
          <>
            确定删除「{lead.title}」（#{lead.consultationIndex}
            ）吗？线索记录将删除，会话中的消息仍会保留，且不可恢复。
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
