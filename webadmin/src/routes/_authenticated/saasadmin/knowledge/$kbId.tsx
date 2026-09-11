import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentKnowledgeDetailPage } from '@/features/course-agent/pages/agent-knowledge-detail-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/knowledge/$kbId')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin/knowledge')
  },
  component: function PlatformKnowledgeDetailRoute() {
    const { kbId } = Route.useParams()
    return (
      <KnowledgePageShell
        title='共享知识库'
        description='平台模板资料。机构知识库相互隔离，互不影响。'
      >
        <AgentKnowledgeDetailPage kbId={kbId} />
      </KnowledgePageShell>
    )
  },
})
