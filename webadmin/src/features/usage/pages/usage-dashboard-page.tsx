import { useEffect, useState } from 'react'
import { MessageSquare, Sparkles, Users, Wallet } from 'lucide-react'
import { ApiClientError } from '@/lib/api/client'
import { getAdminUsageStats, type AdminUsageStats } from '@/lib/api/billing'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { UsageTopUsersChart, UsageTrendChart } from '../components/usage-charts'

export function UsageDashboardPage({
  title = '用量统计',
  description = '对话次数、活跃用户、近 30 日趋势与成员对话排行。',
}: {
  title?: string
  description?: string
}) {
  const [stats, setStats] = useState<AdminUsageStats | null>(null)
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setError(undefined)
      try {
        const data = await getAdminUsageStats(30)
        if (!cancelled) setStats(data)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiClientError ? e.message : '加载用量失败')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-6'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>{title}</h1>
          <p className='text-muted-foreground mt-1'>{description}</p>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}
        {loading ? <p className='text-muted-foreground'>加载中…</p> : null}

        {stats ? (
          <>
            <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
              <StatCard
                title='总对话次数'
                value={stats.totalChats}
                hint='累计用户提问'
                icon={MessageSquare}
              />
              <StatCard
                title='近 30 日活跃用户'
                value={stats.activeUsers}
                hint='有过对话的成员'
                icon={Users}
              />
              <StatCard
                title='免费版机构'
                value={stats.freeUsers}
                hint='当前免费套餐'
                icon={Wallet}
              />
              <StatCard
                title='专业版机构'
                value={stats.proUsers}
                hint='已升级专业版'
                icon={Sparkles}
              />
            </div>
            <Card>
              <CardHeader className='pb-2'>
                <CardTitle>近 30 日对话趋势</CardTitle>
                <CardDescription>按天统计提问次数与活跃成员</CardDescription>
              </CardHeader>
              <CardContent>
                <UsageTrendChart data={stats.trend} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className='pb-2'>
                <CardTitle>成员对话 TOP 10</CardTitle>
                <CardDescription>对话次数最多的 10 位成员</CardDescription>
              </CardHeader>
              <CardContent>
                <UsageTopUsersChart data={stats.topUsers ?? []} />
              </CardContent>
            </Card>
          </>
        ) : null}
      </Main>
    </>
  )
}

function StatCard({
  title,
  value,
  hint,
  icon: Icon,
}: {
  title: string
  value: number
  hint: string
  icon: typeof MessageSquare
}) {
  return (
    <Card>
      <CardHeader className='flex flex-row items-start justify-between space-y-0 pb-2'>
        <CardTitle className='text-muted-foreground text-sm font-medium'>
          {title}
        </CardTitle>
        <Icon className='text-muted-foreground size-4' />
      </CardHeader>
      <CardContent>
        <div className='text-3xl font-semibold tracking-tight'>{value}</div>
        <p className='text-muted-foreground mt-1 text-xs'>{hint}</p>
      </CardContent>
    </Card>
  )
}
