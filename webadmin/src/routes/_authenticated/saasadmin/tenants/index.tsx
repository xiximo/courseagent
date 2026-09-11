import { createFileRoute } from '@tanstack/react-router'
import { PlatformTenantsPage } from '@/features/platform/pages/platform-tenants-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/tenants/')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin/tenants')
  },
  component: PlatformTenantsPage,
})
