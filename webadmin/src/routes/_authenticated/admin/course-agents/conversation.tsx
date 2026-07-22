import { createFileRoute } from '@tanstack/react-router'
import { AgentConversationPage } from '@/features/course-agent/pages/agent-conversation-page'
import { PlatformAgentPageShell } from '@/features/course-agent/components/platform-agent-page-shell'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute(
  '/_authenticated/admin/course-agents/conversation'
)({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentConversationRoute() {
    return (
      <PlatformAgentPageShell>
        <AgentConversationPage />
      </PlatformAgentPageShell>
    )
  },
})
