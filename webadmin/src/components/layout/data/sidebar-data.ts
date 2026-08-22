import {
  ClipboardList,
  Database,
  GraduationCap,
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
      name: '企业智能体平台',
      logo: GraduationCap,
      plan: '',
    },
  ],
  navGroups: [
    {
      title: 'nav.group.courseAgent',
      items: [
        {
          title: 'nav.link.courseAgents',
          url: '/admin/course-agents',
          icon: GraduationCap,
          requiredPermissions: ['course_agent_config'],
        },
        {
          title: 'nav.link.agentLeads',
          url: '/admin/course-agents/leads',
          icon: Users,
          requiredPermissions: ['course_agent_config'],
        },
        {
          title: 'nav.link.agentModel',
          url: '/admin/models',
          icon: SlidersHorizontal,
          requiredPermissions: ['course_agent_config'],
        },
        {
          title: 'nav.link.agentKnowledge',
          url: '/admin/knowledge',
          icon: Database,
          requiredPermissions: ['course_agent_config'],
        },
      ],
    },
    {
      title: 'nav.group.administration',
      items: [
        {
          title: 'nav.link.userManagement',
          url: '/users',
          icon: UserCog,
          requiredPermissions: ['user_manage'],
        },
        {
          title: 'nav.link.auditManagement',
          url: '/audit',
          icon: ClipboardList,
          requiredPermissions: ['user_manage'],
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
