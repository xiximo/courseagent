import { useMemo } from 'react'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import type { AppPermission } from '@/lib/auth/permissions'
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

  return useMemo(() => {
    const navGroups: NavGroup[] = sidebarData.navGroups
      .map((group) => {
        const items = filterNavItems(group.items, can)
        if (items.length === 0) return null
        return { ...group, items }
      })
      .filter(Boolean) as NavGroup[]

    return { ...sidebarData, navGroups }
  }, [can])
}
