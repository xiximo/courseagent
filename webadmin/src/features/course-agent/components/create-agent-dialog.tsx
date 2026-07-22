import { useState } from 'react'
import { Bot, GitBranch, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import { createCourseAgent } from '@/lib/api/course-agent'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { CourseAgentType } from '../data/types'

const AGENT_TYPE_OPTIONS: {
  type: CourseAgentType
  title: string
  description: string
  icon: typeof Bot
}[] = [
  {
    type: 'basic',
    title: '基础型',
    description: '知识库 + LLM 直接问答，无状态机流程，适合快速上线。',
    icon: Bot,
  },
  {
    type: 'workflow',
    title: 'Workflow',
    description: '七步状态机驱动：身份澄清、约束采集、推荐、问答与报名引导。',
    icon: GitBranch,
  },
  {
    type: 'autonomous',
    title: '自主性',
    description: '更高自主度，LLM 自主理解意图并规划多轮对话（POC）。',
    icon: Sparkles,
  },
]

type CreateAgentDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: (agentId: string) => void
}

export function CreateAgentDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateAgentDialogProps) {
  const [agentType, setAgentType] = useState<CourseAgentType>('workflow')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setAgentType('workflow')
    setName('')
    setDescription('')
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) reset()
    onOpenChange(next)
  }

  const handleSubmit = async () => {
    const trimmedName = name.trim()
    if (!trimmedName) {
      toast.error('请输入 Agent 名称')
      return
    }

    setSubmitting(true)
    try {
      const created = await createCourseAgent({
        name: trimmedName,
        description: description.trim(),
        agentType,
      })
      toast.success('Agent 已创建')
      handleOpenChange(false)
      onCreated?.(created.agentId)
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>新建 Agent</DialogTitle>
          <DialogDescription>
            选择 Agent 类型并填写基本信息，创建后可在配置页继续完善。
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-4 py-2'>
          <div className='space-y-2'>
            <Label>Agent 类型</Label>
            <div className='grid gap-2'>
              {AGENT_TYPE_OPTIONS.map((option) => {
                const Icon = option.icon
                const selected = agentType === option.type
                return (
                  <button
                    key={option.type}
                    type='button'
                    className={cn(
                      'hover:bg-muted/60 flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                      selected && 'border-primary bg-primary/5 ring-1 ring-primary'
                    )}
                    onClick={() => setAgentType(option.type)}
                  >
                    <div
                      className={cn(
                        'mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md',
                        selected
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      <Icon className='size-4' />
                    </div>
                    <div className='min-w-0'>
                      <p className='text-sm font-medium'>{option.title}</p>
                      <p className='text-muted-foreground mt-0.5 text-xs leading-relaxed'>
                        {option.description}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          <div className='space-y-2'>
            <Label htmlFor='agent-name'>名称</Label>
            <Input
              id='agent-name'
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder='例如：暑期咨询 Agent'
              maxLength={128}
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='agent-description'>描述（可选）</Label>
            <Textarea
              id='agent-description'
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder='简要说明该 Agent 的服务场景'
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            type='button'
            variant='outline'
            disabled={submitting}
            onClick={() => handleOpenChange(false)}
          >
            取消
          </Button>
          <Button type='button' disabled={submitting} onClick={() => void handleSubmit()}>
            {submitting ? '创建中…' : '创建 Agent'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function agentTypeLabel(type: CourseAgentType): string {
  return AGENT_TYPE_OPTIONS.find((item) => item.type === type)?.title ?? type
}
