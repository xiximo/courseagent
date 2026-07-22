import { createFileRoute } from '@tanstack/react-router'
import { AgentLeadsPage } from '@/features/course-agent/pages/agent-leads-page'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute(
  '/_authenticated/admin/course-agents/leads/'
)({
  beforeLoad: () => {
    appRouteGuard('/admin/course-agents')
  },
  component: function AgentLeadsRoute() {
    return (
      <>
        <AppPageHeader />
        <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
          <AgentLeadsPage />
        </Main>
      </>
    )
  },
})
