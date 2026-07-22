import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentKnowledgePage } from '@/features/course-agent/pages/agent-knowledge-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/knowledge/')({
  beforeLoad: () => {
    appRouteGuard('/admin/knowledge')
  },
  component: function KnowledgeListRoute() {
    return (
      <KnowledgePageShell>
        <AgentKnowledgePage />
      </KnowledgePageShell>
    )
  },
})
