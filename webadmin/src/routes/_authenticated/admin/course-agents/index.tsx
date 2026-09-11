import { createFileRoute } from '@tanstack/react-router'
import { CourseAgentsListPage } from '@/features/course-agent'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/course-agents/')({
  beforeLoad: () => {
    redirectIfPlatform('/saasadmin/agents')
    appRouteGuard('/admin/course-agents')
  },
  component: CourseAgentsListPage,
})
