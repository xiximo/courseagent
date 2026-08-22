import type { CourseAgentReactTool } from '../data/types'

export const HARNESS_PROFILE_TOOLS: CourseAgentReactTool[] = [
  {
    id: 'tool_get_profile',
    name: 'get_user_profile',
    kind: 'profile_get',
    description:
      '获取当前登录用户的画像、目标与约束（疾病、过敏、忌口）。回答任何膳食方案、蛋白质、热量或食材推荐前必须先调用。若存在肾病、痛风、过敏等，回答必须避开冲突建议。',
    knowledgeBaseIds: [],
    enabled: true,
  },
  {
    id: 'tool_update_profile',
    name: 'update_user_profile',
    kind: 'profile_update',
    description:
      '从数据库读取用户发送的消息，调用大模型归纳目标/疾病/过敏/忌口后写入画像。对话中出现新健康事实时必须调用。定时任务可按全部用户批量刷新。不要编造用户未说过的内容。',
    knowledgeBaseIds: [],
    enabled: true,
  },
]

export function isProfileTool(tool: CourseAgentReactTool) {
  return (
    tool.kind === 'profile_get' ||
    tool.kind === 'profile_update' ||
    tool.name === 'get_user_profile' ||
    tool.name === 'update_user_profile'
  )
}

export function withHarnessProfileTools(
  tools: CourseAgentReactTool[]
): CourseAgentReactTool[] {
  const others = tools.filter((tool) => !isProfileTool(tool))
  const existing = new Map(
    tools.filter(isProfileTool).map((tool) => [tool.name, tool])
  )
  const builtins = HARNESS_PROFILE_TOOLS.map((item) => {
    const prev = existing.get(item.name)
    return prev ? { ...item, enabled: prev.enabled } : item
  })
  return [...builtins, ...others]
}
