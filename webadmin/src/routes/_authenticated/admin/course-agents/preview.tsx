import { createFileRoute, redirect } from '@tanstack/react-router'
import { listCourseAgents } from '@/lib/api/course-agent'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/course-agents/preview')({
  beforeLoad: async () => {
    appRouteGuard('/admin/course-agents')
    const agents = await listCourseAgents()
    const defaultAgent =
      agents.find((a) => a.isDefault) ?? agents[0] ?? null
    if (!defaultAgent) {
      throw redirect({ to: '/admin/course-agents' })
    }
    throw redirect({
      to: '/admin/course-agents/$agentId/preview',
      params: { agentId: defaultAgent.agentId },
    })
  },
})
