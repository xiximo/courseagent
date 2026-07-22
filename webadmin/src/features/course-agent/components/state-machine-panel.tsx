import type { CourseAgentStateStep } from '../data/types'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'

type StateMachinePanelProps = {
  steps: CourseAgentStateStep[]
  readOnly?: boolean
}

export function StateMachinePanel({ steps, readOnly }: StateMachinePanelProps) {
  return (
    <div className='space-y-4'>
      <Card>
        <CardHeader>
          <CardTitle>七步状态机</CardTitle>
          <CardDescription>
            显式 FSM 主编排：身份未明不推荐 · 约束≥2 才推荐 · reset 清空上下文
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className='flex flex-wrap items-center gap-2 text-sm'>
            {steps.map((step, i) => (
              <div key={step.id} className='flex items-center gap-2'>
                <div
                  className={`rounded-lg border px-3 py-2 ${
                    step.enabled ? 'border-primary/30 bg-primary/5' : 'opacity-50'
                  }`}
                >
                  <div className='font-medium'>{step.label}</div>
                  <div className='text-xs text-muted-foreground'>
                    {step.description}
                  </div>
                </div>
                {i < steps.length - 1 ? (
                  <span className='text-muted-foreground'>→</span>
                ) : null}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>步骤配置</CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          {steps.map((step) => (
            <div
              key={step.id}
              className='flex items-start justify-between gap-4 rounded-lg border p-4'
            >
              <div>
                <div className='flex items-center gap-2'>
                  <span className='font-medium'>{step.label}</span>
                  <Badge variant='outline'>{step.id}</Badge>
                </div>
                <p className='mt-1 text-sm text-muted-foreground'>
                  {step.description}
                </p>
              </div>
              <Switch checked={step.enabled} disabled={readOnly} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
