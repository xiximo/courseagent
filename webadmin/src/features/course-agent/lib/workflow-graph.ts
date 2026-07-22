/**
 * Course Agent 工作流图（对齐 docs/agent-runtime-spec.md / workflow-graph.schema.json）
 * 存盘格式即为运行时控制面定义；画布仅编辑此结构。
 */

import type { Edge, Node, Viewport } from '@xyflow/react'

export type AgentRole = 'student' | 'teacher' | 'org'
export type RoleStatus = 'unknown' | 'confirmed'

export type WorkflowIntent =
  | 'choose_role'
  | 'provide_constraint'
  | 'ask_recommend'
  | 'ask_detail'
  | 'ask_enroll'
  | 'restart'
  | 'list_courses'
  | 'out_of_scope'
  | 'empty'
  | 'too_long'
  | 'other'

export type WorkflowNodeType =
  | 'entry'
  | 'identity'
  | 'slot_fill'
  | 'scope'
  | 'rag_recommend'
  | 'rag_qa'
  | 'rag_enroll'
  | 'rag_platform'
  | 'session_control'
  | 'boundary'

export type EdgeCondition =
  | { type: 'always' }
  | { type: 'quick_action'; action: string }
  | { type: 'role_eq'; role: AgentRole }
  | { type: 'role_status'; status: RoleStatus }
  | { type: 'constraints_ready'; min: number }
  | { type: 'intent'; intent: WorkflowIntent }
  | { type: 'state_flag'; path: string; equals: unknown }
  | { type: 'and' | 'or'; items: EdgeCondition[] }
  | { type: 'not'; item: EdgeCondition }

export type StatePatch = {
  role?: AgentRole | null
  roleStatus?: RoleStatus
  constraints?: {
    city?: string | null
    date?: string | null
    format?: string | null
    goal?: string | null
  }
  recommendedCourses?: string[]
  lockedCourse?: string | null
  activeKnowledgeBaseId?: string | null
  clearSession?: boolean
  clearRole?: boolean
}

export type SlotDef = {
  key: 'city' | 'date' | 'format' | 'goal'
  label: string
  askPrompt: string
  requiredForCount?: boolean
}

export type EntryConfig = {
  welcomeText: string
  quickActions: string[]
}

export type IdentityConfig = {
  promptWhenUnknown: string
  allowedRoles?: AgentRole[]
}

export type SlotFillConfig = {
  askOneMissingAtATime: boolean
  slots: SlotDef[]
}

export type ScopeConfig = {
  binding: {
    student?: string | null
    teacher?: string | null
    org?: string | null
  }
  missingKbText?: string
}

export type RagRecommendConfig = {
  maxCourses?: number
  lockFirstCourse?: boolean
  systemExtra?: string
  quickActions?: string[]
}

export type RagQaConfig = {
  systemExtra?: string
  quickActions?: string[]
}

export type RagEnrollConfig = {
  systemExtra?: string
  quickActions?: string[]
}

export type RagPlatformConfig = {
  systemExtra?: string
  forbidCourseRecommend?: boolean
  quickActions?: string[]
}

export type SessionControlConfig = {
  restartText?: string
  listCoursesIntro?: string
  quickActions?: string[]
}

export type BoundaryConfig = {
  templates: {
    outOfScope?: string
    modelError?: string
    crossMaterial?: string
  }
  quickActions?: string[]
}

export type WorkflowNodeConfig =
  | EntryConfig
  | IdentityConfig
  | SlotFillConfig
  | ScopeConfig
  | RagRecommendConfig
  | RagQaConfig
  | RagEnrollConfig
  | RagPlatformConfig
  | SessionControlConfig
  | BoundaryConfig

export type WorkflowSpecNode = {
  id: string
  type: WorkflowNodeType
  name: string
  ui?: { x?: number; y?: number }
  config: WorkflowNodeConfig
}

export type WorkflowSpecEdge = {
  id: string
  source: string
  target: string
  priority: number
  when?: EdgeCondition
  apply?: StatePatch
  label?: string
}

export type WorkflowGraph = {
  version: '1'
  entryNodeId: string
  policies: {
    maxInputChars: number
    minConstraintsForRecommend: number
  }
  nodes: WorkflowSpecNode[]
  edges: WorkflowSpecEdge[]
  meta?: Record<string, unknown>
  /** 画布视口，运行时忽略 */
  viewport?: Viewport
}

/** React Flow 节点 data */
export type WorkflowFlowNodeData = {
  name: string
  nodeType: WorkflowNodeType
  config: WorkflowNodeConfig
  summary: string
}

export type WorkflowFlowNode = Node<WorkflowFlowNodeData, 'agentNode'>

export type WorkflowFlowEdgeData = {
  priority: number
  when?: EdgeCondition
  apply?: StatePatch
  label?: string
}

export const NODE_TYPE_META: Record<
  WorkflowNodeType,
  { label: string; tone: string; contract: string }
> = {
  entry: {
    label: '欢迎分流',
    tone: 'border-sky-400/70 bg-sky-50',
    contract: '模板 · 无检索',
  },
  identity: {
    label: '身份澄清',
    tone: 'border-amber-400/70 bg-amber-50',
    contract: 'LLM · 禁止检索',
  },
  slot_fill: {
    label: '约束采集',
    tone: 'border-violet-400/70 bg-violet-50',
    contract: 'LLM 抽槽 · 禁止检索',
  },
  scope: {
    label: '知识范围',
    tone: 'border-indigo-400/70 bg-indigo-50',
    contract: '按角色绑唯一库',
  },
  rag_recommend: {
    label: '班型推荐',
    tone: 'border-emerald-400/70 bg-emerald-50',
    contract: 'RAG + LLM',
  },
  rag_qa: {
    label: '详情追问',
    tone: 'border-cyan-400/70 bg-cyan-50',
    contract: 'RAG + LLM',
  },
  rag_enroll: {
    label: '报名引导',
    tone: 'border-rose-400/70 bg-rose-50',
    contract: 'RAG + LLM',
  },
  rag_platform: {
    label: '平台服务',
    tone: 'border-teal-400/70 bg-teal-50',
    contract: 'RAG + LLM · 禁班型推荐',
  },
  session_control: {
    label: '会话控制',
    tone: 'border-slate-400/70 bg-slate-50',
    contract: '模板 / 目录检索',
  },
  boundary: {
    label: '边界异常',
    tone: 'border-orange-400/70 bg-orange-50',
    contract: '固定模板',
  },
}

export const INTENT_OPTIONS: { value: WorkflowIntent; label: string }[] = [
  { value: 'choose_role', label: '选择身份' },
  { value: 'provide_constraint', label: '提供约束' },
  { value: 'ask_recommend', label: '请求推荐' },
  { value: 'ask_detail', label: '追问详情' },
  { value: 'ask_enroll', label: '报名意向' },
  { value: 'restart', label: '重新开始' },
  { value: 'list_courses', label: '查看全部' },
  { value: 'out_of_scope', label: '超出范围' },
  { value: 'empty', label: '空输入' },
  { value: 'too_long', label: '超长输入' },
  { value: 'other', label: '其它' },
]

export function summarizeNodeConfig(
  type: WorkflowNodeType,
  config: WorkflowNodeConfig
): string {
  switch (type) {
    case 'entry': {
      const c = config as EntryConfig
      return c.welcomeText?.slice(0, 48) || '欢迎语'
    }
    case 'identity':
      return (config as IdentityConfig).promptWhenUnknown?.slice(0, 48) || '身份澄清'
    case 'slot_fill': {
      const c = config as SlotFillConfig
      return `${c.slots?.length ?? 0} 个槽位`
    }
    case 'scope': {
      const b = (config as ScopeConfig).binding || {}
      const n = [b.student, b.teacher, b.org].filter(Boolean).length
      return `已绑 ${n}/3 角色库`
    }
    case 'rag_recommend':
      return (config as RagRecommendConfig).systemExtra?.slice(0, 40) || '资料推荐'
    case 'rag_qa':
      return '班型详情追问'
    case 'rag_enroll':
      return '报名方式（禁止虚构）'
    case 'rag_platform':
      return '平台/会员/合作'
    case 'session_control':
      return '重置 / 列表'
    case 'boundary':
      return '边界与异常提示'
    default:
      return ''
  }
}

export function formatEdgeCondition(when?: EdgeCondition): string {
  if (!when) return 'always'
  switch (when.type) {
    case 'always':
      return 'always'
    case 'quick_action':
      return `点击「${when.action}」`
    case 'role_eq':
      return `role=${when.role}`
    case 'role_status':
      return `roleStatus=${when.status}`
    case 'constraints_ready':
      return `约束≥${when.min}`
    case 'intent':
      return `intent=${when.intent}`
    case 'state_flag':
      return `${when.path}==…`
    case 'and':
      return `AND(${when.items.map(formatEdgeCondition).join(', ')})`
    case 'or':
      return `OR(${when.items.map(formatEdgeCondition).join(', ')})`
    case 'not':
      return `NOT(${formatEdgeCondition(when.item)})`
    default:
      return '条件'
  }
}

function defaultSlotFillConfig(): SlotFillConfig {
  return {
    askOneMissingAtATime: true,
    slots: [
      {
        key: 'city',
        label: '城市/地点',
        askPrompt: '您更倾向哪个城市或地区上课？',
        requiredForCount: true,
      },
      {
        key: 'date',
        label: '可用日期',
        askPrompt: '问您方便的上课时间？（如 7 月、8 月或周末）',
        requiredForCount: true,
      },
      {
        key: 'format',
        label: '线上/线下',
        askPrompt: '您更希望线上还是线下？',
        requiredForCount: true,
      },
      {
        key: 'goal',
        label: '学习目标',
        askPrompt: '您最希望达成的学习目标是什么？',
        requiredForCount: true,
      },
    ],
  }
}

export function createDefaultNodeConfig(type: WorkflowNodeType): WorkflowNodeConfig {
  switch (type) {
    case 'entry':
      return {
        welcomeText:
          '您好，我是 AI 教育中心课程顾问。可咨询学生暑期营、教师培训或 OPC 平台服务。请选择入口，或直接说明您的身份。',
        quickActions: ['学生课程', '教师培训', '平台服务'],
      } satisfies EntryConfig
    case 'identity':
      return {
        promptWhenUnknown: '请问您是学生/家长、教师，还是机构/企业人员？',
        allowedRoles: ['student', 'teacher', 'org'],
      } satisfies IdentityConfig
    case 'slot_fill':
      return defaultSlotFillConfig()
    case 'scope':
      return {
        binding: { student: null, teacher: null, org: null },
        missingKbText:
          '当前身份对应的知识库尚未配置或未完成索引，请联系人工客服。',
      } satisfies ScopeConfig
    case 'rag_recommend':
      return {
        maxCourses: 2,
        lockFirstCourse: true,
        systemExtra:
          '仅依据当前知识库资料推荐 1–2 个真实班型；理由须逐条对应已采集约束；不得编造费用与档期。',
        quickActions: ['了解报名方式', '查看所有课程', '重新开始'],
      } satisfies RagRecommendConfig
    case 'rag_qa':
      return {
        systemExtra:
          '围绕 lockedCourse 回答；末尾可提及文档名与章节；资料不足则明确说明。',
        quickActions: ['了解报名方式', '重新开始'],
      } satisfies RagQaConfig
    case 'rag_enroll':
      return {
        systemExtra:
          '仅提供资料中已有的报名方式；禁止虚构链接、电话、余位或截止状态。',
        quickActions: ['重新开始'],
      } satisfies RagEnrollConfig
    case 'rag_platform':
      return {
        forbidCourseRecommend: true,
        systemExtra:
          '仅介绍 OPC 平台、会员与企业合作；不得输出学生/教师班型推荐，不得把会员价当作课程费用。',
        quickActions: ['查看所有课程', '重新开始'],
      } satisfies RagPlatformConfig
    case 'session_control':
      return {
        restartText: '好的，已为您重新开始。请重新选择服务入口。',
        listCoursesIntro: '根据当前身份资料，可了解的班型/服务如下：',
        quickActions: ['学生课程', '教师培训', '平台服务'],
      } satisfies SessionControlConfig
    case 'boundary':
      return {
        templates: {
          outOfScope:
            '该问题超出课程顾问服务范围。您可选择学生课程、教师培训或平台服务继续咨询。',
          modelError: '模型暂时不可用，请稍后重试，或联系人工客服。',
          crossMaterial:
            '该问题属于其他服务范畴，为避免信息混淆，请切换对应入口后再问。',
        },
        quickActions: ['学生课程', '教师培训', '平台服务'],
      } satisfies BoundaryConfig
  }
}

/** 规格默认拓扑（绑定库初始为空，需在 scope 节点选择真实 KB） */
export function createDefaultWorkflowGraph(): WorkflowGraph {
  return {
    version: '1',
    meta: {
      title: '默认顾问拓扑',
    },
    entryNodeId: 'n_entry',
    policies: {
      maxInputChars: 500,
      minConstraintsForRecommend: 2,
    },
    viewport: { x: 0, y: 0, zoom: 0.72 },
    nodes: [
      {
        id: 'n_entry',
        type: 'entry',
        name: '欢迎与分流',
        ui: { x: 40, y: 220 },
        config: createDefaultNodeConfig('entry'),
      },
      {
        id: 'n_identity',
        type: 'identity',
        name: '身份澄清',
        ui: { x: 300, y: 220 },
        config: createDefaultNodeConfig('identity'),
      },
      {
        id: 'n_slots',
        type: 'slot_fill',
        name: '约束采集',
        ui: { x: 560, y: 120 },
        config: createDefaultNodeConfig('slot_fill'),
      },
      {
        id: 'n_scope',
        type: 'scope',
        name: '知识范围绑定',
        ui: { x: 820, y: 120 },
        config: createDefaultNodeConfig('scope'),
      },
      {
        id: 'n_recommend',
        type: 'rag_recommend',
        name: '班型推荐',
        ui: { x: 1080, y: 40 },
        config: createDefaultNodeConfig('rag_recommend'),
      },
      {
        id: 'n_platform',
        type: 'rag_platform',
        name: '平台服务介绍',
        ui: { x: 1080, y: 260 },
        config: createDefaultNodeConfig('rag_platform'),
      },
      {
        id: 'n_qa',
        type: 'rag_qa',
        name: '详情追问',
        ui: { x: 1340, y: 40 },
        config: createDefaultNodeConfig('rag_qa'),
      },
      {
        id: 'n_enroll',
        type: 'rag_enroll',
        name: '报名引导',
        ui: { x: 1600, y: 40 },
        config: createDefaultNodeConfig('rag_enroll'),
      },
      {
        id: 'n_control',
        type: 'session_control',
        name: '会话控制',
        ui: { x: 560, y: 400 },
        config: createDefaultNodeConfig('session_control'),
      },
      {
        id: 'n_boundary',
        type: 'boundary',
        name: '边界与异常',
        ui: { x: 300, y: 400 },
        config: createDefaultNodeConfig('boundary'),
      },
    ],
    edges: [
      {
        id: 'e_entry_student',
        source: 'n_entry',
        target: 'n_identity',
        priority: 10,
        label: '点击学生',
        when: { type: 'quick_action', action: '学生课程' },
        apply: { role: 'student', roleStatus: 'confirmed' },
      },
      {
        id: 'e_entry_teacher',
        source: 'n_entry',
        target: 'n_identity',
        priority: 10,
        label: '点击教师',
        when: { type: 'quick_action', action: '教师培训' },
        apply: { role: 'teacher', roleStatus: 'confirmed' },
      },
      {
        id: 'e_entry_org',
        source: 'n_entry',
        target: 'n_identity',
        priority: 10,
        label: '点击平台',
        when: { type: 'quick_action', action: '平台服务' },
        apply: { role: 'org', roleStatus: 'confirmed' },
      },
      {
        id: 'e_entry_restart',
        source: 'n_entry',
        target: 'n_control',
        priority: 10,
        label: '重新开始',
        when: { type: 'quick_action', action: '重新开始' },
      },
      {
        id: 'e_entry_nl',
        source: 'n_entry',
        target: 'n_identity',
        priority: 100,
        label: '自然语言',
        when: { type: 'always' },
      },
      {
        id: 'e_id_out',
        source: 'n_identity',
        target: 'n_boundary',
        priority: 10,
        label: '超范围',
        when: { type: 'intent', intent: 'out_of_scope' },
      },
      {
        id: 'e_id_restart',
        source: 'n_identity',
        target: 'n_control',
        priority: 10,
        when: { type: 'intent', intent: 'restart' },
      },
      {
        id: 'e_id_org_skip_slots',
        source: 'n_identity',
        target: 'n_scope',
        priority: 15,
        label: '机构跳过约束',
        when: {
          type: 'and',
          items: [
            { type: 'role_status', status: 'confirmed' },
            { type: 'role_eq', role: 'org' },
          ],
        },
      },
      {
        id: 'e_id_confirmed',
        source: 'n_identity',
        target: 'n_slots',
        priority: 20,
        label: '学生/教师→采集',
        when: { type: 'role_status', status: 'confirmed' },
      },
      {
        id: 'e_id_wait',
        source: 'n_identity',
        target: 'n_identity',
        priority: 100,
        label: '继续澄清',
        when: { type: 'always' },
      },
      {
        id: 'e_slot_restart',
        source: 'n_slots',
        target: 'n_control',
        priority: 5,
        when: { type: 'intent', intent: 'restart' },
      },
      {
        id: 'e_slot_list',
        source: 'n_slots',
        target: 'n_control',
        priority: 5,
        when: { type: 'intent', intent: 'list_courses' },
      },
      {
        id: 'e_slot_out',
        source: 'n_slots',
        target: 'n_boundary',
        priority: 5,
        when: { type: 'intent', intent: 'out_of_scope' },
      },
      {
        id: 'e_slot_ready',
        source: 'n_slots',
        target: 'n_scope',
        priority: 20,
        label: '约束足够',
        when: { type: 'constraints_ready', min: 2 },
      },
      {
        id: 'e_slot_wait',
        source: 'n_slots',
        target: 'n_slots',
        priority: 100,
        label: '继续采集',
        when: { type: 'always' },
      },
      {
        id: 'e_scope_org',
        source: 'n_scope',
        target: 'n_platform',
        priority: 10,
        label: '机构→平台',
        when: { type: 'role_eq', role: 'org' },
      },
      {
        id: 'e_scope_course',
        source: 'n_scope',
        target: 'n_recommend',
        priority: 20,
        label: '学生/教师→推荐',
        when: {
          type: 'or',
          items: [
            { type: 'role_eq', role: 'student' },
            { type: 'role_eq', role: 'teacher' },
          ],
        },
      },
      {
        id: 'e_rec_enroll',
        source: 'n_recommend',
        target: 'n_enroll',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'ask_enroll' },
            { type: 'quick_action', action: '了解报名方式' },
          ],
        },
      },
      {
        id: 'e_rec_restart',
        source: 'n_recommend',
        target: 'n_control',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'restart' },
            { type: 'quick_action', action: '重新开始' },
          ],
        },
      },
      {
        id: 'e_rec_list',
        source: 'n_recommend',
        target: 'n_control',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'list_courses' },
            { type: 'quick_action', action: '查看所有课程' },
          ],
        },
      },
      {
        id: 'e_rec_qa',
        source: 'n_recommend',
        target: 'n_qa',
        priority: 30,
        label: '追问详情',
        when: { type: 'intent', intent: 'ask_detail' },
      },
      {
        id: 'e_rec_other_to_qa',
        source: 'n_recommend',
        target: 'n_qa',
        priority: 40,
        label: '其它→追问',
        when: { type: 'intent', intent: 'other' },
      },
      {
        id: 'e_rec_stay',
        source: 'n_recommend',
        target: 'n_recommend',
        priority: 100,
        label: '停留推荐',
        when: { type: 'always' },
      },
      {
        id: 'e_plat_restart',
        source: 'n_platform',
        target: 'n_control',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'restart' },
            { type: 'quick_action', action: '重新开始' },
          ],
        },
      },
      {
        id: 'e_plat_list',
        source: 'n_platform',
        target: 'n_control',
        priority: 10,
        label: '查看平台目录',
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'list_courses' },
            { type: 'quick_action', action: '查看所有课程' },
          ],
        },
      },
      {
        id: 'e_plat_out',
        source: 'n_platform',
        target: 'n_boundary',
        priority: 10,
        when: { type: 'intent', intent: 'out_of_scope' },
      },
      {
        id: 'e_plat_stay',
        source: 'n_platform',
        target: 'n_platform',
        priority: 100,
        label: '继续平台问答',
        when: { type: 'always' },
      },
      {
        id: 'e_qa_enroll',
        source: 'n_qa',
        target: 'n_enroll',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'ask_enroll' },
            { type: 'quick_action', action: '了解报名方式' },
          ],
        },
      },
      {
        id: 'e_qa_restart',
        source: 'n_qa',
        target: 'n_control',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'restart' },
            { type: 'quick_action', action: '重新开始' },
          ],
        },
      },
      {
        id: 'e_qa_cross',
        source: 'n_qa',
        target: 'n_boundary',
        priority: 10,
        when: { type: 'intent', intent: 'out_of_scope' },
      },
      {
        id: 'e_qa_stay',
        source: 'n_qa',
        target: 'n_qa',
        priority: 100,
        label: '多轮追问',
        when: { type: 'always' },
      },
      {
        id: 'e_enroll_restart',
        source: 'n_enroll',
        target: 'n_control',
        priority: 10,
        when: {
          type: 'or',
          items: [
            { type: 'intent', intent: 'restart' },
            { type: 'quick_action', action: '重新开始' },
          ],
        },
      },
      {
        id: 'e_enroll_qa',
        source: 'n_enroll',
        target: 'n_qa',
        priority: 100,
        label: '报名后继续问',
        when: { type: 'always' },
      },
      {
        id: 'e_ctrl_done',
        source: 'n_control',
        target: 'n_entry',
        priority: 10,
        label: '重置回入口',
        when: { type: 'intent', intent: 'restart' },
        apply: { clearSession: true, clearRole: true },
      },
      {
        id: 'e_ctrl_role',
        source: 'n_control',
        target: 'n_identity',
        priority: 15,
        label: '控制节点选身份',
        when: { type: 'intent', intent: 'choose_role' },
      },
      {
        id: 'e_ctrl_list_back',
        source: 'n_control',
        target: 'n_entry',
        priority: 20,
        when: { type: 'always' },
      },
      {
        id: 'e_bound_restart',
        source: 'n_boundary',
        target: 'n_control',
        priority: 10,
        when: { type: 'quick_action', action: '重新开始' },
      },
      {
        id: 'e_bound_student',
        source: 'n_boundary',
        target: 'n_identity',
        priority: 10,
        when: { type: 'quick_action', action: '学生课程' },
        apply: {
          role: 'student',
          roleStatus: 'confirmed',
          clearSession: true,
        },
      },
      {
        id: 'e_bound_teacher',
        source: 'n_boundary',
        target: 'n_identity',
        priority: 10,
        when: { type: 'quick_action', action: '教师培训' },
        apply: {
          role: 'teacher',
          roleStatus: 'confirmed',
          clearSession: true,
        },
      },
      {
        id: 'e_bound_org',
        source: 'n_boundary',
        target: 'n_identity',
        priority: 10,
        when: { type: 'quick_action', action: '平台服务' },
        apply: { role: 'org', roleStatus: 'confirmed', clearSession: true },
      },
      {
        id: 'e_bound_back',
        source: 'n_boundary',
        target: 'n_entry',
        priority: 100,
        when: { type: 'always' },
      },
    ],
  }
}

const SPEC_NODE_TYPES = new Set<string>([
  'entry',
  'identity',
  'slot_fill',
  'scope',
  'rag_recommend',
  'rag_qa',
  'rag_enroll',
  'rag_platform',
  'session_control',
  'boundary',
])

/** 将任意存盘 JSON 规范为 v1 图；旧七步画布无法迁移时回退默认图 */
export function normalizeWorkflowGraph(raw: unknown): WorkflowGraph {
  if (!raw || typeof raw !== 'object') return createDefaultWorkflowGraph()
  const obj = raw as Record<string, unknown>
  const nodesArr = obj.nodes

  if (!Array.isArray(nodesArr) || nodesArr.length === 0) {
    return createDefaultWorkflowGraph()
  }

  const first = nodesArr[0] as Record<string, unknown>
  const data = first.data as Record<string, unknown> | undefined

  // 旧七步画布：type=workflowStep + data.kind
  if (data?.kind && !SPEC_NODE_TYPES.has(String(first.type))) {
    return createDefaultWorkflowGraph()
  }

  // React Flow 快照（type=agentNode）
  if (first.type === 'agentNode' || data?.nodeType) {
    return reactFlowSnapshotToGraph(obj)
  }

  // 规格节点（type=entry/identity/…）
  if (SPEC_NODE_TYPES.has(String(first.type))) {
    return sanitizeSpecGraph({
      version: '1',
      entryNodeId: obj.entryNodeId,
      policies: obj.policies,
      nodes: obj.nodes,
      edges: obj.edges,
      meta: obj.meta,
      viewport: obj.viewport,
    })
  }

  return createDefaultWorkflowGraph()
}

function sanitizeSpecGraph(obj: Record<string, unknown>): WorkflowGraph {
  const base = createDefaultWorkflowGraph()
  const filtered = Array.isArray(obj.nodes)
    ? (obj.nodes as WorkflowSpecNode[]).filter((n) =>
        SPEC_NODE_TYPES.has(n?.type)
      )
    : []
  // 过滤后为空说明存盘已损坏，回退默认拓扑（避免画布空白）
  const nodes = filtered.length > 0 ? filtered : base.nodes
  const edges = Array.isArray(obj.edges) && (obj.edges as unknown[]).length > 0
    ? (obj.edges as WorkflowSpecEdge[])
    : filtered.length > 0
      ? (obj.edges as WorkflowSpecEdge[]) || []
      : base.edges
  const policies = (obj.policies as WorkflowGraph['policies']) || base.policies
  const entryNodeId =
    typeof obj.entryNodeId === 'string' &&
    nodes.some((n) => n.id === obj.entryNodeId)
      ? obj.entryNodeId
      : nodes[0]?.id || base.entryNodeId

  return {
    version: '1',
    entryNodeId,
    policies: {
      maxInputChars: Number(policies.maxInputChars) || 500,
      minConstraintsForRecommend:
        Number(policies.minConstraintsForRecommend) || 2,
    },
    nodes: nodes.map((n) => ({
      ...n,
      name: n.name || NODE_TYPE_META[n.type]?.label || n.id,
      config: n.config || createDefaultNodeConfig(n.type),
      ui: {
        x: typeof n.ui?.x === 'number' ? n.ui.x : 0,
        y: typeof n.ui?.y === 'number' ? n.ui.y : 0,
      },
    })),
    edges: (edges || []).map((e) => ({
      ...e,
      priority: typeof e.priority === 'number' ? e.priority : 100,
      when: e.when || { type: 'always' as const },
    })),
    meta: (obj.meta as Record<string, unknown>) || undefined,
    viewport: (obj.viewport as Viewport) || base.viewport,
  }
}

function reactFlowSnapshotToGraph(obj: Record<string, unknown>): WorkflowGraph {
  const rfNodes = (obj.nodes as WorkflowFlowNode[]) || []
  const rfEdges = (obj.edges as Edge[]) || []
  const nodes: WorkflowSpecNode[] = rfNodes
    .map((n): WorkflowSpecNode | null => {
      const nodeType = n.data?.nodeType
      if (!nodeType || !SPEC_NODE_TYPES.has(nodeType)) return null
      return {
        id: n.id,
        type: nodeType,
        name: n.data?.name || NODE_TYPE_META[nodeType].label,
        ui: { x: n.position?.x ?? 0, y: n.position?.y ?? 0 },
        config: n.data?.config || createDefaultNodeConfig(nodeType),
      }
    })
    .filter((n): n is WorkflowSpecNode => n !== null)

  if (nodes.length === 0) return createDefaultWorkflowGraph()

  const edges: WorkflowSpecEdge[] = rfEdges.map((e) => {
    const d = (e.data || {}) as WorkflowFlowEdgeData
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      priority: d.priority ?? 100,
      when: d.when,
      apply: d.apply,
      label: d.label || (typeof e.label === 'string' ? e.label : undefined),
    }
  })
  return sanitizeSpecGraph({
    version: '1',
    entryNodeId: (obj.entryNodeId as string) || nodes[0]?.id,
    policies: obj.policies,
    nodes,
    edges,
    meta: obj.meta,
    viewport: obj.viewport,
  })
}

export function graphToReactFlow(graph: WorkflowGraph): {
  nodes: WorkflowFlowNode[]
  edges: Edge[]
} {
  const nodes: WorkflowFlowNode[] = graph.nodes.map((n) => ({
    id: n.id,
    type: 'agentNode',
    position: { x: n.ui?.x ?? 0, y: n.ui?.y ?? 0 },
    data: {
      name: n.name,
      nodeType: n.type,
      config: n.config,
      summary: summarizeNodeConfig(n.type, n.config),
    },
  }))

  const edges: Edge[] = graph.edges.map((e) => {
    const label = e.label || formatEdgeCondition(e.when)
    const isSelf = e.source === e.target
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label,
      animated: e.priority < 50,
      style: isSelf ? { strokeDasharray: '4 3' } : undefined,
      data: {
        priority: e.priority,
        when: e.when,
        apply: e.apply,
        label: e.label,
      } satisfies WorkflowFlowEdgeData,
    }
  })

  return { nodes, edges }
}

export function reactFlowToGraph(
  graph: WorkflowGraph,
  nodes: WorkflowFlowNode[],
  edges: Edge[],
  viewport?: Viewport
): WorkflowGraph {
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  return {
    ...graph,
    viewport: viewport ?? graph.viewport,
    nodes: graph.nodes.map((n) => {
      const rf = nodeById.get(n.id)
      if (!rf) return n
      return {
        ...n,
        name: rf.data.name,
        type: rf.data.nodeType,
        config: rf.data.config,
        ui: { x: rf.position.x, y: rf.position.y },
      }
    }),
    edges: edges.map((e) => {
      const d = (e.data || {}) as WorkflowFlowEdgeData
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        priority: d.priority ?? 100,
        when: d.when ?? { type: 'always' },
        apply: d.apply,
        label: d.label,
      }
    }),
  }
}

export function updateSpecNode(
  graph: WorkflowGraph,
  nodeId: string,
  patch: Partial<Pick<WorkflowSpecNode, 'name' | 'config' | 'type'>>
): WorkflowGraph {
  return {
    ...graph,
    nodes: graph.nodes.map((n) => {
      if (n.id !== nodeId) return n
      const next = { ...n, ...patch }
      if (patch.config) {
        next.config = patch.config
      }
      return next
    }),
  }
}

export function updateSpecEdge(
  graph: WorkflowGraph,
  edgeId: string,
  patch: Partial<WorkflowSpecEdge>
): WorkflowGraph {
  return {
    ...graph,
    edges: graph.edges.map((e) => (e.id === edgeId ? { ...e, ...patch } : e)),
  }
}

/** 从 scope 节点收集绑定知识库 ID（供 Agent 资源索引） */
export function collectBoundKnowledgeBaseIds(graph: WorkflowGraph): string[] {
  const ids = new Set<string>()
  for (const n of graph.nodes) {
    if (n.type !== 'scope') continue
    const b = (n.config as ScopeConfig).binding || {}
    for (const v of [b.student, b.teacher, b.org]) {
      if (v && !String(v).startsWith('kb_material_')) ids.add(String(v))
    }
  }
  return [...ids]
}

export function getEntryWelcome(graph: WorkflowGraph): {
  welcomeMessage: string
  menuButtons: string[]
} {
  const entry = graph.nodes.find((n) => n.id === graph.entryNodeId && n.type === 'entry')
    || graph.nodes.find((n) => n.type === 'entry')
  const cfg = (entry?.config || createDefaultNodeConfig('entry')) as EntryConfig
  return {
    welcomeMessage: cfg.welcomeText,
    menuButtons: cfg.quickActions || [],
  }
}

/** 兼容旧字段：从规格图派生粗粒度 stateMachine 列表（仅展示/兼容） */
export function workflowGraphToStateMachine(graph: WorkflowGraph) {
  const order: WorkflowNodeType[] = [
    'entry',
    'identity',
    'slot_fill',
    'rag_recommend',
    'rag_qa',
    'rag_enroll',
  ]
  const idMap: Record<string, string> = {
    entry: 'welcome',
    identity: 'identity',
    slot_fill: 'constraints',
    rag_recommend: 'recommend',
    rag_qa: 'qa',
    rag_enroll: 'enroll',
  }
  return order
    .map((t) => {
      const n = graph.nodes.find((x) => x.type === t)
      if (!n) return null
      return {
        id: idMap[t] as
          | 'welcome'
          | 'identity'
          | 'constraints'
          | 'recommend'
          | 'qa'
          | 'enroll',
        label: n.name,
        description: summarizeNodeConfig(t, n.config),
        enabled: true,
      }
    })
    .filter(Boolean)
}
