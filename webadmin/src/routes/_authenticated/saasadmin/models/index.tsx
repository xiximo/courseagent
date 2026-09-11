import { createFileRoute } from '@tanstack/react-router'
import { KnowledgePageShell } from '@/features/course-agent/components/knowledge-page-shell'
import { AgentModelPage } from '@/features/course-agent/pages/agent-model-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/models/')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin/models')
  },
  component: function PlatformModelsRoute() {
    return (
      <KnowledgePageShell
        title='模型'
        description='平台级模型路由，供全部机构的顾问使用。'
      >
        <AgentModelPage />
      </KnowledgePageShell>
    )
  },
})
