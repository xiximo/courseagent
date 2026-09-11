export type AppPermission =
  | 'course_agent_view'
  | 'course_agent_config'
  | 'org_workspace'
  | 'user_manage'
  | 'platform_manage'

export function isPlatformAdmin(roleCodes: string[]): boolean {
  return roleCodes.some((code) =>
    ['sys_admin', 'SYSTEM_ADMIN', 'admin'].includes(code)
  )
}

export function isOrgAdmin(roleCodes: string[]): boolean {
  return roleCodes.some((code) => code === 'org_admin')
}

export function isAdmin(roleCodes: string[]): boolean {
  return isPlatformAdmin(roleCodes) || isOrgAdmin(roleCodes)
}

export function hasPermission(
  roleCodes: string[],
  permission: AppPermission
): boolean {
  if (permission === 'course_agent_view') {
    return true
  }
  if (permission === 'org_workspace') {
    return isOrgAdmin(roleCodes)
  }
  if (permission === 'course_agent_config') {
    return isAdmin(roleCodes) || isDevMockFallback()
  }
  if (permission === 'user_manage' || permission === 'platform_manage') {
    return isPlatformAdmin(roleCodes) || isDevMockFallback()
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
  if (base === '/saasadmin' || base.startsWith('/saasadmin/')) {
    return hasPermission(roleCodes, 'platform_manage')
  }
  if (base === '/admin/chat' || base.startsWith('/admin/chat/')) {
    return hasPermission(roleCodes, 'course_agent_view')
  }
  if (base.startsWith('/admin/course-agents/leads')) {
    return hasPermission(roleCodes, 'org_workspace')
  }
  if (base.startsWith('/admin/members')) {
    return hasPermission(roleCodes, 'org_workspace')
  }
  if (base.startsWith('/admin/course-agents')) {
    return hasPermission(roleCodes, 'org_workspace')
  }
  if (base.startsWith('/admin/models')) {
    return hasPermission(roleCodes, 'platform_manage')
  }
  if (
    base === '/admin' ||
    base === '/admin/' ||
    base.startsWith('/admin/knowledge') ||
    base.startsWith('/admin/usage')
  ) {
    return hasPermission(roleCodes, 'org_workspace')
  }
  return true
}

function isDevMockFallback(): boolean {
  return (
    import.meta.env.VITE_DEV_MOCK === 'true' ||
    import.meta.env.VITE_QIBIAO_MOCK === 'true'
  )
}
