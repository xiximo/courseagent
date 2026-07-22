import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import type { CourseAgentKnowledgeBase } from '../../data/types'
import {
  NODE_TYPE_META,
  type AgentRole,
  type BoundaryConfig,
  type EntryConfig,
  type IdentityConfig,
  type RagEnrollConfig,
  type RagPlatformConfig,
  type RagQaConfig,
  type RagRecommendConfig,
  type ScopeConfig,
  type SessionControlConfig,
  type SlotFillConfig,
  type WorkflowNodeConfig,
  type WorkflowNodeType,
  type WorkflowSpecNode,
} from '../../lib/workflow-graph'

type WorkflowNodeInspectorProps = {
  node: WorkflowSpecNode
  readOnly?: boolean
  knowledgeBases: CourseAgentKnowledgeBase[]
  isEntry?: boolean
  onChange: (next: Partial<Pick<WorkflowSpecNode, 'name' | 'config'>>) => void
  onSetAsEntry?: () => void
}

function linesToList(text: string): string[] {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

function listToLines(list: string[] | undefined): string {
  return (list || []).join('\n')
}

export function WorkflowNodeInspector({
  node,
  readOnly,
  knowledgeBases,
  isEntry,
  onChange,
  onSetAsEntry,
}: WorkflowNodeInspectorProps) {
  const meta = NODE_TYPE_META[node.type]
  const patchConfig = (config: WorkflowNodeConfig) => onChange({ config })

  return (
    <div className='space-y-4'>
      <div>
        <p className='text-sm font-semibold'>{node.name}</p>
        <p className='text-muted-foreground mt-1 font-mono text-xs'>
          {node.type} · {meta?.contract}
        </p>
        {isEntry ? (
          <p className='mt-1 text-xs text-emerald-700'>当前入口节点</p>
        ) : onSetAsEntry ? (
          <Button
            type='button'
            variant='outline'
            size='sm'
            className='mt-2'
            disabled={readOnly}
            onClick={onSetAsEntry}
          >
            设为入口
          </Button>
        ) : null}
      </div>

      <div className='space-y-2'>
        <Label htmlFor='wf-node-name'>节点名称</Label>
        <Input
          id='wf-node-name'
          value={node.name}
          disabled={readOnly}
          onChange={(e) => onChange({ name: e.target.value })}
        />
      </div>

      {node.type === 'entry' ? (
        <EntryFields
          config={node.config as EntryConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'identity' ? (
        <IdentityFields
          config={node.config as IdentityConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'slot_fill' ? (
        <SlotFillFields
          config={node.config as SlotFillConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'scope' ? (
        <ScopeFields
          config={node.config as ScopeConfig}
          readOnly={readOnly}
          knowledgeBases={knowledgeBases}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'rag_recommend' ? (
        <RagRecommendFields
          config={node.config as RagRecommendConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'rag_qa' || node.type === 'rag_enroll' ? (
        <RagSimpleFields
          config={node.config as RagQaConfig | RagEnrollConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'rag_platform' ? (
        <RagPlatformFields
          config={node.config as RagPlatformConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'session_control' ? (
        <SessionControlFields
          config={node.config as SessionControlConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
      {node.type === 'boundary' ? (
        <BoundaryFields
          config={node.config as BoundaryConfig}
          readOnly={readOnly}
          onChange={patchConfig}
        />
      ) : null}
    </div>
  )
}

function EntryFields({
  config,
  readOnly,
  onChange,
}: {
  config: EntryConfig
  readOnly?: boolean
  onChange: (c: EntryConfig) => void
}) {
  return (
    <>
      <div className='space-y-2'>
        <Label>欢迎语</Label>
        <Textarea
          rows={4}
          value={config.welcomeText}
          disabled={readOnly}
          onChange={(e) => onChange({ ...config, welcomeText: e.target.value })}
        />
      </div>
      <div className='space-y-2'>
        <Label>快捷按钮（每行一个）</Label>
        <Textarea
          rows={4}
          value={listToLines(config.quickActions)}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, quickActions: linesToList(e.target.value) })
          }
        />
      </div>
    </>
  )
}

function IdentityFields({
  config,
  readOnly,
  onChange,
}: {
  config: IdentityConfig
  readOnly?: boolean
  onChange: (c: IdentityConfig) => void
}) {
  return (
    <div className='space-y-2'>
      <Label>未确认时追问话术</Label>
      <Textarea
        rows={3}
        value={config.promptWhenUnknown}
        disabled={readOnly}
        onChange={(e) =>
          onChange({ ...config, promptWhenUnknown: e.target.value })
        }
      />
    </div>
  )
}

function SlotFillFields({
  config,
  readOnly,
  onChange,
}: {
  config: SlotFillConfig
  readOnly?: boolean
  onChange: (c: SlotFillConfig) => void
}) {
  return (
    <div className='space-y-3'>
      <div className='flex items-center justify-between gap-3 rounded-lg border px-3 py-2'>
        <div>
          <p className='text-sm font-medium'>一次只追问一个缺槽</p>
        </div>
        <Switch
          checked={config.askOneMissingAtATime}
          disabled={readOnly}
          onCheckedChange={(v) =>
            onChange({ ...config, askOneMissingAtATime: v })
          }
        />
      </div>
      {config.slots.map((slot, index) => (
        <div key={slot.key} className='space-y-2 rounded-lg border p-3'>
          <p className='text-xs font-medium text-slate-600'>
            {slot.label}（{slot.key}）
          </p>
          <Textarea
            rows={2}
            value={slot.askPrompt}
            disabled={readOnly}
            onChange={(e) => {
              const slots = [...config.slots]
              slots[index] = { ...slot, askPrompt: e.target.value }
              onChange({ ...config, slots })
            }}
          />
        </div>
      ))}
    </div>
  )
}

function ScopeFields({
  config,
  readOnly,
  knowledgeBases,
  onChange,
}: {
  config: ScopeConfig
  readOnly?: boolean
  knowledgeBases: CourseAgentKnowledgeBase[]
  onChange: (c: ScopeConfig) => void
}) {
  const roles: { key: AgentRole; label: string; hint: string }[] = [
    { key: 'student', label: '学生 / 家长', hint: '素材 A' },
    { key: 'teacher', label: '教师', hint: '素材 B' },
    { key: 'org', label: '机构 / 企业', hint: '素材 C' },
  ]
  const binding = config.binding || {}

  return (
    <div className='space-y-3'>
      <p className='text-muted-foreground text-xs'>
        每个身份只能绑定一个知识库；运行时禁止跨库检索。
      </p>
      {roles.map((r) => (
        <div key={r.key} className='space-y-1.5'>
          <Label>
            {r.label}
            <span className='text-muted-foreground ml-1 font-normal'>
              （{r.hint}）
            </span>
          </Label>
          <Select
            value={binding[r.key] || '__none__'}
            disabled={readOnly}
            onValueChange={(v) =>
              onChange({
                ...config,
                binding: {
                  ...binding,
                  [r.key]: v === '__none__' ? null : v,
                },
              })
            }
          >
            <SelectTrigger className='w-full'>
              <SelectValue placeholder='选择知识库' />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='__none__'>未绑定</SelectItem>
              {knowledgeBases.map((kb) => (
                <SelectItem key={kb.id} value={kb.id}>
                  {kb.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ))}
      <div className='space-y-2'>
        <Label>未配置知识库时提示</Label>
        <Textarea
          rows={2}
          value={config.missingKbText || ''}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, missingKbText: e.target.value })
          }
        />
      </div>
    </div>
  )
}

function RagRecommendFields({
  config,
  readOnly,
  onChange,
}: {
  config: RagRecommendConfig
  readOnly?: boolean
  onChange: (c: RagRecommendConfig) => void
}) {
  return (
    <>
      <div className='space-y-2'>
        <Label>最多推荐班型数</Label>
        <Input
          type='number'
          min={1}
          max={2}
          value={config.maxCourses ?? 2}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, maxCourses: Number(e.target.value) || 2 })
          }
        />
      </div>
      <div className='flex items-center justify-between gap-3 rounded-lg border px-3 py-2'>
        <p className='text-sm'>推荐后锁定第一个班型</p>
        <Switch
          checked={config.lockFirstCourse ?? true}
          disabled={readOnly}
          onCheckedChange={(v) => onChange({ ...config, lockFirstCourse: v })}
        />
      </div>
      <RagSimpleFields config={config} readOnly={readOnly} onChange={onChange} />
    </>
  )
}

function RagSimpleFields({
  config,
  readOnly,
  onChange,
}: {
  config: { systemExtra?: string; quickActions?: string[] }
  readOnly?: boolean
  onChange: (c: { systemExtra?: string; quickActions?: string[] }) => void
}) {
  return (
    <>
      <div className='space-y-2'>
        <Label>生成补充说明（systemExtra）</Label>
        <Textarea
          rows={4}
          value={config.systemExtra || ''}
          disabled={readOnly}
          onChange={(e) => onChange({ ...config, systemExtra: e.target.value })}
        />
      </div>
      <div className='space-y-2'>
        <Label>快捷按钮（每行一个）</Label>
        <Textarea
          rows={3}
          value={listToLines(config.quickActions)}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, quickActions: linesToList(e.target.value) })
          }
        />
      </div>
    </>
  )
}

function RagPlatformFields({
  config,
  readOnly,
  onChange,
}: {
  config: RagPlatformConfig
  readOnly?: boolean
  onChange: (c: RagPlatformConfig) => void
}) {
  return (
    <>
      <div className='flex items-center justify-between gap-3 rounded-lg border px-3 py-2'>
        <p className='text-sm'>禁止输出学生/教师班型推荐</p>
        <Switch
          checked={config.forbidCourseRecommend ?? true}
          disabled={readOnly}
          onCheckedChange={(v) =>
            onChange({ ...config, forbidCourseRecommend: v })
          }
        />
      </div>
      <RagSimpleFields config={config} readOnly={readOnly} onChange={onChange} />
    </>
  )
}

function SessionControlFields({
  config,
  readOnly,
  onChange,
}: {
  config: SessionControlConfig
  readOnly?: boolean
  onChange: (c: SessionControlConfig) => void
}) {
  return (
    <>
      <div className='space-y-2'>
        <Label>重置话术</Label>
        <Textarea
          rows={2}
          value={config.restartText || ''}
          disabled={readOnly}
          onChange={(e) => onChange({ ...config, restartText: e.target.value })}
        />
      </div>
      <div className='space-y-2'>
        <Label>查看全部班型引言</Label>
        <Textarea
          rows={2}
          value={config.listCoursesIntro || ''}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, listCoursesIntro: e.target.value })
          }
        />
      </div>
      <div className='space-y-2'>
        <Label>快捷按钮（每行一个）</Label>
        <Textarea
          rows={3}
          value={listToLines(config.quickActions)}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, quickActions: linesToList(e.target.value) })
          }
        />
      </div>
    </>
  )
}

function BoundaryFields({
  config,
  readOnly,
  onChange,
}: {
  config: BoundaryConfig
  readOnly?: boolean
  onChange: (c: BoundaryConfig) => void
}) {
  const t = config.templates || {}
  return (
    <>
      <div className='space-y-2'>
        <Label>超出服务范围</Label>
        <Textarea
          rows={2}
          value={t.outOfScope || ''}
          disabled={readOnly}
          onChange={(e) =>
            onChange({
              ...config,
              templates: { ...t, outOfScope: e.target.value },
            })
          }
        />
      </div>
      <div className='space-y-2'>
        <Label>模型异常</Label>
        <Textarea
          rows={2}
          value={t.modelError || ''}
          disabled={readOnly}
          onChange={(e) =>
            onChange({
              ...config,
              templates: { ...t, modelError: e.target.value },
            })
          }
        />
      </div>
      <div className='space-y-2'>
        <Label>跨资料混淆</Label>
        <Textarea
          rows={2}
          value={t.crossMaterial || ''}
          disabled={readOnly}
          onChange={(e) =>
            onChange({
              ...config,
              templates: { ...t, crossMaterial: e.target.value },
            })
          }
        />
      </div>
      <div className='space-y-2'>
        <Label>快捷按钮（每行一个）</Label>
        <Textarea
          rows={3}
          value={listToLines(config.quickActions)}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...config, quickActions: linesToList(e.target.value) })
          }
        />
      </div>
    </>
  )
}

export function nodeTypeLabel(type: WorkflowNodeType): string {
  return NODE_TYPE_META[type]?.label ?? type
}
