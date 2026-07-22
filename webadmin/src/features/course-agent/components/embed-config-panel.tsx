import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import type { CourseAgentEmbedConfig } from '../data/types'
import {
  getMockEmbedSnippet,
  getMockPublicChatUrl,
} from '../mock/course-agent-handlers'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CopyButton } from '@/components/ui/copy-button'

type EmbedConfigPanelProps = {
  agentId: string
  embed: CourseAgentEmbedConfig
  readOnly?: boolean
  onSave?: (embed: CourseAgentEmbedConfig) => Promise<void>
}

export function EmbedConfigPanel({
  agentId,
  embed,
  readOnly,
  onSave,
}: EmbedConfigPanelProps) {
  const publicUrl = getMockPublicChatUrl(agentId)
  const snippet = getMockEmbedSnippet(agentId)
  const [origins, setOrigins] = useState(embed.allowedOrigins.join('\n'))
  const [position, setPosition] = useState(embed.position)
  const [theme, setTheme] = useState(embed.theme)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setOrigins(embed.allowedOrigins.join('\n'))
    setPosition(embed.position)
    setTheme(embed.theme)
  }, [embed])

  const handleSave = async () => {
    if (!onSave || readOnly) return
    const next: CourseAgentEmbedConfig = {
      embedKey: embed.embedKey,
      allowedOrigins: origins
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
      position,
      theme,
    }
    setSaving(true)
    try {
      await onSave(next)
      toast.success('接入配置已保存')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className='space-y-4'>
      <Card>
        <CardHeader>
          <CardTitle>独立对话页</CardTitle>
          <CardDescription>
            C 端无授权访问，扫码或链接直达（独立页不受来源域名限制）
          </CardDescription>
        </CardHeader>
        <CardContent className='flex flex-wrap items-center gap-2'>
          <code className='bg-muted flex-1 rounded-md px-3 py-2 text-sm'>
            {publicUrl}
          </code>
          <CopyButton content={publicUrl} copyMessage='已复制链接' />
          <Button variant='outline' size='sm' asChild>
            <a href={publicUrl} target='_blank' rel='noreferrer'>
              打开预览
            </a>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>JS 嵌入代码</CardTitle>
          <CardDescription>一行 script 嵌入机构官网</CardDescription>
        </CardHeader>
        <CardContent className='space-y-3'>
          <pre className='bg-muted overflow-x-auto rounded-md p-4 text-xs'>
            {snippet}
          </pre>
          <CopyButton content={snippet} copyMessage='已复制嵌入代码' />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>接入密钥</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <Label>embedKey（前端）</Label>
            <div className='flex gap-2'>
              <Input readOnly value={embed.embedKey} />
              <CopyButton content={embed.embedKey} copyMessage='已复制' />
            </div>
          </div>
          <div className='space-y-2'>
            <Label>挂件模式</Label>
            <Select
              disabled={readOnly}
              value={position}
              onValueChange={(v) =>
                setPosition(v as CourseAgentEmbedConfig['position'])
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='bottom-right'>右下角浮窗</SelectItem>
                <SelectItem value='inline'>页面内嵌</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label>主题</Label>
            <Select
              disabled={readOnly}
              value={theme}
              onValueChange={(v) =>
                setTheme(v as CourseAgentEmbedConfig['theme'])
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='light'>浅色</SelectItem>
                <SelectItem value='dark'>深色</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2 md:col-span-2'>
            <Label>域名白名单（每行一个）</Label>
            <textarea
              className='border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[80px] w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50'
              disabled={readOnly}
              value={origins}
              onChange={(e) => setOrigins(e.target.value)}
            />
          </div>
          {!readOnly && onSave ? (
            <Button type='button' disabled={saving} onClick={() => void handleSave()}>
              {saving ? '保存中…' : '保存接入配置'}
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
