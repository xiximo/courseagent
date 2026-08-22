import { listCourseAgents } from '@/lib/api/course-agent'
import { isAgentVisibleInChat } from '@/features/course-agent/lib/agent-schedule'
import type { AuthUserProfile } from '@/lib/api/auth'
import { canAccessPath, isAdmin } from '@/lib/auth/permissions'
import { resolveAuthRedirect } from '@/lib/auth-redirect'

export type AppNavTarget = {
  to: string
  params?: Record<string, string>
}

const ADMIN_HOME: AppNavTarget = { to: '/admin/course-agents' }
const FALLBACK_HOME: AppNavTarget = { to: '/settings/account' }

function loadRoleCodes(): string[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const raw = localStorage.getItem('taixing_auth_user')
    if (!raw) return []
    const user = JSON.parse(raw) as AuthUserProfile
    return user.roleCodes ?? []
  } catch {
    return []
  }
}

export async function firstPublishedChatTarget(): Promise<AppNavTarget | null> {
  try {
    const agents = await listCourseAgents()
    const published = agents.filter((item) => isAgentVisibleInChat(item))
    const first =
      published.find((item) => item.isDefault) ?? published[0] ?? null
    if (!first) return null
    return {
      to: '/admin/chat/$agentId',
      params: { agentId: first.agentId },
    }
  } catch {
    return null
  }
}

export async function resolveLoggedInHome(
  roleCodes = loadRoleCodes()
): Promise<AppNavTarget> {
  if (isAdmin(roleCodes)) return ADMIN_HOME
  return (await firstPublishedChatTarget()) ?? FALLBACK_HOME
}

export async function resolvePostLoginTarget(
  redirectTo: string | undefined,
  roleCodes: string[]
): Promise<AppNavTarget> {
  const requested = resolveAuthRedirect(redirectTo, '')
  const base = requested.split('?')[0] ?? requested
  if (
    requested &&
    requested !== '/' &&
    canAccessPath(roleCodes, base)
  ) {
    const chatMatch = base.match(/^\/admin\/chat\/([^/]+)$/)
    if (chatMatch?.[1]) {
      return {
        to: '/admin/chat/$agentId',
        params: { agentId: decodeURIComponent(chatMatch[1]) },
      }
    }
    return { to: requested }
  }
  return resolveLoggedInHome(roleCodes)
}
