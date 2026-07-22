export type AppPermission = 'course_agent_view' | 'course_agent_config'

export function isAdmin(roleCodes: string[]): boolean {
  return roleCodes.some((code) =>
    ['sys_admin', 'SYSTEM_ADMIN', 'admin'].includes(code)
  )
}

export function hasPermission(
  roleCodes: string[],
  permission: AppPermission
): boolean {
  if (permission === 'course_agent_view') {
    return roleCodes.length > 0 || isDevMockFallback()
  }
  if (permission === 'course_agent_config') {
    return isAdmin(roleCodes) || isDevMockFallback()
  }
  return false
}

export function canAccessPath(roleCodes: string[], path: string): boolean {
  const base = path.split('?')[0]
  if (
    base.startsWith('/admin/course-agents') ||
    base.startsWith('/admin/knowledge') ||
    base.startsWith('/admin/models')
  ) {
    return hasPermission(roleCodes, 'course_agent_view')
  }
  return true
}

function isDevMockFallback(): boolean {
  return (
    import.meta.env.VITE_DEV_MOCK === 'true' ||
    import.meta.env.VITE_QIBIAO_MOCK === 'true'
  )
}
