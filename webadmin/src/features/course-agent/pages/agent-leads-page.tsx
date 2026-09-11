import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ChevronDown, MessageSquare, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteAdminSessionRecord,
  listAdminSessionRecords,
  listCourseAgents,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
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
import { cn } from '@/lib/utils'
import type {
  AdminSessionRecord,
  AdminUserSessionGroup,
  CourseAgentSummary,
} from '../data/types'

function formatTime(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function AgentLeadsPage() {
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const [groups, setGroups] = useState<AdminUserSessionGroup[]>([])
  const [agents, setAgents] = useState<CourseAgentSummary[]>([])
  const [agentFilter, setAgentFilter] = useState<string>('all')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [openUsers, setOpenUsers] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [deleteTarget, setDeleteTarget] = useState<AdminSessionRecord | null>(
    null
  )
  const [deleting, setDeleting] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      const [sessionGroups, agentRows] = await Promise.all([
        listAdminSessionRecords({
          agentId: agentFilter === 'all' ? undefined : agentFilter,
          from: fromDate ? `${fromDate}T00:00:00` : undefined,
          to: toDate ? `${toDate}T23:59:59` : undefined,
        }),
        listCourseAgents(),
      ])
      setGroups(sessionGroups)
      setAgents(agentRows)
      setOpenUsers(
        new Set(
          sessionGroups.map((group) => group.userId ?? `guest:${group.username}`)
        )
      )
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载会话记录失败')
      setGroups([])
    } finally {
      setLoading(false)
    }
  }, [agentFilter, fromDate, toDate])

  useEffect(() => {
    void reload()
  }, [reload])

  const totalSessions = useMemo(
    () => groups.reduce((sum, group) => sum + group.sessionCount, 0),
    [groups]
  )

  const toggleUser = (key: string) => {
    setOpenUsers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteAdminSessionRecord(deleteTarget.id)
      setDeleteTarget(null)
      toast.success('会话已删除')
      await reload()
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
          <h2 className='text-2xl font-bold tracking-tight'>用户会话记录</h2>
          <p className='text-muted-foreground'>
            按登录用户查看全部对话历史（已脱敏）。共 {groups.length} 位用户、
            {totalSessions} 条会话。
          </p>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <Input
            type='date'
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className='w-[150px]'
          />
          <span className='text-muted-foreground text-sm'>至</span>
          <Input
            type='date'
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className='w-[150px]'
          />
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
      ) : groups.length === 0 ? (
        <p className='text-muted-foreground'>
          暂无会话记录。用户登录后在对话页提问会出现在此。
        </p>
      ) : (
        <div className='space-y-3'>
          {groups.map((group) => {
            const key = group.userId ?? `guest:${group.username}`
            const open = openUsers.has(key)
            return (
              <Collapsible
                key={key}
                open={open}
                onOpenChange={() => toggleUser(key)}
              >
                <div className='overflow-hidden rounded-xl border bg-card'>
                  <CollapsibleTrigger asChild>
                    <button
                      type='button'
                      className='hover:bg-muted/50 flex w-full items-center gap-3 px-4 py-3 text-left'
                    >
                      <ChevronDown
                        className={cn(
                          'text-muted-foreground size-4 shrink-0 transition-transform',
                          open ? 'rotate-0' : '-rotate-90'
                        )}
                      />
                      <div className='min-w-0 flex-1'>
                        <div className='flex flex-wrap items-center gap-2'>
                          <span className='font-medium'>{group.fullName}</span>
                          <span className='text-muted-foreground font-mono text-xs'>
                            @{group.username}
                          </span>
                          {group.personaLabel ? (
                            <Badge variant='secondary'>{group.personaLabel}</Badge>
                          ) : null}
                        </div>
                        <div className='text-muted-foreground mt-0.5 text-xs'>
                          {group.sessionCount} 条会话
                          {group.lastActiveAt
                            ? ` · 最近 ${formatTime(group.lastActiveAt)}`
                            : ''}
                        </div>
                      </div>
                    </button>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div className='border-t'>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>会话</TableHead>
                            <TableHead>Agent</TableHead>
                            <TableHead>消息</TableHead>
                            <TableHead>更新时间</TableHead>
                            <TableHead className='text-right'>操作</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {group.sessions.map((session) => (
                            <TableRow key={session.id}>
                              <TableCell>
                                <div className='flex items-center gap-2'>
                                  <MessageSquare className='text-muted-foreground size-3.5 shrink-0' />
                                  <span className='font-medium'>
                                    {session.title || '新对话'}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell className='text-sm'>
                                {session.agentName}
                              </TableCell>
                              <TableCell>{session.messageCount}</TableCell>
                              <TableCell className='whitespace-nowrap text-sm'>
                                {formatTime(session.updatedAt)}
                              </TableCell>
                              <TableCell className='text-right'>
                                <div className='flex items-center justify-end gap-1'>
                                  <Button asChild variant='ghost' size='sm'>
                                    <Link
                                      to='/admin/course-agents/leads/$leadId'
                                      params={{ leadId: session.id }}
                                    >
                                      查看
                                    </Link>
                                  </Button>
                                  {canConfig ? (
                                    <Button
                                      type='button'
                                      variant='ghost'
                                      size='sm'
                                      className='text-destructive hover:text-destructive'
                                      onClick={() => setDeleteTarget(session)}
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
                  </CollapsibleContent>
                </div>
              </Collapsible>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除会话记录'
        desc={
          deleteTarget
            ? `确定删除「${deleteTarget.title || '新对话'}」吗？对话内容将一并删除，且不可恢复。`
            : ''
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
