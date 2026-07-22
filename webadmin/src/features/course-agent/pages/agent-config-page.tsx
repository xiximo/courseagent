import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import { updateCourseAgent } from '@/lib/api/course-agent'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { agentTypeLabel } from '../components/create-agent-dialog'
import { BasicAgentConfigWorkspace } from '../components/basic-agent-config-workspace'
import { EmbedConfigPanel } from '../components/embed-config-panel'
import { WorkflowAgentConfigWorkspace } from '../components/workflow-agent-config-workspace'
import {
  AgentConfigProvider,
  useAgentConfig,
} from '../context/agent-config-context'
import type { CourseAgentEmbedConfig, CourseAgentStatus } from '../data/types'

type AgentConfigPageProps = {
  agentId: string
}

type ConfigPageTab = 'config' | 'embed'

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

  return (
    <div className='rounded-xl border p-8 text-center'>
      <p className='text-muted-foreground text-sm'>
        自主型 Agent 配置页即将扩展；当前可先通过对话预览验证能力。
      </p>
      <div className='mt-4 flex flex-wrap justify-center gap-2'>
        <Button size='sm' asChild>
          <Link
            to='/admin/course-agents/$agentId/preview'
            params={{ agentId: config.agentId }}
            target='_blank'
          >
            对话预览
          </Link>
        </Button>
      </div>
    </div>
  )
}

function AgentConfigPageBody() {
  const { config, loading, error, canConfig, setConfig } = useAgentConfig()
  const [pageTab, setPageTab] = useState<ConfigPageTab>('config')

  const isPublished = config?.status === 'active'

  useEffect(() => {
    if (!isPublished && pageTab === 'embed') {
      setPageTab('config')
    }
  }, [isPublished, pageTab])

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
      toast.success(
        status === 'active' ? '已启用，可用于公开对话页' : '状态已更新'
      )
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '更新状态失败')
    }
  }

  const handleEmbedSave = async (embed: CourseAgentEmbedConfig) => {
    const updated = await updateCourseAgent(config.agentId, { embed })
    setConfig(updated)
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
                ? '已启用'
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
                <SelectItem value='active'>启用</SelectItem>
                <SelectItem value='disabled'>停用</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button size='sm' variant='outline' asChild>
            <Link
              to='/admin/course-agents/$agentId/preview'
              params={{ agentId: config.agentId }}
              target='_blank'
            >
              预览对话
            </Link>
          </Button>
        </div>
      </div>

      <Tabs
        value={pageTab}
        onValueChange={(v) => setPageTab(v as ConfigPageTab)}
        className='flex min-h-0 flex-1 flex-col gap-4'
      >
        <TabsList>
          <TabsTrigger value='config'>配置</TabsTrigger>
          {isPublished ? (
            <TabsTrigger value='embed'>接入配置</TabsTrigger>
          ) : null}
        </TabsList>

        <TabsContent
          value='config'
          className='mt-0 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden'
          forceMount
        >
          <AgentConfigWorkspace />
        </TabsContent>

        {isPublished ? (
          <TabsContent
            value='embed'
            className='mt-0 min-h-0 flex-1 overflow-y-auto data-[state=inactive]:hidden'
          >
            <div className='mb-4 space-y-1'>
              <h2 className='text-lg font-semibold'>接入配置</h2>
              <p className='text-muted-foreground text-sm'>
                公开对话页链接、嵌入代码与域名白名单（仅已启用时可配置）
              </p>
            </div>
            <EmbedConfigPanel
              agentId={config.agentId}
              embed={config.embed}
              readOnly={!canConfig}
              onSave={handleEmbedSave}
            />
          </TabsContent>
        ) : null}
      </Tabs>
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
