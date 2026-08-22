import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { ApiClientError } from '@/lib/api/client'
import { listLoginAudits } from '@/lib/api/audit'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { LoginAuditLog } from '../data/types'

function formatLoginTime(iso: string) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return iso
  }
}

export function LoginAuditPage() {
  const [logs, setLogs] = useState<LoginAuditLog[]>([])
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)

  const loadLogs = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setLogs(await listLoginAudits())
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadLogs()
  }, [loadLogs])

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>日志审计</h2>
            <p className='text-muted-foreground'>
              仅记录用户登录账号、IP 地址与登录时间
            </p>
          </div>
          <Button
            type='button'
            variant='outline'
            disabled={loading}
            onClick={() => void loadLogs()}
          >
            <RefreshCw className='mr-1 size-4' />
            刷新
          </Button>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        {loading ? (
          <p className='text-sm text-muted-foreground'>加载中…</p>
        ) : logs.length === 0 ? (
          <p className='text-sm text-muted-foreground'>暂无登录记录</p>
        ) : (
          <div className='rounded-md border'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用户</TableHead>
                  <TableHead>账号</TableHead>
                  <TableHead>IP 地址</TableHead>
                  <TableHead>登录时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className='font-medium'>
                      {log.fullName || '—'}
                    </TableCell>
                    <TableCell className='font-mono text-sm'>
                      {log.username}
                    </TableCell>
                    <TableCell className='font-mono text-sm'>
                      {log.ipAddress || '未知'}
                    </TableCell>
                    <TableCell className='whitespace-nowrap text-sm'>
                      {formatLoginTime(log.loggedInAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Main>
    </>
  )
}
