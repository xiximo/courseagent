export type AppPermission = 'course_agent_view' | 'course_agent_config' | 'user_manage'

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
    // 已登录即可对话；配置/用户管理仍走管理员权限
    return true
  }
  if (permission === 'course_agent_config' || permission === 'user_manage') {
    return isAdmin(roleCodes) || isDevMockFallback()
  }
  return false
}

export function canAccessPath(roleCodes: string[], path: string): boolean {
  const base = path.split('?')[0] ?? path
  if (base === '/users' || base.startsWith('/users/')) {
    return hasPermission(roleCodes, 'user_manage')
  }
  if (base === '/audit' || base.startsWith('/audit/')) {
    return hasPermission(roleCodes, 'user_manage')
  }
  if (base === '/admin/chat' || base.startsWith('/admin/chat/')) {
    return hasPermission(roleCodes, 'course_agent_view')
  }
  if (
    base.startsWith('/admin/course-agents') ||
    base.startsWith('/admin/knowledge') ||
    base.startsWith('/admin/models')
  ) {
    return hasPermission(roleCodes, 'course_agent_config')
  }
  return true
}

function isDevMockFallback(): boolean {
  return (
    import.meta.env.VITE_DEV_MOCK === 'true' ||
    import.meta.env.VITE_QIBIAO_MOCK === 'true'
  )
}
