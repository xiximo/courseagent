import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteCourseAgentLead,
  listCourseAgentLeads,
  listCourseAgents,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import type {
  CourseAgentLeadSummary,
  CourseAgentSummary,
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
      return role || '—'
  }
}

function formatProfile(lead: CourseAgentLeadSummary) {
  const c = lead.profile?.constraints || {}
  const parts = [c.city, c.date, c.format, c.goal].filter(Boolean)
  return parts.length ? parts.join(' · ') : '—'
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

export function AgentLeadsPage() {
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [leads, setLeads] = useState<CourseAgentLeadSummary[]>([])
  const [agents, setAgents] = useState<CourseAgentSummary[]>([])
  const [agentFilter, setAgentFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [deleteTarget, setDeleteTarget] = useState<CourseAgentLeadSummary | null>(
    null
  )
  const [deleting, setDeleting] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      const [leadRows, agentRows] = await Promise.all([
        listCourseAgentLeads({
          agentId: agentFilter === 'all' ? undefined : agentFilter,
          limit: 100,
        }),
        listCourseAgents(),
      ])
      setLeads(leadRows)
      setAgents(agentRows)
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载客户线索失败')
      setLeads([])
    } finally {
      setLoading(false)
    }
  }, [agentFilter])

  useEffect(() => {
    void reload()
  }, [reload])

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const result = await deleteCourseAgentLead(deleteTarget.id)
      setDeleteTarget(null)
      toast.success(result.message || '线索已删除')
      setLeads((prev) => prev.filter((item) => item.id !== deleteTarget.id))
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className='flex flex-col gap-4'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h2 className='text-2xl font-bold tracking-tight'>客户线索</h2>
          <p className='text-muted-foreground'>
            每次公开对话开始或「重新开始」记为一次客户咨询，可查看 IP、画像与完整对话
          </p>
        </div>
        <div className='flex items-center gap-2'>
          <Select value={agentFilter} onValueChange={setAgentFilter}>
            <SelectTrigger className='w-[220px]'>
              <SelectValue placeholder='筛选 Agent' />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>全部 Agent</SelectItem>
              {agents.map((a) => (
                <SelectItem key={a.agentId} value={a.agentId}>
                  {a.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type='button' variant='outline' onClick={() => void reload()}>
            刷新
          </Button>
        </div>
      </div>

      {error ? <AppErrorAlert message={error} /> : null}

      {loading ? (
        <p className='text-muted-foreground'>加载中…</p>
      ) : leads.length === 0 ? (
        <p className='text-muted-foreground'>
          暂无客户线索。访客在公开对话页咨询后会出现在此。
        </p>
      ) : (
        <div className='rounded-md border'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>开始时间</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>IP</TableHead>
                <TableHead>身份</TableHead>
                <TableHead>画像摘要</TableHead>
                <TableHead>消息</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className='text-right'>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.map((lead) => (
                <TableRow key={lead.id}>
                  <TableCell className='whitespace-nowrap text-sm'>
                    {formatTime(lead.startedAt)}
                  </TableCell>
                  <TableCell>
                    <div className='font-medium'>{lead.agentName}</div>
                    <div className='text-muted-foreground text-xs'>
                      #{lead.consultationIndex} · {lead.title}
                    </div>
                  </TableCell>
                  <TableCell className='font-mono text-sm'>
                    {lead.clientIp || '—'}
                  </TableCell>
                  <TableCell>{roleLabel(lead.role)}</TableCell>
                  <TableCell className='max-w-[220px] truncate text-sm'>
                    {formatProfile(lead)}
                  </TableCell>
                  <TableCell>{lead.messageCount}</TableCell>
                  <TableCell>
                    <Badge
                      variant={lead.status === 'open' ? 'default' : 'secondary'}
                    >
                      {lead.status === 'open' ? '进行中' : '已结束'}
                    </Badge>
                  </TableCell>
                  <TableCell className='text-right'>
                    <div className='flex items-center justify-end gap-1'>
                      <Button asChild variant='ghost' size='sm'>
                        <Link
                          to='/admin/course-agents/leads/$leadId'
                          params={{ leadId: lead.id }}
                        >
                          详情
                        </Link>
                      </Button>
                      {canConfig ? (
                        <Button
                          type='button'
                          variant='ghost'
                          size='sm'
                          className='text-destructive hover:text-destructive'
                          onClick={() => setDeleteTarget(lead)}
                        >
                          <Trash2 className='size-4' />
                          <span className='sr-only'>删除</span>
                        </Button>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除客户线索'
        desc={
          deleteTarget ? (
            <>
              确定删除「{deleteTarget.title}」（#{deleteTarget.consultationIndex}
              ）吗？线索记录将删除，会话中的消息仍会保留，且不可恢复。
            </>
          ) : (
            ''
          )
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
