import { createFileRoute } from '@tanstack/react-router'
import { OrgMembersPage } from '@/features/org/pages/org-members-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/members/')({
  beforeLoad: () => {
    appRouteGuard('/admin/members')
  },
  component: OrgMembersPage,
})
