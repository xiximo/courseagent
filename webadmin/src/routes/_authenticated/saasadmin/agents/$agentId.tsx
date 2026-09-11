import { createFileRoute } from '@tanstack/react-router'
import { AgentConfigPage } from '@/features/course-agent/pages/agent-config-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/agents/$agentId')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin/agents')
  },
  component: function PlatformAgentConfigRoute() {
    const { agentId } = Route.useParams()
    return <AgentConfigPage agentId={agentId} />
  },
})
