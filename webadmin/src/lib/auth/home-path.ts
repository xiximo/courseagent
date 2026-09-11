import { listCourseAgents } from '@/lib/api/course-agent'
import { isAgentVisibleInChat } from '@/features/course-agent/lib/agent-schedule'
import type { AuthUserProfile } from '@/lib/api/auth'
import { canAccessPath, isOrgAdmin, isPlatformAdmin } from '@/lib/auth/permissions'
import { resolveAuthRedirect } from '@/lib/auth-redirect'

export type AppNavTarget = {
  to: string
  params?: Record<string, string>
}

const PLATFORM_HOME: AppNavTarget = { to: '/saasadmin' }
const ORG_HOME: AppNavTarget = { to: '/admin' }
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
  if (isPlatformAdmin(roleCodes)) return PLATFORM_HOME
  if (isOrgAdmin(roleCodes)) return ORG_HOME
  return (await firstPublishedChatTarget()) ?? FALLBACK_HOME
}

async function findOwnedAgent(agentId: string) {
  try {
    const agents = await listCourseAgents()
    return agents.find((item) => item.agentId === agentId) ?? null
  } catch {
    return null
  }
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
    const configMatch = base.match(/^\/admin\/course-agents\/([^/]+)$/)
    const agentId = decodeURIComponent(chatMatch?.[1] || configMatch?.[1] || '')
    if (agentId) {
      const owned = await findOwnedAgent(agentId)
      if (owned && chatMatch) {
        return {
          to: '/admin/chat/$agentId',
          params: { agentId },
        }
      }
      if (owned && configMatch && isOrgAdmin(roleCodes)) {
        return {
          to: '/admin/course-agents/$agentId',
          params: { agentId },
        }
      }
      return resolveLoggedInHome(roleCodes)
    }
    return { to: requested }
  }
  return resolveLoggedInHome(roleCodes)
}

export function navigateToAppTarget(
  navigate: (opts: {
    to: string
    params?: Record<string, string>
    replace?: boolean
  }) => void,
  dest: AppNavTarget,
  replace = false
) {
  if (dest.params?.agentId) {
    navigate({
      to: '/admin/chat/$agentId',
      params: { agentId: dest.params.agentId },
      replace,
    })
    return
  }
  navigate({ to: dest.to, replace })
}
