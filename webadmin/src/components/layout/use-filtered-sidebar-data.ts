import { useMemo } from 'react'
import { MessageSquare } from 'lucide-react'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import type { AppPermission } from '@/lib/auth/permissions'
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
  const { can } = useAppPermissions()
  const canViewAgents = can('course_agent_view')
  const { data: agents = [] } = useCourseAgentsQuery(canViewAgents)

  return useMemo(() => {
    const navGroups: NavGroup[] = sidebarData.navGroups
      .map((group) => {
        const items = filterNavItems(group.items, can)
        if (items.length === 0) return null
        return { ...group, items }
      })
      .filter(Boolean) as NavGroup[]

    const published = agents.filter((agent) => isAgentVisibleInChat(agent))
    if (canViewAgents && published.length > 0) {
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

    return { ...sidebarData, navGroups }
  }, [agents, can, canViewAgents])
}
