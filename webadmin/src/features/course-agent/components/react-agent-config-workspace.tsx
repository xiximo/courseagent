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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useInvalidateCourseAgents } from '../hooks/use-course-agents-query'
import {
  DEFAULT_REACT_MENU_BUTTONS,
  DEFAULT_REACT_PROHIBITION,
  DEFAULT_REACT_SOUL,
  DEFAULT_REACT_WELCOME,
} from '../lib/react-agent-defaults'
import {
  HARNESS_PROFILE_TOOLS,
  isProfileTool,
  withHarnessProfileTools,
} from '../lib/harness-profile-tools'
import {
  DEFAULT_AGENT_SCHEDULE,
  normalizeAgentSchedule,
  splitScheduleInterval,
  toIntervalHours,
} from '../lib/agent-schedule'
import type {
  CourseAgentConfig,
  CourseAgentKnowledgeBase,
  CourseAgentModelProfile,
  CourseAgentReactTool,
  CourseAgentSchedule,
} from '../data/types'

type ReactAgentConfigWorkspaceProps = {
  config: CourseAgentConfig
  canConfig: boolean
  onSaved: (config: CourseAgentConfig) => void
}

function emptyTool(index: number): CourseAgentReactTool {
  return {
    id: `tool_${Date.now().toString(36)}_${index}`,
    name: `search_kb_${index + 1}`,
    description: '',
    knowledgeBaseIds: [],
    enabled: true,
  }
}

function isCoreKb(kb: CourseAgentKnowledgeBase) {
  const blob = `${kb.materialLabel} ${kb.name}`.toLowerCase()
  return ['material_a', 'material_b', '膳食指南', '饮食计划', '营养'].some((t) =>
    blob.includes(t)
  )
}

function isPlatformKb(kb: CourseAgentKnowledgeBase) {
  const blob = `${kb.materialLabel} ${kb.name}`.toLowerCase()
  return ['material_c', '白皮书', '平台服务', '会员'].some((t) => blob.includes(t))
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
    withHarnessProfileTools(react?.tools ?? [])
  )
  const [schedule, setSchedule] = useState<CourseAgentSchedule>(
    normalizeAgentSchedule(config.schedule)
  )
  const [intervalUnit, setIntervalUnit] = useState<'hours' | 'minutes'>(
    splitScheduleInterval(config.schedule?.intervalHours ?? 2).unit
  )
  const [intervalValue, setIntervalValue] = useState(
    splitScheduleInterval(config.schedule?.intervalHours ?? 2).value
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
    setTools(withHarnessProfileTools(config.reactConfig?.tools ?? []))
    const nextSchedule = normalizeAgentSchedule(config.schedule)
    setSchedule(nextSchedule)
    const split = splitScheduleInterval(nextSchedule.intervalHours)
    setIntervalUnit(split.unit)
    setIntervalValue(split.value)
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

  const applyContestPreset = () => {
    const core = catalogKbs.filter(isCoreKb)
    const platform = catalogKbs.filter(isPlatformKb)
    const next: CourseAgentReactTool[] = [...HARNESS_PROFILE_TOOLS]
    if (core.length) {
      next.push({
        id: 'tool_core_nutrition',
        name: 'search_core_nutrition',
        description:
          '检索核心营养知识库（膳食指南、个性化饮食计划）。用于减脂/增肌/调理推荐、食材营养成分、搭配原则、禁忌与替换。禁止用于会员价格、企业合作或平台套餐介绍。',
        knowledgeBaseIds: core.map((kb) => kb.id),
        enabled: true,
      })
    }
    if (platform.length) {
      next.push({
        id: 'tool_platform',
        name: 'search_platform_guide',
        description:
          '检索健康优选平台白皮书。仅用于平台介绍、会员订阅、企业健康管理、合作方案。禁止用于膳食方案推荐或营养成分问答。',
        knowledgeBaseIds: platform.map((kb) => kb.id),
        enabled: true,
      })
    }
    if (!next.length) {
      toast.error('未识别到核心营养库或平台白皮书，请先创建并命名知识库，或手动添加工具。')
      return
    }
    setSoul(DEFAULT_REACT_SOUL)
    setProhibitionRules(DEFAULT_REACT_PROHIBITION)
    setWelcomeMessage(DEFAULT_REACT_WELCOME)
    setMenuButtons(DEFAULT_REACT_MENU_BUTTONS.join('，'))
    setTools(next)
    toast.success('已填入赛题膳食顾问预设（A+B 核心库 / C 平台库）')
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
        const ids = item.knowledgeBaseIds
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
          tools: withHarnessProfileTools(tools),
        },
        schedule: {
          ...schedule,
          intervalHours: toIntervalHours(intervalValue, intervalUnit),
          taskPrompt:
            schedule.taskPrompt.trim() || DEFAULT_AGENT_SCHEDULE.taskPrompt,
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
            Soul、禁止规则、用户画像工具，以及可按间隔自动跑的定时任务
          </p>
        </div>
        <Button
          type='button'
          variant='outline'
          size='sm'
          disabled={!canConfig || loadingCatalog}
          onClick={applyContestPreset}
        >
          填入赛题预设
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
              placeholder='例如：健康优选膳食顾问'
            />
          </div>

          <div className='space-y-4 rounded-lg border p-4'>
            <div className='flex items-start justify-between gap-3'>
              <div>
                <Label htmlFor='react-schedule-enabled'>定时任务</Label>
                <p className='text-muted-foreground mt-1 text-xs'>
                  到期后由 update_user_profile 读取各用户在库中的发言，用大模型归纳后写回画像，不创建聊天记录。需先发布 Agent。
                </p>
              </div>
              <Switch
                id='react-schedule-enabled'
                checked={schedule.enabled}
                disabled={!canConfig}
                onCheckedChange={(checked) =>
                  setSchedule((prev) => ({ ...prev, enabled: checked }))
                }
              />
            </div>

            <div className='grid gap-3 md:grid-cols-2'>
              <div className='space-y-1.5'>
                <Label>运行方式</Label>
                <Select
                  value={schedule.runMode}
                  disabled={!canConfig}
                  onValueChange={(value) => {
                    const runMode = value as CourseAgentSchedule['runMode']
                    setSchedule((prev) => ({
                      ...prev,
                      runMode,
                      visibleInChat: runMode !== 'scheduled',
                    }))
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='chat'>对话 + 可选定时</SelectItem>
                    <SelectItem value='scheduled'>仅定时（不进对话入口）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className='space-y-1.5'>
                <Label>执行对象</Label>
                <Select
                  value={schedule.target}
                  disabled={!canConfig}
                  onValueChange={(value) =>
                    setSchedule((prev) => ({
                      ...prev,
                      target: value as CourseAgentSchedule['target'],
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='all_users'>全部启用账号</SelectItem>
                    <SelectItem value='members'>仅普通用户（不含管理员）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className='grid gap-3 md:grid-cols-3'>
              <div className='space-y-1.5'>
                <Label htmlFor='react-interval'>间隔</Label>
                <Input
                  id='react-interval'
                  type='number'
                  min={intervalUnit === 'minutes' ? 3 : 0.05}
                  step={intervalUnit === 'minutes' ? 1 : 0.25}
                  disabled={!canConfig}
                  value={intervalValue}
                  onChange={(e) => setIntervalValue(Number(e.target.value))}
                />
              </div>
              <div className='space-y-1.5'>
                <Label>单位</Label>
                <Select
                  value={intervalUnit}
                  disabled={!canConfig}
                  onValueChange={(value) => {
                    const unit = value as 'hours' | 'minutes'
                    const hours = toIntervalHours(intervalValue, intervalUnit)
                    setIntervalUnit(unit)
                    if (unit === 'minutes') {
                      setIntervalValue(Math.max(3, Math.round(hours * 60)))
                    } else {
                      setIntervalValue(
                        Math.max(0.05, Math.round(hours * 100) / 100)
                      )
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value='hours'>小时</SelectItem>
                    <SelectItem value='minutes'>分钟</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className='space-y-1.5'>
                <Label htmlFor='react-lookback'>回看对话（小时）</Label>
                <Input
                  id='react-lookback'
                  type='number'
                  min={1}
                  max={720}
                  disabled={!canConfig}
                  value={schedule.lookbackHours}
                  onChange={(e) =>
                    setSchedule((prev) => ({
                      ...prev,
                      lookbackHours: Number(e.target.value) || 24,
                    }))
                  }
                />
              </div>
            </div>

            <label className='flex items-center gap-2 text-sm'>
              <Checkbox
                checked={schedule.onlyIfNewMessages}
                disabled={!canConfig}
                onCheckedChange={(v) =>
                  setSchedule((prev) => ({
                    ...prev,
                    onlyIfNewMessages: Boolean(v),
                  }))
                }
              />
              仅当回看窗口内有用户新消息时才跑
            </label>

            <label className='flex items-center gap-2 text-sm'>
              <Checkbox
                checked={schedule.visibleInChat}
                disabled={!canConfig}
                onCheckedChange={(v) =>
                  setSchedule((prev) => ({
                    ...prev,
                    visibleInChat: Boolean(v),
                  }))
                }
              />
              出现在侧栏「对话」入口
            </label>

            <div className='space-y-1.5'>
              <Label htmlFor='react-task-prompt'>定时任务说明</Label>
              <Textarea
                id='react-task-prompt'
                rows={4}
                disabled={!canConfig}
                value={schedule.taskPrompt}
                onChange={(e) =>
                  setSchedule((prev) => ({ ...prev, taskPrompt: e.target.value }))
                }
                className='font-mono text-xs'
              />
            </div>

            {schedule.lastRunAt ? (
              <p className='text-muted-foreground text-xs'>
                上次执行：{new Date(schedule.lastRunAt).toLocaleString('zh-CN')}
                {schedule.lastRunNote ? ` · ${schedule.lastRunNote}` : ''}
              </p>
            ) : (
              <p className='text-muted-foreground text-xs'>
                启用并发布后，服务会按间隔自动执行；最短间隔 3 分钟。
              </p>
            )}
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
              placeholder='减脂怎么吃，增肌蛋白质怎么补'
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
              会写入系统提示词，约束模型不得混淆核心营养库与平台白皮书，并强制医疗免责声明。
            </p>
          </div>

          <div className='space-y-3'>
            <Label>画像工具（内置）</Label>
            <p className='text-muted-foreground text-xs'>
              读取当前用户画像；对话中出现新事实时调用 update_user_profile。该工具会读数据库里的用户发言并用模型归纳后写回。登录用户会持久保存。
            </p>
            <div className='space-y-3'>
              {tools.filter(isProfileTool).map((tool) => (
                <div key={tool.id} className='space-y-2 rounded-lg border p-3'>
                  <label className='flex items-center gap-2 text-sm'>
                    <Checkbox
                      checked={tool.enabled}
                      disabled={!canConfig}
                      onCheckedChange={(v) =>
                        updateTool(tool.id, { enabled: Boolean(v) })
                      }
                    />
                    启用 {tool.name}
                  </label>
                  <p className='text-muted-foreground text-xs leading-relaxed'>
                    {tool.description}
                  </p>
                </div>
              ))}
            </div>
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
            {tools.filter((tool) => !isProfileTool(tool)).length === 0 ? (
              <p className='text-muted-foreground text-sm'>
                尚未配置知识库工具。可点「填入赛题预设」，或手动添加并把知识库绑定到工具。
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
                          平台还没有知识库，请先在知识库页创建并上传素材。
                        </p>
                      ) : (
                        <div className='grid gap-2 sm:grid-cols-2'>
                          {catalogKbs.map((kb) => (
                            <label
                              key={kb.id}
                              className='flex items-start gap-2 text-sm'
                            >
                              <Checkbox
                                checked={tool.knowledgeBaseIds.includes(kb.id)}
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
                      {tool.knowledgeBaseIds
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
