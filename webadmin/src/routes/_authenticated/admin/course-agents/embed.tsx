import { createFileRoute } from '@tanstack/react-router'
import { AgentEmbedPage } from '@/features/course-agent/pages/agent-embed-page'
import { PlatformAgentPageShell } from '@/features/course-agent/components/platform-agent-page-shell'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/course-agents/embed')({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentEmbedRoute() {
    return (
      <PlatformAgentPageShell>
        <AgentEmbedPage />
      </PlatformAgentPageShell>
    )
  },
})
