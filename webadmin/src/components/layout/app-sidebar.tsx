import { useEffect } from 'react'
import { fetchCurrentUser } from '@/lib/api/auth'
import { useAuthStore } from '@/stores/auth-store'
import { useLayout } from '@/context/layout-provider'
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar'
import { NavGroup } from './nav-group'
import { TeamSwitcher } from './team-switcher'
import { useFilteredSidebarData } from './use-filtered-sidebar-data'

export function AppSidebar() {
  const { collapsible, variant } = useLayout()
  const data = useFilteredSidebarData()
  const accessToken = useAuthStore((s) => s.auth.accessToken)
  const setUser = useAuthStore((s) => s.auth.setUser)

  useEffect(() => {
    if (!accessToken) return
    void fetchCurrentUser()
      .then(setUser)
      .catch(() => undefined)
  }, [accessToken, setUser])

  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        {data.navGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))}
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
