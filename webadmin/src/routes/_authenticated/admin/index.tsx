import { createFileRoute } from '@tanstack/react-router'
import { OrgWorkspacePage } from '@/features/org/pages/org-workspace-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/')({
  beforeLoad: () => {
    appRouteGuard('/admin')
  },
  component: OrgWorkspacePage,
})
