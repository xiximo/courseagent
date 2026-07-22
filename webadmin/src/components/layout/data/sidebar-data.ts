import {
  Database,
  GraduationCap,
  MessageSquare,
  Settings,
  SlidersHorizontal,
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
      name: 'Agent',
      logo: GraduationCap,
      plan: 'Agent',
    },
  ],
  navGroups: [
    {
      title: 'nav.group.courseAgent',
      items: [
        {
          title: 'nav.link.agentPreview',
          url: '/admin/course-agents/preview',
          icon: MessageSquare,
          requiredPermissions: ['course_agent_view'],
        },
        {
          title: 'nav.link.courseAgents',
          url: '/admin/course-agents',
          icon: GraduationCap,
          requiredPermissions: ['course_agent_view'],
        },
        {
          title: 'nav.link.agentLeads',
          url: '/admin/course-agents/leads',
          icon: Users,
          requiredPermissions: ['course_agent_view'],
        },
        {
          title: 'nav.link.agentModel',
          url: '/admin/models',
          icon: SlidersHorizontal,
          requiredPermissions: ['course_agent_view'],
        },
        {
          title: 'nav.link.agentKnowledge',
          url: '/admin/knowledge',
          icon: Database,
          requiredPermissions: ['course_agent_view'],
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
