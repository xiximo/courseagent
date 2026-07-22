import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  listPlatformKnowledgeBases,
  listPlatformModels,
  updateCourseAgent,
} from '@/lib/api/course-agent'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { AgentPreviewPanel } from './agent-preview-panel'
import { resolveBasicSystemPrompt } from '../lib/basic-system-prompt'
import type {
  CourseAgentConfig,
  CourseAgentKnowledgeBase,
  CourseAgentModelProfile,
} from '../data/types'

type BasicAgentConfigWorkspaceProps = {
  config: CourseAgentConfig
  canConfig: boolean
  onSaved: (config: CourseAgentConfig) => void
}

export function BasicAgentConfigWorkspace({
  config,
  canConfig,
  onSaved,
}: BasicAgentConfigWorkspaceProps) {
  const [name, setName] = useState(config.name)
  const [temperature, setTemperature] = useState(config.temperature ?? 0.3)
  const [welcomeMessage, setWelcomeMessage] = useState(
    config.conversation.welcomeMessage ?? ''
  )
  const [systemPrompt, setSystemPrompt] = useState(
    resolveBasicSystemPrompt(config.conversation.systemPrompt)
  )
  const [kbIds, setKbIds] = useState<string[]>(config.boundKnowledgeBaseIds ?? [])
  const [modelIds, setModelIds] = useState<string[]>(config.boundModelIds ?? [])
  const [catalogKbs, setCatalogKbs] = useState<CourseAgentKnowledgeBase[]>([])
  const [catalogModels, setCatalogModels] = useState<CourseAgentModelProfile[]>(
    []
  )
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [saving, setSaving] = useState(false)
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0)

  useEffect(() => {
    setName(config.name)
    setTemperature(config.temperature ?? 0.3)
    setWelcomeMessage(config.conversation.welcomeMessage ?? '')
    setSystemPrompt(resolveBasicSystemPrompt(config.conversation.systemPrompt))
    setKbIds(config.boundKnowledgeBaseIds ?? [])
    setModelIds(config.boundModelIds ?? [])
  }, [config])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoadingCatalog(true)
      try {
        const [kbs, models] = await Promise.all([
          listPlatformKnowledgeBases(),
          listPlatformModels(),
        ])
        if (!cancelled) {
          setCatalogKbs(kbs)
          setCatalogModels(models)
        }
      } catch (e) {
        if (!cancelled) {
          toast.error(e instanceof ApiClientError ? e.message : '加载资源目录失败')
        }
      } finally {
        if (!cancelled) setLoadingCatalog(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const toggleId = (
    list: string[],
    id: string,
    checked: boolean,
    setter: (next: string[]) => void
  ) => {
    if (checked) setter([...list, id])
    else setter(list.filter((item) => item !== id))
  }

  const handleSave = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('请输入 Agent 名称')
      return
    }
    setSaving(true)
    try {
      const updated = await updateCourseAgent(config.agentId, {
        name: trimmed,
        temperature,
        boundKnowledgeBaseIds: kbIds,
        boundModelIds: modelIds,
        conversation: {
          ...config.conversation,
          welcomeMessage: welcomeMessage.trim(),
          systemPrompt: systemPrompt.trim(),
        },
      })
      onSaved(updated)
      setPreviewRefreshKey((k) => k + 1)
      toast.success('配置已保存')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className='grid min-h-[min(760px,calc(100svh-8rem))] gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]'>
      <div className='bg-card flex min-h-0 flex-col rounded-xl border'>
        <div className='border-b px-4 py-3'>
          <h2 className='font-semibold'>基础配置</h2>
          <p className='text-muted-foreground text-sm'>
            名称、欢迎词、系统提示词、温度、知识库与模型
          </p>
        </div>
        <ScrollArea className='min-h-0 flex-1'>
          <div className='space-y-5 p-4'>
            <div className='space-y-2'>
              <Label htmlFor='basic-agent-name'>Agent 名称</Label>
              <Input
                id='basic-agent-name'
                value={name}
                disabled={!canConfig}
                onChange={(e) => setName(e.target.value)}
                placeholder='例如：暑期咨询 Agent'
              />
            </div>

            <div className='space-y-2'>
              <Label htmlFor='basic-welcome'>欢迎词</Label>
              <Textarea
                id='basic-welcome'
                rows={3}
                disabled={!canConfig}
                value={welcomeMessage}
                onChange={(e) => setWelcomeMessage(e.target.value)}
                placeholder='用户进入对话时展示的开场白'
              />
            </div>

            <div className='space-y-2'>
              <Label htmlFor='basic-system-prompt'>系统提示词</Label>
              <Textarea
                id='basic-system-prompt'
                rows={8}
                disabled={!canConfig}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder='定义助手角色、回答边界与语气；留空则使用平台默认提示词'
                className='font-mono text-xs'
              />
              <p className='text-muted-foreground text-xs'>
                将作为 LLM 的 system 消息；知识库检索片段仍会一并注入用户侧上下文
              </p>
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between'>
                <Label htmlFor='basic-temperature'>Temperature</Label>
                <span className='text-muted-foreground text-xs'>
                  {temperature.toFixed(1)}
                </span>
              </div>
              <Input
                id='basic-temperature'
                type='number'
                min={0}
                max={1}
                step={0.1}
                disabled={!canConfig}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
              />
              <p className='text-muted-foreground text-xs'>
                建议 0.2—0.4，值越高回复越发散
              </p>
            </div>

            <div className='space-y-2'>
              <Label>使用的知识库</Label>
              {loadingCatalog ? (
                <p className='text-muted-foreground text-sm'>加载中…</p>
              ) : catalogKbs.length === 0 ? (
                <p className='text-muted-foreground text-sm'>
                  暂无知识库，请先在「知识库」模块创建
                </p>
              ) : (
                <div className='space-y-2 rounded-lg border p-3'>
                  {catalogKbs.map((kb) => {
                    const checked = kbIds.includes(kb.id)
                    return (
                      <label
                        key={kb.id}
                        className='hover:bg-muted/50 flex cursor-pointer items-start gap-2 rounded-md p-1.5'
                      >
                        <Checkbox
                          checked={checked}
                          disabled={!canConfig}
                          onCheckedChange={(value) =>
                            toggleId(kbIds, kb.id, value === true, setKbIds)
                          }
                        />
                        <span className='min-w-0'>
                          <span className='block text-sm font-medium'>
                            {kb.name}
                          </span>
                          {kb.description ? (
                            <span className='text-muted-foreground line-clamp-1 text-xs'>
                              {kb.description}
                            </span>
                          ) : null}
                        </span>
                      </label>
                    )
                  })}
                </div>
              )}
            </div>

            <div className='space-y-2'>
              <Label>使用的模型</Label>
              {loadingCatalog ? (
                <p className='text-muted-foreground text-sm'>加载中…</p>
              ) : catalogModels.length === 0 ? (
                <p className='text-muted-foreground text-sm'>
                  暂无模型配置，请先在「模型配置」模块创建
                </p>
              ) : (
                <div className='space-y-2 rounded-lg border p-3'>
                  {catalogModels.map((model) => {
                    const checked = modelIds.includes(model.id)
                    return (
                      <label
                        key={model.id}
                        className='hover:bg-muted/50 flex cursor-pointer items-start gap-2 rounded-md p-1.5'
                      >
                        <Checkbox
                          checked={checked}
                          disabled={!canConfig}
                          onCheckedChange={(value) =>
                            toggleId(
                              modelIds,
                              model.id,
                              value === true,
                              setModelIds
                            )
                          }
                        />
                        <span className='min-w-0'>
                          <span className='block text-sm font-medium'>
                            {model.name}
                          </span>
                          <span className='text-muted-foreground line-clamp-1 text-xs'>
                            {model.provider} · {model.modelName}
                          </span>
                        </span>
                      </label>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
        {canConfig ? (
          <div className='border-t p-4'>
            <Button
              type='button'
              className='w-full'
              disabled={saving}
              onClick={() => void handleSave()}
            >
              {saving ? '保存中…' : '保存配置'}
            </Button>
          </div>
        ) : null}
      </div>

      <div className='flex min-h-0 flex-col'>
        <AgentPreviewPanel
          agentId={config.agentId}
          agentName={name || config.name}
          menuButtons={config.conversation.menuButtons}
          compact
          hideReset
          refreshKey={previewRefreshKey}
        />
      </div>
    </div>
  )
}
