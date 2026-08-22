import { createFileRoute } from '@tanstack/react-router'
import { AdminAgentChatPage } from '@/features/course-agent/pages/admin-agent-chat-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/chat/$agentId')({
  beforeLoad: () => {
    appRouteGuard('/admin/chat')
  },
  component: function AdminAgentChatRoute() {
    const { agentId } = Route.useParams()
    return <AdminAgentChatPage agentId={agentId} />
  },
})
