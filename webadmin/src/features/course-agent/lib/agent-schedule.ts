import type { CourseAgentSchedule } from '../data/types'

export const DEFAULT_SCHEDULE_TASK_PROMPT =
  '只根据用户自己发送的消息归纳目标、疾病、过敏、忌口；没有新事实不要改画像，不要编造未提及的健康状况。'

export const DEFAULT_AGENT_SCHEDULE: CourseAgentSchedule = {
  enabled: false,
  intervalHours: 2,
  runMode: 'chat',
  visibleInChat: true,
  target: 'all_users',
  onlyIfNewMessages: true,
  lookbackHours: 24,
  taskPrompt: DEFAULT_SCHEDULE_TASK_PROMPT,
}

export function normalizeAgentSchedule(
  raw?: CourseAgentSchedule | null
): CourseAgentSchedule {
  return {
    ...DEFAULT_AGENT_SCHEDULE,
    ...raw,
    intervalHours: raw?.intervalHours || DEFAULT_AGENT_SCHEDULE.intervalHours,
    lookbackHours: raw?.lookbackHours || DEFAULT_AGENT_SCHEDULE.lookbackHours,
    taskPrompt: raw?.taskPrompt?.trim() || DEFAULT_SCHEDULE_TASK_PROMPT,
  }
}

export function isAgentVisibleInChat(agent: {
  status?: string
  visibleInChat?: boolean
  runMode?: string
  schedule?: { visibleInChat?: boolean; runMode?: string } | null
}) {
  if (agent.status !== 'active') return false
  const visible = agent.visibleInChat ?? agent.schedule?.visibleInChat
  const runMode = agent.runMode ?? agent.schedule?.runMode
  if (visible === false) return false
  if (runMode === 'scheduled') return false
  return true
}

export function isScheduledHarnessAgent(agent: {
  agentType?: string
  scheduleEnabled?: boolean
  runMode?: string
  schedule?: { enabled?: boolean; runMode?: string } | null
}) {
  if (agent.agentType && agent.agentType !== 'autonomous') return false
  if (agent.scheduleEnabled) return true
  if (agent.runMode === 'scheduled' || agent.schedule?.runMode === 'scheduled') {
    return true
  }
  if (agent.schedule?.enabled) return true
  return false
}

export function splitScheduleInterval(hours: number): {
  value: number
  unit: 'hours' | 'minutes'
} {
  if (hours > 0 && hours < 1) {
    return { value: Math.round(hours * 60), unit: 'minutes' }
  }
  return { value: hours, unit: 'hours' }
}

export function toIntervalHours(value: number, unit: 'hours' | 'minutes') {
  if (!Number.isFinite(value) || value <= 0) return 2
  return unit === 'minutes' ? value / 60 : value
}
