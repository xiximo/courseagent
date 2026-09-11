import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { Bot, MessageSquare, Plus, Star, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteCourseAgent,
  listCourseAgents,
  setDefaultCourseAgent,
} from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Main } from '@/components/layout/main'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { getBillingMe } from '@/lib/api/billing'
import {
  useAgentConsolePaths,
  useIsPlatformConsole,
} from '@/lib/auth/console-paths'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import {
  agentTypeLabel,
  CreateAgentDialog,
} from '../components/create-agent-dialog'
import { useInvalidateCourseAgents } from '../hooks/use-course-agents-query'
import { isAgentVisibleInChat } from '../lib/agent-schedule'
import type { CourseAgentSummary } from '../data/types'

function statusLabel(status: CourseAgentSummary['status']) {
  switch (status) {
    case 'active':
      return '已发布'
    case 'draft':
      return '草稿'
    case 'disabled':
      return '已停用'
  }
}

function statusVariant(status: CourseAgentSummary['status']) {
  switch (status) {
    case 'active':
      return 'default' as const
    case 'draft':
      return 'secondary' as const
    case 'disabled':
      return 'outline' as const
  }
}

export function CourseAgentsListPage() {
  const navigate = useNavigate()
  const { can } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const platform = useIsPlatformConsole()
  const agentPaths = useAgentConsolePaths()
  const [canUseHarness, setCanUseHarness] = useState(platform)
  const [agents, setAgents] = useState<CourseAgentSummary[]>([])
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<CourseAgentSummary | null>(
    null
  )
  const [deleting, setDeleting] = useState(false)
  const [settingDefaultId, setSettingDefaultId] = useState<string | null>(null)
  const invalidateAgents = useInvalidateCourseAgents()

  const loadAgents = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setAgents(await listCourseAgents())
      if (!platform) {
        try {
          const mine = await getBillingMe()
          setCanUseHarness(Boolean(mine.canUseHarnessAgent))
        } catch {
          setCanUseHarness(false)
        }
      }
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [platform])

  useEffect(() => {
    void loadAgents()
  }, [loadAgents])

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const result = await deleteCourseAgent(deleteTarget.agentId)
      setDeleteTarget(null)
      toast.success(result.message || 'Agent 已删除')
      invalidateAgents()
      await loadAgents()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleSetDefault = async (agent: CourseAgentSummary) => {
    if (agent.isDefault) return
    setSettingDefaultId(agent.agentId)
    try {
      await setDefaultCourseAgent(agent.agentId)
      toast.success(`已将「${agent.name}」设为默认`)
      invalidateAgents()
      await loadAgents()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '设置默认失败')
    } finally {
      setSettingDefaultId(null)
    }
  }

  const activeCount = agents.filter((a) => a.status === 'active').length
  const draftCount = agents.filter((a) => a.status === 'draft').length

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>顾问配置</h2>
            <p className='text-muted-foreground'>
              {platform
                ? '配置平台模板顾问。各机构在自己的顾问配置里维护，互不影响。'
                : '只管理本机构顾问。左侧对话入口仅展示本机构已发布的版本。'}
            </p>
          </div>
          <Button
            type='button'
            disabled={!canConfig}
            onClick={() => setCreateOpen(true)}
          >
            <Plus className='mr-1 size-4' />
            新建 Agent
          </Button>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        <div className='grid gap-4 sm:grid-cols-3'>
          <Card>
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium'>Agent 总数</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{agents.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium'>已发布</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{activeCount}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium'>草稿</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{draftCount}</div>
            </CardContent>
          </Card>
        </div>

        {loading ? (
          <p className='text-muted-foreground'>加载中…</p>
        ) : agents.length === 0 ? (
          <p className='text-muted-foreground text-sm'>
            暂无顾问。请点击「新建 Agent」创建。
          </p>
        ) : (
          <div className='grid gap-4 md:grid-cols-2'>
            {agents.map((agent) => (
              <Card key={agent.agentId} className='hover:border-primary/40 transition-colors'>
                <CardHeader className='flex flex-row items-start gap-3'>
                  <div className='bg-primary/10 text-primary flex size-11 shrink-0 items-center justify-center rounded-lg'>
                    <Bot className='size-5' />
                  </div>
                  <div className='min-w-0 flex-1'>
                    <div className='flex flex-wrap items-center gap-2'>
                      <CardTitle className='text-base'>{agent.name}</CardTitle>
                      {agent.isDefault ? (
                        <Badge variant='default'>默认</Badge>
                      ) : null}
                      <Badge variant={statusVariant(agent.status)}>
                        {statusLabel(agent.status)}
                      </Badge>
                      <Badge variant='outline'>
                        {agentTypeLabel(agent.agentType ?? 'workflow')}
                      </Badge>
                    </div>
                    <CardDescription className='mt-1 line-clamp-2'>
                      {agent.description}
                    </CardDescription>
                    <p className='text-muted-foreground mt-2 font-mono text-xs'>
                      {agent.agentId}
                    </p>
                  </div>
                </CardHeader>
                <CardContent className='flex flex-wrap gap-2'>
                  <Button size='sm' asChild>
                    <Link
                      to={agentPaths.detail}
                      params={{ agentId: agent.agentId }}
                    >
                      配置管理
                    </Link>
                  </Button>
                  {isAgentVisibleInChat(agent) ? (
                    <Button size='sm' asChild>
                      <Link
                        to='/admin/chat/$agentId'
                        params={{ agentId: agent.agentId }}
                      >
                        <MessageSquare className='mr-1 size-3.5' />
                        进入对话
                      </Link>
                    </Button>
                  ) : null}
                  <Button
                    type='button'
                    size='sm'
                    variant='outline'
                    disabled={
                      !canConfig ||
                      Boolean(agent.isDefault) ||
                      settingDefaultId === agent.agentId
                    }
                    onClick={() => void handleSetDefault(agent)}
                  >
                    <Star
                      className={`mr-1 size-3.5 ${agent.isDefault ? 'fill-current' : ''}`}
                    />
                    {agent.isDefault ? '当前默认' : '设为默认'}
                  </Button>
                  <Button
                    type='button'
                    size='sm'
                    variant='outline'
                    className='text-destructive hover:text-destructive'
                    disabled={!canConfig}
                    onClick={() => setDeleteTarget(agent)}
                  >
                    <Trash2 className='mr-1 size-3.5' />
                    删除
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </Main>

      <CreateAgentDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        allowedTypes={
          platform
            ? undefined
            : canUseHarness
              ? ['basic', 'autonomous']
              : ['basic']
        }
        onCreated={(agentId) => {
          invalidateAgents()
          void loadAgents()
          void navigate({
            to: agentPaths.detail,
            params: { agentId },
          })
        }}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除 Agent'
        desc={
          deleteTarget ? (
            <>
              确定删除「{deleteTarget.name}」吗？将同时删除其会话、模型配置与关联知识库文档，且不可恢复。
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
    </>
  )
}
