import { createFileRoute } from '@tanstack/react-router'
import { AgentLeadDetailPage } from '@/features/course-agent/pages/agent-lead-detail-page'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute(
  '/_authenticated/admin/course-agents/leads/$leadId'
)({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentLeadDetailRoute() {
    const { leadId } = Route.useParams()
    return (
      <>
        <AppPageHeader />
        <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
          <AgentLeadDetailPage leadId={leadId} />
        </Main>
      </>
    )
  },
})
