import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentModelPage } from '@/features/course-agent/pages/agent-model-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/models/')({
  beforeLoad: () => {
    appRouteGuard('/admin/models')
  },
  component: function ModelsRoute() {
    return (
      <KnowledgePageShell>
        <AgentModelPage />
      </KnowledgePageShell>
    )
  },
})
