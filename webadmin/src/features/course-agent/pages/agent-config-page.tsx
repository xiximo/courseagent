import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ArrowLeft, MessageSquare, Play } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import { runCourseAgentSchedule, updateCourseAgent } from '@/lib/api/course-agent'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { agentTypeLabel } from '../components/create-agent-dialog'
import { BasicAgentConfigWorkspace } from '../components/basic-agent-config-workspace'
import { ReactAgentConfigWorkspace } from '../components/react-agent-config-workspace'
import { WorkflowAgentConfigWorkspace } from '../components/workflow-agent-config-workspace'
import {
  AgentConfigProvider,
  useAgentConfig,
} from '../context/agent-config-context'
import { useInvalidateCourseAgents } from '../hooks/use-course-agents-query'
import { isAgentVisibleInChat, isScheduledHarnessAgent } from '../lib/agent-schedule'
import type { CourseAgentStatus } from '../data/types'

type AgentConfigPageProps = {
  agentId: string
}

function AgentConfigWorkspace() {
  const { config, canConfig, setConfig } = useAgentConfig()
  if (!config) return null

  if (config.agentType === 'basic') {
    return (
      <BasicAgentConfigWorkspace
        config={config}
        canConfig={canConfig}
        onSaved={setConfig}
      />
    )
  }

  if (config.agentType === 'workflow') {
    return (
      <WorkflowAgentConfigWorkspace
        config={config}
        canConfig={canConfig}
        onSaved={setConfig}
      />
    )
  }

  if (config.agentType === 'autonomous') {
    return (
      <ReactAgentConfigWorkspace
        config={config}
        canConfig={canConfig}
        onSaved={setConfig}
      />
    )
  }

  return (
    <div className='rounded-xl border p-8 text-center'>
      <p className='text-muted-foreground text-sm'>未知的智能体类型。</p>
    </div>
  )
}

function AgentConfigPageBody() {
  const { config, loading, error, canConfig, setConfig } = useAgentConfig()
  const [runningSchedule, setRunningSchedule] = useState(false)
  const invalidateAgents = useInvalidateCourseAgents()

  if (loading) {
    return <p className='text-muted-foreground'>加载中…</p>
  }

  if (error) {
    return <AppErrorAlert message={error} />
  }

  if (!config) return null

  const handleStatusChange = async (status: CourseAgentStatus) => {
    try {
      const updated = await updateCourseAgent(config.agentId, { status })
      setConfig(updated)
      invalidateAgents()
      toast.success(
        status === 'active'
          ? '已发布，可在左侧导航进入对话'
          : '状态已更新'
      )
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '更新状态失败')
    }
  }

  const handleRunSchedule = async () => {
    setRunningSchedule(true)
    try {
      const updated = await runCourseAgentSchedule(config.agentId)
      setConfig(updated)
      invalidateAgents()
      toast.success(updated.schedule?.lastRunNote || '定时任务已执行')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '执行失败')
    } finally {
      setRunningSchedule(false)
    }
  }

  return (
    <div className='flex min-h-0 flex-1 flex-col gap-4'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div className='space-y-2'>
          <Button variant='ghost' size='sm' asChild className='-ml-2 h-8 px-2'>
            <Link to='/admin/course-agents'>
              <ArrowLeft className='mr-1 size-4' />
              返回列表
            </Link>
          </Button>
          <div className='flex flex-wrap items-center gap-2'>
            <h1 className='text-2xl font-bold tracking-tight'>{config.name}</h1>
            <Badge variant='outline'>
              {agentTypeLabel(config.agentType ?? 'workflow')}
            </Badge>
            <Badge variant={config.status === 'active' ? 'default' : 'secondary'}>
              {config.status === 'active'
                ? '已发布'
                : config.status === 'draft'
                  ? '草稿'
                  : '已停用'}
            </Badge>
          </div>
          <p className='text-muted-foreground font-mono text-xs'>
            {config.agentId}
          </p>
        </div>
        <div className='flex flex-wrap items-end gap-3'>
          <div className='space-y-1.5'>
            <Label className='text-xs'>发布状态</Label>
            <Select
              value={config.status}
              disabled={!canConfig}
              onValueChange={(v) => void handleStatusChange(v as CourseAgentStatus)}
            >
              <SelectTrigger className='w-[140px]'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='draft'>草稿</SelectItem>
                <SelectItem value='active'>发布</SelectItem>
                <SelectItem value='disabled'>停用</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {isScheduledHarnessAgent(config) ? (
            <Button
              size='sm'
              variant='outline'
              disabled={!canConfig || runningSchedule}
              onClick={() => void handleRunSchedule()}
            >
              <Play className='mr-1 size-4' />
              {runningSchedule ? '执行中…' : '立即执行'}
            </Button>
          ) : null}
          {isAgentVisibleInChat(config) ? (
            <Button size='sm' asChild>
              <Link to='/admin/chat/$agentId' params={{ agentId: config.agentId }}>
                <MessageSquare className='mr-1 size-4' />
                进入对话
              </Link>
            </Button>
          ) : null}
        </div>
      </div>

      <div className='flex min-h-0 flex-1 flex-col'>
        <AgentConfigWorkspace />
      </div>
    </div>
  )
}

export function AgentConfigPage({ agentId }: AgentConfigPageProps) {
  const { can } = useAppPermissions()

  return (
    <>
      <AppPageHeader />
      <Main className='flex min-h-0 flex-1 flex-col gap-4 sm:gap-6'>
        <AgentConfigProvider
          agentId={agentId}
          canConfig={can('course_agent_config')}
        >
          <AgentConfigPageBody />
        </AgentConfigProvider>
      </Main>
    </>
  )
}
