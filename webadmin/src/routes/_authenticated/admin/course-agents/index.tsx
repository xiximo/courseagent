import { createFileRoute } from '@tanstack/react-router'
import { CourseAgentsListPage } from '@/features/course-agent'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/course-agents/')({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: CourseAgentsListPage,
})
