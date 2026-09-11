import { createFileRoute } from '@tanstack/react-router'
import { AgentConfigPage } from '@/features/course-agent/pages/agent-config-page'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute(
  '/_authenticated/admin/course-agents/$agentId'
)({
  beforeLoad: ({ params }) => {
    redirectIfPlatform('/saasadmin/agents/$agentId', { agentId: params.agentId })
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentConfigRoute() {
    const { agentId } = Route.useParams()
    return <AgentConfigPage agentId={agentId} />
  },
})
