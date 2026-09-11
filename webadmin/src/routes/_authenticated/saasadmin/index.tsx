import { createFileRoute } from '@tanstack/react-router'
import { PlatformConsolePage } from '@/features/platform/pages/platform-console-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin')
  },
  component: PlatformConsolePage,
})
