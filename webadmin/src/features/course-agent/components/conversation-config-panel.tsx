import type { CourseAgentConversationConfig } from '../data/types'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type ConversationConfigPanelProps = {
  config: CourseAgentConversationConfig
  readOnly?: boolean
  onChange?: (c: CourseAgentConversationConfig) => void
}

export function ConversationConfigPanel({
  config,
  readOnly,
  onChange,
}: ConversationConfigPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>对话体验</CardTitle>
        <CardDescription>欢迎语、快捷按钮与异常提示模板（固定文案，无需 LLM）</CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='space-y-2'>
          <Label>欢迎语</Label>
          <Textarea
            disabled={readOnly}
            rows={3}
            value={config.welcomeMessage}
            onChange={(e) =>
              onChange?.({ ...config, welcomeMessage: e.target.value })
            }
          />
        </div>
        <div className='space-y-2'>
          <Label>快捷按钮（逗号分隔）</Label>
          <Input
            disabled={readOnly}
            value={config.menuButtons.join('，')}
            onChange={(e) =>
              onChange?.({
                ...config,
                menuButtons: e.target.value.split(/[,，]/).map((s) => s.trim()),
              })
            }
          />
        </div>
        <div className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <Label>空输入提示</Label>
            <Input
              disabled={readOnly}
              value={config.emptyInputMessage}
              onChange={(e) =>
                onChange?.({ ...config, emptyInputMessage: e.target.value })
              }
            />
          </div>
          <div className='space-y-2'>
            <Label>超长输入提示</Label>
            <Input
              disabled={readOnly}
              value={config.tooLongMessage}
              onChange={(e) =>
                onChange?.({ ...config, tooLongMessage: e.target.value })
              }
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
