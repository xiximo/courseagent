import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentKnowledgeDetailPage } from '@/features/course-agent/pages/agent-knowledge-detail-page'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/knowledge/$kbId')({
  beforeLoad: ({ params }) => {
    redirectIfPlatform('/saasadmin/knowledge/$kbId', { kbId: params.kbId })
    appRouteGuard('/admin/knowledge')
  },
  component: function KnowledgeDetailRoute() {
    const { kbId } = Route.useParams()
    return (
      <KnowledgePageShell
        title='知识库'
        description='维护本机构知识库文档，不会同步到其他机构。'
      >
        <AgentKnowledgeDetailPage kbId={kbId} />
      </KnowledgePageShell>
    )
  },
})
