import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ApiClientError } from '@/lib/api/client'
import { getAdminUsageStats, type AdminUsageStats } from '@/lib/api/billing'
import { listPlatformTenants, type TenantSummary } from '@/lib/api/tenants'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

export function PlatformConsolePage() {
  const [tenants, setTenants] = useState<TenantSummary[]>([])
  const [stats, setStats] = useState<AdminUsageStats | null>(null)
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setError(undefined)
      try {
        const [tenantRows, usage] = await Promise.all([
          listPlatformTenants(),
          getAdminUsageStats(30),
        ])
        if (cancelled) return
        setTenants(tenantRows)
        setStats(usage)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiClientError ? e.message : '加载平台数据失败')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const recent = useMemo(() => {
    const cutoff = Date.now() - WEEK_MS
    return tenants
      .filter((row) => {
        const time = new Date(row.createdAt).getTime()
        return Number.isFinite(time) && time >= cutoff
      })
      .slice(0, 5)
  }, [tenants])

  const proTenants = tenants.filter((row) => row.planCode === 'pro').length

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-6'>
        <div>
          <p className='text-muted-foreground text-sm'>平台运营</p>
          <h1 className='mt-1 text-2xl font-bold tracking-tight'>总览</h1>
          <p className='text-muted-foreground mt-1'>
            看谁开通了、用得怎么样、产品能力是否就绪。
          </p>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        <div className='grid gap-4 sm:grid-cols-2 xl:grid-cols-4'>
          <StatCard title='已开通机构' value={tenants.length} loading={loading} />
          <StatCard
            title='专业版机构'
            value={loading ? undefined : proTenants}
            loading={loading}
          />
          <StatCard title='总对话次数' value={stats?.totalChats} loading={loading} />
          <StatCard
            title='近 30 日活跃用户'
            value={stats?.activeUsers}
            loading={loading}
          />
        </div>

        <div className='flex flex-wrap gap-2'>
          <Button asChild>
            <Link to='/saasadmin/tenants'>查看机构</Link>
          </Button>
          <Button asChild variant='outline'>
            <Link to='/saasadmin/usage'>全平台用量</Link>
          </Button>
          <Button asChild variant='outline'>
            <Link to='/saasadmin/agents'>顾问配置</Link>
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>近 7 日新开通</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className='text-muted-foreground text-sm'>加载中…</p>
            ) : recent.length === 0 ? (
              <p className='text-muted-foreground text-sm'>
                近 7 日没有新机构。完整列表在「机构」。
              </p>
            ) : (
              <ul className='space-y-3'>
                {recent.map((row) => (
                  <li
                    key={row.id}
                    className='flex flex-wrap items-center justify-between gap-2 text-sm'
                  >
                    <div>
                      <div className='font-medium'>{row.name}</div>
                      <div className='text-muted-foreground text-xs'>
                        {row.ownerUsername || '—'} · {formatTime(row.createdAt)}
                      </div>
                    </div>
                    <Badge variant={row.planCode === 'pro' ? 'default' : 'secondary'}>
                      {row.planCode === 'pro' ? '专业版' : '免费版'}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </Main>
    </>
  )
}

function StatCard({
  title,
  value,
  loading,
}: {
  title: string
  value?: number
  loading: boolean
}) {
  return (
    <Card>
      <CardHeader className='pb-2'>
        <CardTitle className='text-muted-foreground text-sm font-medium'>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className='text-2xl font-semibold'>
        {loading || value == null ? '—' : value}
      </CardContent>
    </Card>
  )
}

function formatTime(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
