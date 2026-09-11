import { createFileRoute } from '@tanstack/react-router'
import { LoginAuditPage } from '@/features/audit/pages/login-audit-page'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/audit/')({
  beforeLoad: () => {
    redirectIfPlatform('/saasadmin/audit')
    appRouteGuard('/audit')
  },
  component: LoginAuditPage,
})
