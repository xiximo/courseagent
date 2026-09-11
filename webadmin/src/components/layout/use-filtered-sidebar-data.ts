import { useMemo } from 'react'
import { MessageSquare } from 'lucide-react'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import type { AppPermission } from '@/lib/auth/permissions'
import { useAuthStore } from '@/stores/auth-store'
import { useCourseAgentsQuery } from '@/features/course-agent/hooks/use-course-agents-query'
import { isAgentVisibleInChat } from '@/features/course-agent/lib/agent-schedule'
import { sidebarData } from './data/sidebar-data'
import { type NavGroup, type NavItem } from './types'

function filterNavItems(
  items: NavItem[],
  can: (p: AppPermission) => boolean
): NavItem[] {
  return items
    .map((item) => {
      if ('items' in item && item.items) {
        const sub = item.items.filter(
          (subItem) =>
            !subItem.requiredPermissions ||
            subItem.requiredPermissions.every((p) => can(p))
        )
        if (sub.length === 0) return null
        return { ...item, items: sub }
      }
      if (
        item.requiredPermissions &&
        !item.requiredPermissions.every((p) => can(p))
      ) {
        return null
      }
      return item
    })
    .filter(Boolean) as NavItem[]
}

export function useFilteredSidebarData() {
  const { can, isPlatformAdmin } = useAppPermissions()
  const user = useAuthStore((s) => s.auth.user)
  const showOrgChat = can('course_agent_view') && Boolean(user?.tenantId)
  const { data: agents = [] } = useCourseAgentsQuery(showOrgChat)

  return useMemo(() => {
    const navGroups: NavGroup[] = sidebarData.navGroups
      .map((group) => {
        const items = filterNavItems(group.items, can)
        if (items.length === 0) return null
        return { ...group, items }
      })
      .filter(Boolean) as NavGroup[]

    const tenantId = user?.tenantId ?? null
    const published = agents.filter((agent) => {
      if (tenantId && agent.tenantId && agent.tenantId !== tenantId) return false
      if (!isAgentVisibleInChat(agent)) return false
      if (isPlatformAdmin) return false
      if (user?.planCode === 'pro') return true
      return (agent.agentType ?? 'workflow') === 'basic'
    })
    if (showOrgChat && !isPlatformAdmin && published.length > 0) {
      navGroups.unshift({
        title: 'nav.group.agentChat',
        items: published.map((agent) => ({
          title: agent.name,
          url: `/admin/chat/${agent.agentId}`,
          icon: MessageSquare,
          rawTitle: true,
          requiredPermissions: ['course_agent_view'],
        })),
      })
    }

    const tenantName = user?.tenantName?.trim()
    const brandName = tenantName
      ? tenantName
      : isPlatformAdmin
        ? '启明顾问'
        : '本机构'
    const plan = tenantName
      ? user?.planCode === 'pro'
        ? '专业版'
        : '免费版'
      : isPlatformAdmin
        ? '平台'
        : ''

    return {
      ...sidebarData,
      navGroups,
      teams: [
        {
          ...sidebarData.teams[0],
          name: brandName,
          plan,
        },
      ],
    }
  }, [agents, can, isPlatformAdmin, showOrgChat, user])
}
