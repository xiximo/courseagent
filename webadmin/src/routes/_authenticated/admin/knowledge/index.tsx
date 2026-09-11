import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentKnowledgePage } from '@/features/course-agent/pages/agent-knowledge-page'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/knowledge/')({
  beforeLoad: () => {
    redirectIfPlatform('/saasadmin/knowledge')
    appRouteGuard('/admin/knowledge')
  },
  component: function KnowledgeListRoute() {
    return (
      <KnowledgePageShell
        title='知识库'
        description='上传本机构的课程资料，仅本机构顾问可检索。'
      >
        <AgentKnowledgePage />
      </KnowledgePageShell>
    )
  },
})
