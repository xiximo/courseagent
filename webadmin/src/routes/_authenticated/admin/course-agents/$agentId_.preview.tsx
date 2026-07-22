import { createFileRoute } from '@tanstack/react-router'
import { AgentStandalonePreviewPage } from '@/features/course-agent/pages/agent-standalone-preview-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

/**
 * 使用 `$agentId_.preview`：与配置页平级，避免嵌套在 `$agentId` 下被配置页吞掉。
 * 全路径仍为 `/admin/course-agents/$agentId/preview`。
 */
export const Route = createFileRoute(
  '/_authenticated/admin/course-agents/$agentId_/preview'
)({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentStandalonePreviewRoute() {
    const { agentId } = Route.useParams()
    return <AgentStandalonePreviewPage agentId={agentId} />
  },
})
