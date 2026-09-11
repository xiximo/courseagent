import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
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
import { useInvalidateCourseAgents } from '../hooks/use-course-agents-query'
import {
  DEFAULT_REACT_MENU_BUTTONS,
  DEFAULT_REACT_PROHIBITION,
  DEFAULT_REACT_SOUL,
  DEFAULT_REACT_WELCOME,
  isLegacyDefaultToolName,
} from '../lib/react-agent-defaults'
import { isProfileTool, withoutProfileTools } from '../lib/harness-profile-tools'
import { DEFAULT_AGENT_SCHEDULE } from '../lib/agent-schedule'
import type {
  CourseAgentConfig,
  CourseAgentKnowledgeBase,
  CourseAgentModelProfile,
  CourseAgentReactTool,
} from '../data/types'

type ReactAgentConfigWorkspaceProps = {
  config: CourseAgentConfig
  canConfig: boolean
  onSaved: (config: CourseAgentConfig) => void
}

function emptyTool(index: number): CourseAgentReactTool {
  return {
    id: `tool_${Date.now().toString(36)}_${index}`,
    name: `search_docs_${index + 1}`,
    description: '',
    knowledgeBaseIds: [],
    enabled: true,
  }
}

function visibleConfigTools(tools: CourseAgentReactTool[]) {
  return withoutProfileTools(tools)
    .filter((tool) => !isLegacyDefaultToolName(tool.name))
    .map((tool) => ({
      ...tool,
      knowledgeBaseIds: Array.isArray(tool.knowledgeBaseIds)
        ? tool.knowledgeBaseIds
        : [],
    }))
}

export function ReactAgentConfigWorkspace({
  config,
  canConfig,
  onSaved,
}: ReactAgentConfigWorkspaceProps) {
  const react = config.reactConfig
  const [name, setName] = useState(config.name)
  const [temperature, setTemperature] = useState(config.temperature ?? 0.3)
  const [welcomeMessage, setWelcomeMessage] = useState(
    config.conversation.welcomeMessage || DEFAULT_REACT_WELCOME
  )
  const [menuButtons, setMenuButtons] = useState(
    (config.conversation.menuButtons ?? []).join('，') ||
      DEFAULT_REACT_MENU_BUTTONS.join('，')
  )
  const [soul, setSoul] = useState(react?.soul || DEFAULT_REACT_SOUL)
  const [prohibitionRules, setProhibitionRules] = useState(
    react?.prohibitionRules || DEFAULT_REACT_PROHIBITION
  )
  const [tools, setTools] = useState<CourseAgentReactTool[]>(
    visibleConfigTools(react?.tools ?? [])
  )
  const [modelIds, setModelIds] = useState<string[]>(config.boundModelIds ?? [])
  const [catalogKbs, setCatalogKbs] = useState<CourseAgentKnowledgeBase[]>([])
  const [catalogModels, setCatalogModels] = useState<CourseAgentModelProfile[]>(
    []
  )
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [saving, setSaving] = useState(false)
  const invalidateAgents = useInvalidateCourseAgents()

  useEffect(() => {
    setName(config.name)
    setTemperature(config.temperature ?? 0.3)
    setWelcomeMessage(config.conversation.welcomeMessage || DEFAULT_REACT_WELCOME)
    setMenuButtons(
      (config.conversation.menuButtons ?? []).join('，') ||
        DEFAULT_REACT_MENU_BUTTONS.join('，')
    )
    setSoul(config.reactConfig?.soul || DEFAULT_REACT_SOUL)
    setProhibitionRules(
      config.reactConfig?.prohibitionRules || DEFAULT_REACT_PROHIBITION
    )
    setTools(visibleConfigTools(config.reactConfig?.tools ?? []))
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

  const kbById = useMemo(
    () => new Map(catalogKbs.map((kb) => [kb.id, kb])),
    [catalogKbs]
  )

  const applyKbTools = () => {
    if (!catalogKbs.length) {
      toast.error('当前没有可绑定的知识库，请先创建知识库。')
      return
    }
    setTools(
      catalogKbs.map((kb, index) => ({
        id: `tool_docs_${index + 1}`,
        name: `search_docs_${index + 1}`,
        description: `检索知识库「${kb.name}」。仅在问题与该库主题相关时调用。`,
        knowledgeBaseIds: [kb.id],
        enabled: true,
      }))
    )
    toast.success('已按知识库生成检索工具')
  }

  const updateTool = (id: string, patch: Partial<CourseAgentReactTool>) => {
    setTools((list) =>
      list.map((item) => (item.id === id ? { ...item, ...patch } : item))
    )
  }

  const toggleToolKb = (toolId: string, kbId: string, checked: boolean) => {
    setTools((list) =>
      list.map((item) => {
        if (item.id !== toolId) return item
        const ids = item.knowledgeBaseIds ?? []
        return {
          ...item,
          knowledgeBaseIds: checked
            ? [...ids, kbId]
            : ids.filter((id) => id !== kbId),
        }
      })
    )
  }

  const handleSave = async () => {
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('请输入 Agent 名称')
      return
    }
    const parsedButtons = menuButtons
      .split(/[,，]/)
      .map((item) => item.trim())
      .filter(Boolean)
    setSaving(true)
    try {
      const updated = await updateCourseAgent(config.agentId, {
        name: trimmed,
        temperature,
        boundModelIds: modelIds,
        conversation: {
          ...config.conversation,
          welcomeMessage: welcomeMessage.trim() || DEFAULT_REACT_WELCOME,
          menuButtons: parsedButtons,
          emptyInputMessage: '请输入您的问题',
          tooLongMessage: '输入内容过长，请精简后重试',
        },
        reactConfig: {
          soul: soul.trim() || DEFAULT_REACT_SOUL,
          prohibitionRules: prohibitionRules.trim() || DEFAULT_REACT_PROHIBITION,
          maxToolRounds: config.reactConfig?.maxToolRounds ?? 5,
          tools: visibleConfigTools(tools),
        },
        schedule: {
          ...DEFAULT_AGENT_SCHEDULE,
          enabled: false,
          runMode: 'chat',
          visibleInChat: true,
        },
      })
      onSaved(updated)
      invalidateAgents()
      toast.success('配置已保存')
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className='bg-card flex min-h-[min(760px,calc(100svh-8rem))] flex-col rounded-xl border'>
      <div className='flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3'>
        <div>
          <h2 className='font-semibold'>Harness 配置</h2>
          <p className='text-muted-foreground text-sm'>
            Soul、禁止规则与知识库工具编排
          </p>
        </div>
        <Button
          type='button'
          variant='outline'
          size='sm'
          disabled={!canConfig || loadingCatalog}
          onClick={applyKbTools}
        >
          按知识库生成工具
        </Button>
      </div>
      <ScrollArea className='min-h-0 flex-1'>
        <div className='space-y-5 p-4'>
          <div className='space-y-2'>
            <Label htmlFor='react-agent-name'>Agent 名称</Label>
            <Input
              id='react-agent-name'
              value={name}
              disabled={!canConfig}
              onChange={(e) => setName(e.target.value)}
              placeholder='例如：课程顾问'
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='react-welcome'>欢迎语</Label>
            <Textarea
              id='react-welcome'
              rows={3}
              disabled={!canConfig}
              value={welcomeMessage}
              onChange={(e) => setWelcomeMessage(e.target.value)}
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='react-menu'>快捷问题（逗号分隔）</Label>
            <Input
              id='react-menu'
              disabled={!canConfig}
              value={menuButtons}
              onChange={(e) => setMenuButtons(e.target.value)}
              placeholder='北京线下班详情，我在上海周末有空'
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='react-soul'>Soul（角色与目标）</Label>
            <Textarea
              id='react-soul'
              rows={8}
              disabled={!canConfig}
              value={soul}
              onChange={(e) => setSoul(e.target.value)}
              className='font-mono text-xs'
            />
          </div>

          <div className='space-y-2'>
            <Label htmlFor='react-rules'>禁止规则</Label>
            <Textarea
              id='react-rules'
              rows={8}
              disabled={!canConfig}
              value={prohibitionRules}
              onChange={(e) => setProhibitionRules(e.target.value)}
              className='font-mono text-xs'
            />
            <p className='text-muted-foreground text-xs'>
              会写入系统提示词，约束模型不得编造班型或超出知识库作答。
            </p>
          </div>

          <div className='space-y-3'>
            <div className='flex items-center justify-between gap-2'>
              <Label>知识库工具</Label>
              <Button
                type='button'
                size='sm'
                variant='outline'
                disabled={!canConfig}
                onClick={() => setTools((list) => [...list, emptyTool(list.length)])}
              >
                <Plus className='size-3.5' />
                添加工具
              </Button>
            </div>
            <p className='text-muted-foreground text-xs'>
              未绑定具体知识库时，问答会自动检索本机构当前的全部知识库，不会用模型自己的知识代替。
            </p>
            {tools.filter((tool) => !isProfileTool(tool)).length === 0 ? (
              <p className='text-muted-foreground text-sm'>
                尚未单独配置知识库工具。对话时仍会检索本机构知识库；也可点「按知识库生成工具」做更细的绑定。
              </p>
            ) : (
              <div className='space-y-3'>
                {tools
                  .filter((tool) => !isProfileTool(tool))
                  .map((tool, index) => (
                  <div key={tool.id} className='space-y-3 rounded-lg border p-3'>
                    <div className='flex items-center justify-between gap-2'>
                      <label className='flex items-center gap-2 text-sm'>
                        <Checkbox
                          checked={tool.enabled}
                          disabled={!canConfig}
                          onCheckedChange={(v) =>
                            updateTool(tool.id, { enabled: Boolean(v) })
                          }
                        />
                        启用 {index + 1}
                      </label>
                      <Button
                        type='button'
                        size='icon'
                        variant='ghost'
                        className='text-muted-foreground hover:text-destructive size-7'
                        disabled={!canConfig}
                        onClick={() =>
                          setTools((list) => list.filter((item) => item.id !== tool.id))
                        }
                      >
                        <Trash2 className='size-3.5' />
                      </Button>
                    </div>
                    <div className='grid gap-3 md:grid-cols-2'>
                      <div className='space-y-1.5'>
                        <Label className='text-xs'>工具名（英文函数名）</Label>
                        <Input
                          disabled={!canConfig}
                          value={tool.name}
                          onChange={(e) => updateTool(tool.id, { name: e.target.value })}
                          className='font-mono text-xs'
                        />
                      </div>
                    </div>
                    <div className='space-y-1.5'>
                      <Label className='text-xs'>调用说明（何时用、禁止用于什么）</Label>
                      <Textarea
                        rows={3}
                        disabled={!canConfig}
                        value={tool.description}
                        onChange={(e) =>
                          updateTool(tool.id, { description: e.target.value })
                        }
                      />
                    </div>
                    <div className='space-y-1.5'>
                      <Label className='text-xs'>绑定知识库</Label>
                      {loadingCatalog ? (
                        <p className='text-muted-foreground text-xs'>加载知识库…</p>
                      ) : catalogKbs.length === 0 ? (
                        <p className='text-muted-foreground text-xs'>
                          还没有知识库，请先在知识库页创建并上传素材。
                        </p>
                      ) : (
                        <div className='grid gap-2 sm:grid-cols-2'>
                          {catalogKbs.map((kb) => (
                            <label
                              key={kb.id}
                              className='flex items-start gap-2 text-sm'
                            >
                              <Checkbox
                                checked={(tool.knowledgeBaseIds ?? []).includes(kb.id)}
                                disabled={!canConfig}
                                onCheckedChange={(v) =>
                                  toggleToolKb(tool.id, kb.id, Boolean(v))
                                }
                              />
                              <span>
                                {kb.name}
                                <span className='text-muted-foreground ml-1 font-mono text-xs'>
                                  {kb.materialLabel}
                                </span>
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                      {(tool.knowledgeBaseIds ?? [])
                        .filter((id) => !kbById.has(id))
                        .map((id) => (
                          <p key={id} className='text-muted-foreground text-xs'>
                            已绑定未知库 {id}
                          </p>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <Label htmlFor='react-temperature'>Temperature</Label>
              <span className='text-muted-foreground text-xs'>
                {temperature.toFixed(1)}
              </span>
            </div>
            <Input
              id='react-temperature'
              type='number'
              min={0}
              max={1}
              step={0.1}
              disabled={!canConfig}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
            />
          </div>

          <div className='space-y-2'>
            <Label>使用的模型</Label>
            {loadingCatalog ? (
              <p className='text-muted-foreground text-sm'>加载中…</p>
            ) : catalogModels.length === 0 ? (
              <p className='text-muted-foreground text-sm'>暂无平台模型，请先在模型页创建。</p>
            ) : (
              catalogModels.map((model) => (
                <label key={model.id} className='flex items-center gap-2 text-sm'>
                  <Checkbox
                    checked={modelIds.includes(model.id)}
                    disabled={!canConfig}
                    onCheckedChange={(v) => {
                      const checked = Boolean(v)
                      setModelIds((list) =>
                        checked
                          ? [...list, model.id]
                          : list.filter((id) => id !== model.id)
                      )
                    }}
                  />
                  {model.name}
                </label>
              ))
            )}
          </div>
        </div>
      </ScrollArea>
      <div className='flex justify-end border-t px-4 py-3'>
        <Button disabled={!canConfig || saving} onClick={() => void handleSave()}>
          {saving ? '保存中…' : '保存配置'}
        </Button>
      </div>
    </div>
  )
}
