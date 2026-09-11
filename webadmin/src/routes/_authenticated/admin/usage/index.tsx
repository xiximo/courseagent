import { createFileRoute } from '@tanstack/react-router'
import { UsageDashboardPage } from '@/features/usage/pages/usage-dashboard-page'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/admin/usage/')({
  beforeLoad: () => {
    redirectIfPlatform('/saasadmin/usage')
    appRouteGuard('/admin/usage')
  },
  component: function OrgUsageRoute() {
    return (
      <UsageDashboardPage
        title='用量统计'
        description='本机构对话次数、活跃用户、近 30 日趋势与成员对话排行。'
      />
    )
  },
})
