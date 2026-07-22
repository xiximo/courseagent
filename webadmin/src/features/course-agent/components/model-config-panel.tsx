import type { CourseAgentModelConfig } from '../data/types'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'

type ModelConfigPanelProps = {
  model: CourseAgentModelConfig
  readOnly?: boolean
}

export function ModelConfigPanel({ model, readOnly }: ModelConfigPanelProps) {
  void readOnly

  return (
    <Card>
      <CardHeader>
        <CardTitle>当前启用模型</CardTitle>
        <CardDescription>
          详细配置请在模型列表中编辑；API Key 存于数据库且接口脱敏返回。
        </CardDescription>
      </CardHeader>
      <CardContent className='grid gap-4 md:grid-cols-2'>
        <div className='space-y-1'>
          <Label>提供商</Label>
          <p className='text-sm'>{model.provider}</p>
        </div>
        <div className='space-y-1'>
          <Label>流式输出</Label>
          <Badge variant={model.stream ? 'default' : 'secondary'}>
            {model.stream ? '已启用' : '关闭'}
          </Badge>
        </div>
        <div className='space-y-1 md:col-span-2'>
          <Label>模型名称</Label>
          <p className='text-sm'>{model.modelName || '—'}</p>
        </div>
        <div className='space-y-1 md:col-span-2'>
          <Label>Endpoint ID</Label>
          <p className='text-sm'>{model.endpointId || '—'}</p>
        </div>
        <div className='space-y-1 md:col-span-2'>
          <Label>Base URL</Label>
          <p className='text-sm'>{model.baseUrl || '—'}</p>
        </div>
      </CardContent>
    </Card>
  )
}
