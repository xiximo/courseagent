import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  INTENT_OPTIONS,
  formatEdgeCondition,
  type AgentRole,
  type EdgeCondition,
  type StatePatch,
  type WorkflowIntent,
  type WorkflowSpecEdge,
} from '../../lib/workflow-graph'

type WorkflowEdgeInspectorProps = {
  edge: WorkflowSpecEdge
  readOnly?: boolean
  onChange: (patch: Partial<WorkflowSpecEdge>) => void
}

type SimpleWhenKind =
  | 'always'
  | 'quick_action'
  | 'role_eq'
  | 'role_status'
  | 'constraints_ready'
  | 'intent'
  | 'advanced'

function classifyWhen(when?: EdgeCondition): SimpleWhenKind {
  if (!when) return 'always'
  if (when.type === 'and' || when.type === 'or' || when.type === 'not') {
    return 'advanced'
  }
  if (when.type === 'state_flag') return 'advanced'
  return when.type
}

export function WorkflowEdgeInspector({
  edge,
  readOnly,
  onChange,
}: WorkflowEdgeInspectorProps) {
  const kind = classifyWhen(edge.when)
  const when = edge.when

  const setSimpleWhen = (next: EdgeCondition) => {
    onChange({ when: next, label: edge.label })
  }

  return (
    <div className='space-y-4'>
      <div>
        <p className='text-sm font-semibold'>{edge.label || edge.id}</p>
        <p className='text-muted-foreground mt-1 font-mono text-xs'>
          {edge.source} → {edge.target}
        </p>
        <p className='mt-1 text-xs text-slate-500'>
          {formatEdgeCondition(edge.when)}
        </p>
      </div>

      <div className='space-y-2'>
        <Label>显示标签</Label>
        <Input
          value={edge.label || ''}
          disabled={readOnly}
          onChange={(e) => onChange({ label: e.target.value })}
        />
      </div>

      <div className='space-y-2'>
        <Label>优先级（越小越先匹配）</Label>
        <Input
          type='number'
          min={0}
          value={edge.priority}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ priority: Number(e.target.value) || 0 })
          }
        />
      </div>

      <div className='space-y-2'>
        <Label>条件类型</Label>
        <Select
          value={kind}
          disabled={readOnly}
          onValueChange={(v) => {
            const k = v as SimpleWhenKind
            if (k === 'always') setSimpleWhen({ type: 'always' })
            else if (k === 'quick_action')
              setSimpleWhen({ type: 'quick_action', action: '学生课程' })
            else if (k === 'role_eq')
              setSimpleWhen({ type: 'role_eq', role: 'student' })
            else if (k === 'role_status')
              setSimpleWhen({ type: 'role_status', status: 'confirmed' })
            else if (k === 'constraints_ready')
              setSimpleWhen({ type: 'constraints_ready', min: 2 })
            else if (k === 'intent')
              setSimpleWhen({ type: 'intent', intent: 'ask_detail' })
            // advanced: keep current JSON
          }}
        >
          <SelectTrigger className='w-full'>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value='always'>always</SelectItem>
            <SelectItem value='quick_action'>快捷按钮</SelectItem>
            <SelectItem value='role_eq'>角色等于</SelectItem>
            <SelectItem value='role_status'>身份状态</SelectItem>
            <SelectItem value='constraints_ready'>约束足够</SelectItem>
            <SelectItem value='intent'>意图</SelectItem>
            <SelectItem value='advanced'>复合条件（JSON）</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {kind === 'quick_action' && when?.type === 'quick_action' ? (
        <div className='space-y-2'>
          <Label>按钮文案</Label>
          <Input
            value={when.action}
            disabled={readOnly}
            onChange={(e) =>
              setSimpleWhen({ type: 'quick_action', action: e.target.value })
            }
          />
        </div>
      ) : null}

      {kind === 'role_eq' && when?.type === 'role_eq' ? (
        <div className='space-y-2'>
          <Label>角色</Label>
          <Select
            value={when.role}
            disabled={readOnly}
            onValueChange={(v) =>
              setSimpleWhen({ type: 'role_eq', role: v as AgentRole })
            }
          >
            <SelectTrigger className='w-full'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='student'>student</SelectItem>
              <SelectItem value='teacher'>teacher</SelectItem>
              <SelectItem value='org'>org</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {kind === 'role_status' && when?.type === 'role_status' ? (
        <div className='space-y-2'>
          <Label>状态</Label>
          <Select
            value={when.status}
            disabled={readOnly}
            onValueChange={(v) =>
              setSimpleWhen({
                type: 'role_status',
                status: v as 'unknown' | 'confirmed',
              })
            }
          >
            <SelectTrigger className='w-full'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='unknown'>unknown</SelectItem>
              <SelectItem value='confirmed'>confirmed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {kind === 'constraints_ready' && when?.type === 'constraints_ready' ? (
        <div className='space-y-2'>
          <Label>最少有效约束数</Label>
          <Input
            type='number'
            min={1}
            value={when.min}
            disabled={readOnly}
            onChange={(e) =>
              setSimpleWhen({
                type: 'constraints_ready',
                min: Number(e.target.value) || 1,
              })
            }
          />
        </div>
      ) : null}

      {kind === 'intent' && when?.type === 'intent' ? (
        <div className='space-y-2'>
          <Label>意图</Label>
          <Select
            value={when.intent}
            disabled={readOnly}
            onValueChange={(v) =>
              setSimpleWhen({
                type: 'intent',
                intent: v as WorkflowIntent,
              })
            }
          >
            <SelectTrigger className='w-full'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {INTENT_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {kind === 'advanced' ? (
        <div className='space-y-2'>
          <Label>条件 JSON</Label>
          <Textarea
            rows={8}
            className='font-mono text-xs'
            disabled={readOnly}
            defaultValue={JSON.stringify(edge.when ?? { type: 'always' }, null, 2)}
            onBlur={(e) => {
              try {
                const parsed = JSON.parse(e.target.value) as EdgeCondition
                onChange({ when: parsed })
              } catch {
                // keep previous
              }
            }}
          />
        </div>
      ) : null}

      <div className='space-y-2'>
        <Label>边写入补丁 apply（JSON，可选）</Label>
        <Textarea
          rows={5}
          className='font-mono text-xs'
          disabled={readOnly}
          defaultValue={JSON.stringify(edge.apply ?? {}, null, 2)}
          onBlur={(e) => {
            try {
              const parsed = JSON.parse(e.target.value) as StatePatch
              onChange({ apply: parsed })
            } catch {
              // keep
            }
          }}
        />
        <p className='text-muted-foreground text-[11px]'>
          例：点击入口时写入 {'{ "role": "student", "roleStatus": "confirmed" }'}
        </p>
      </div>
    </div>
  )
}
