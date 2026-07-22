import { createFileRoute } from '@tanstack/react-router'
import { AgentStateMachinePage } from '@/features/course-agent/pages/agent-state-machine-page'
import { PlatformAgentPageShell } from '@/features/course-agent/components/platform-agent-page-shell'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute(
  '/_authenticated/admin/course-agents/state-machine'
)({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentStateMachineRoute() {
    return (
      <PlatformAgentPageShell>
        <AgentStateMachinePage />
      </PlatformAgentPageShell>
    )
  },
})
