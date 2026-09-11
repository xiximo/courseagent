import {
  BarChart3,
  Bot,
  Building2,
  ClipboardList,
  CreditCard,
  Database,
  GraduationCap,  LayoutDashboard,
  Settings,
  SlidersHorizontal,
  UserCog,
  Users,
  Wrench,
} from 'lucide-react'
import { type SidebarData } from '../types'

/** `title` 为 i18n key（`nav.*`），在 `NavGroup` / 命令面板中用 `t(title)` 渲染 */
export const sidebarData: SidebarData = {
  user: {
    name: '管理员',
    email: 'admin@example.com',
    avatar: '/avatars/shadcn.jpg',
  },
  teams: [
    {
      name: '启明顾问',
      logo: GraduationCap,
      plan: '',
    },
  ],
  navGroups: [
    {
      title: 'nav.group.orgWorkspace',
      items: [
        {
          title: 'nav.link.orgHome',
          url: '/admin',
          icon: GraduationCap,
          requiredPermissions: ['org_workspace'],
        },
        {
          title: 'nav.link.orgMembers',
          url: '/admin/members',
          icon: Users,
          requiredPermissions: ['org_workspace'],
        },
        {
          title: 'nav.link.orgAgents',
          url: '/admin/course-agents',
          icon: Bot,
          requiredPermissions: ['org_workspace'],
        },
        {
          title: 'nav.link.agentKnowledge',
          url: '/admin/knowledge',
          icon: Database,
          requiredPermissions: ['org_workspace'],
        },
        {
          title: 'nav.link.agentLeads',
          url: '/admin/course-agents/leads',
          icon: Users,
          requiredPermissions: ['org_workspace'],
        },
        {
          title: 'nav.link.usageStats',
          url: '/admin/usage',
          icon: BarChart3,
          requiredPermissions: ['org_workspace'],
        },
        {
          title: 'nav.link.plans',
          url: '/plans',
          icon: CreditCard,
          requiredPermissions: ['org_workspace'],
        },
      ],
    },
    {
      title: 'nav.group.platform',
      items: [
        {
          title: 'nav.link.platformHome',
          url: '/saasadmin',
          icon: LayoutDashboard,
          requiredPermissions: ['platform_manage'],
        },
        {
          title: 'nav.link.platformTenants',
          url: '/saasadmin/tenants',
          icon: Building2,
          requiredPermissions: ['platform_manage'],
        },
        {
          title: 'nav.link.platformUsage',
          url: '/saasadmin/usage',
          icon: BarChart3,
          requiredPermissions: ['platform_manage'],
        },
      ],
    },
    {
      title: 'nav.group.platformProduct',
      items: [
        {
          title: 'nav.link.platformAgents',
          url: '/saasadmin/agents',
          icon: GraduationCap,
          requiredPermissions: ['platform_manage'],
        },
        {
          title: 'nav.link.platformKnowledge',
          url: '/saasadmin/knowledge',
          icon: Database,
          requiredPermissions: ['platform_manage'],
        },
        {
          title: 'nav.link.agentModel',
          url: '/saasadmin/models',
          icon: SlidersHorizontal,
          requiredPermissions: ['platform_manage'],
        },
      ],
    },
    {
      title: 'nav.group.platformGovernance',
      items: [
        {
          title: 'nav.link.userManagement',
          url: '/saasadmin/users',
          icon: UserCog,
          requiredPermissions: ['platform_manage'],
        },
        {
          title: 'nav.link.auditManagement',
          url: '/saasadmin/audit',
          icon: ClipboardList,
          requiredPermissions: ['platform_manage'],
        },
      ],
    },
    {
      title: 'nav.group.preferences',
      items: [
        {
          title: 'nav.link.settingsSection',
          icon: Settings,
          items: [
            {
              title: 'nav.link.account',
              url: '/settings/account',
              icon: Wrench,
            },
          ],
        },
      ],
    },
  ],
}
