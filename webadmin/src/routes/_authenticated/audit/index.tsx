import { createFileRoute } from '@tanstack/react-router'
import { LoginAuditPage } from '@/features/audit/pages/login-audit-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/audit/')({
  beforeLoad: () => {
    appRouteGuard('/audit')
  },
  component: LoginAuditPage,
})
