import type { CourseAgentSessionState, CourseAgentStep } from '../data/types'

const STEP_LABELS: Record<CourseAgentStep, string> = {
  welcome: '欢迎分流',
  identity: '身份澄清',
  constraints: '约束采集',
  recommend: '班型推荐',
  qa: '详情追问',
  enroll: '报名引导',
  preview: '对话预览',
}

const ROLE_LABELS = {
  student: '学生/家长',
  teacher: '教师',
  org: '机构/企业',
} as const

type AgentStatusBarProps = {
  state: CourseAgentSessionState
  className?: string
}

export function AgentStatusBar({ state, className }: AgentStatusBarProps) {
  const constraintParts = [
    state.role ? ROLE_LABELS[state.role] : null,
    state.constraints.city,
    state.constraints.date,
    state.constraints.format === 'online'
      ? '线上'
      : state.constraints.format === 'offline'
        ? '线下'
        : null,
    state.constraints.goal,
    state.lockedCourse ? `锁定：${state.lockedCourse}` : null,
  ].filter(Boolean)

  return (
    <div
      className={`flex flex-wrap items-center gap-2 border-b bg-muted/40 px-4 py-2 text-xs ${className ?? ''}`}
    >
      <span className='rounded-md bg-primary/10 px-2 py-0.5 font-medium text-primary'>
        {STEP_LABELS[state.step]}
      </span>
      {constraintParts.length > 0 ? (
        <span className='text-muted-foreground'>
          {constraintParts.join(' · ')}
        </span>
      ) : (
        <span className='text-muted-foreground'>等待用户输入</span>
      )}
    </div>
  )
}

export { STEP_LABELS, ROLE_LABELS }
