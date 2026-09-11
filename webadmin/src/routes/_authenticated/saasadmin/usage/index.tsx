import { createFileRoute } from '@tanstack/react-router'
import { UsageDashboardPage } from '@/features/usage/pages/usage-dashboard-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/saasadmin/usage/')({
  beforeLoad: () => {
    appRouteGuard('/saasadmin/usage')
  },
  component: function PlatformUsageRoute() {
    return (
      <UsageDashboardPage
        title='全平台用量'
        description='全部机构的对话次数、活跃用户、近 30 日趋势与成员对话排行。'
      />
    )
  },
})
