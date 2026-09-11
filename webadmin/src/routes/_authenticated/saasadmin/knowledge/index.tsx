import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentKnowledgePage } from '@/features/course-agent/pages/agent-knowledge-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/knowledge/')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin/knowledge')
  },
  component: function PlatformKnowledgeListRoute() {
    return (
      <KnowledgePageShell
        title='共享知识库'
        description='平台模板知识库。各机构有自己的资料库，不会与这里混用。'
      >
        <AgentKnowledgePage />
      </KnowledgePageShell>
    )
  },
})
