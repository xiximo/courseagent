import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentKnowledgeDetailPage } from '@/features/course-agent/pages/agent-knowledge-detail-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/knowledge/$kbId')({
  beforeLoad: () => {
    appRouteGuard('/admin/knowledge')
  },
  component: function KnowledgeDetailRoute() {
    const { kbId } = Route.useParams()
    return (
      <KnowledgePageShell>
        <AgentKnowledgeDetailPage kbId={kbId} />
      </KnowledgePageShell>
    )
  },
})
