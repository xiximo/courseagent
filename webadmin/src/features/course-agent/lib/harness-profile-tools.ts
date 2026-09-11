import type { CourseAgentReactTool } from '../data/types'

export function isProfileTool(tool: CourseAgentReactTool) {
  return (
    tool.kind === 'profile_get' ||
    tool.kind === 'profile_update' ||
    tool.name === 'get_user_profile' ||
    tool.name === 'update_user_profile'
  )
}

export function withoutProfileTools(
  tools: CourseAgentReactTool[]
): CourseAgentReactTool[] {
  return tools.filter((tool) => !isProfileTool(tool))
}
