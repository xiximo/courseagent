import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deletePlatformTenant,
  listPlatformTenants,
  updatePlatformTenantPlan,
  type TenantSummary,
} from '@/lib/api/tenants'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Main } from '@/components/layout/main'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function PlatformTenantsPage() {
  const [tenants, setTenants] = useState<TenantSummary[]>([])
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<TenantSummary | null>(null)
  const [planTarget, setPlanTarget] = useState<TenantSummary | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<TenantSummary | null>(null)
  const [updating, setUpdating] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setTenants(await listPlatformTenants())
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载机构失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const applyTenant = (row: TenantSummary) => {
    setTenants((prev) => prev.map((item) => (item.id === row.id ? row : item)))
    setSelected((current) => (current?.id === row.id ? row : current))
  }

  const handleChangePlan = async () => {
    if (!planTarget) return
    const nextPlan = planTarget.planCode === 'pro' ? 'free' : 'pro'
    setUpdating(true)
    try {
      const updated = await updatePlatformTenantPlan(planTarget.id, nextPlan)
      applyTenant(updated)
      toast.success(
        nextPlan === 'free'
          ? `「${updated.name}」已降为免费版`
          : `「${updated.name}」已升级为专业版`
      )
      setPlanTarget(null)
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '套餐更新失败')
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const result = await deletePlatformTenant(deleteTarget.id)
      setTenants((prev) => prev.filter((item) => item.id !== deleteTarget.id))
      if (selected?.id === deleteTarget.id) setSelected(null)
      toast.success(result.message || '机构已删除')
      setDeleteTarget(null)
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-6'>
        <div>
          <p className='text-muted-foreground text-sm'>平台运营</p>
          <h1 className='mt-1 text-2xl font-bold tracking-tight'>机构</h1>
          <p className='text-muted-foreground mt-1'>
            管理已开通的机构空间，可升级、降级套餐或删除租户。
          </p>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        {loading ? (
          <p className='text-muted-foreground text-sm'>加载中…</p>
        ) : tenants.length === 0 ? (
          <p className='text-muted-foreground text-sm'>
            还没有机构注册。落地页「开通机构空间」会创建第一条租户。
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>机构</TableHead>
                <TableHead>管理员</TableHead>
                <TableHead>套餐</TableHead>
                <TableHead>成员</TableHead>
                <TableHead>开通时间</TableHead>
                <TableHead className='text-right'>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.map((row) => (
                <TableRow
                  key={row.id}
                  className='cursor-pointer'
                  onClick={() => setSelected(row)}
                >
                  <TableCell>
                    <div className='font-medium'>{row.name}</div>
                    <div className='text-muted-foreground text-xs'>{row.slug}</div>
                  </TableCell>
                  <TableCell>{row.ownerUsername || '—'}</TableCell>
                  <TableCell>
                    <Badge variant={row.planCode === 'pro' ? 'default' : 'secondary'}>
                      {row.planCode === 'pro' ? '专业版' : '免费版'}
                    </Badge>
                  </TableCell>
                  <TableCell>{row.userCount}</TableCell>
                  <TableCell className='text-muted-foreground'>
                    {formatTime(row.createdAt)}
                  </TableCell>
                  <TableCell className='text-right'>
                    <div
                      className='flex justify-end gap-2'
                      onClick={(event) => event.stopPropagation()}
                    >
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        onClick={() => setPlanTarget(row)}
                      >
                        {row.planCode === 'pro' ? '降为免费版' : '升为专业版'}
                      </Button>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        className='text-destructive hover:text-destructive'
                        onClick={() => setDeleteTarget(row)}
                      >
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Main>

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{selected?.name ?? '机构详情'}</SheetTitle>
            <SheetDescription>
              套餐改的是租户本身。降级后该机构立即按免费版限额执行。
            </SheetDescription>
          </SheetHeader>
          {selected ? (
            <div className='mt-6 space-y-6'>
              <dl className='space-y-3 text-sm'>
                <Detail label='标识' value={selected.slug} />
                <Detail label='管理员' value={selected.ownerUsername || '—'} />
                <Detail
                  label='套餐'
                  value={selected.planCode === 'pro' ? '专业版' : '免费版'}
                />
                <Detail label='成员数' value={String(selected.userCount)} />
                <Detail label='开通时间' value={formatTime(selected.createdAt)} />
              </dl>
              <div className='flex flex-wrap gap-2'>
                <Button
                  type='button'
                  variant='outline'
                  onClick={() => setPlanTarget(selected)}
                >
                  {selected.planCode === 'pro' ? '降为免费版' : '升为专业版'}
                </Button>
                <Button
                  type='button'
                  variant='destructive'
                  onClick={() => setDeleteTarget(selected)}
                >
                  删除机构
                </Button>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={planTarget !== null}
        onOpenChange={(open) => {
          if (!open && !updating) setPlanTarget(null)
        }}
        title={planTarget?.planCode === 'pro' ? '降为免费版' : '升为专业版'}
        desc={
          planTarget ? (
            planTarget.planCode === 'pro' ? (
              <>
                确定将「{planTarget.name}」降为免费版吗？该机构将立即只能使用基础型
                Agent、1 个知识库，并恢复每月 50 次对话限额。
              </>
            ) : (
              <>
                确定将「{planTarget.name}」升为专业版吗？将立即解锁 Harness Agent
                与不限数量知识库。
              </>
            )
          ) : (
            ''
          )
        }
        cancelBtnText='取消'
        confirmText={planTarget?.planCode === 'pro' ? '确认降级' : '确认升级'}
        isLoading={updating}
        handleConfirm={() => void handleChangePlan()}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
        title='删除机构'
        desc={
          deleteTarget ? (
            <>
              确定删除「{deleteTarget.name}」吗？将同时删除其成员账号、顾问、知识库与会话，且不可恢复。
            </>
          ) : (
            ''
          )
        }
        cancelBtnText='取消'
        confirmText='删除'
        destructive
        isLoading={deleting}
        handleConfirm={() => void handleDelete()}
      />
    </>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className='text-muted-foreground'>{label}</dt>
      <dd className='mt-0.5 font-medium'>{value}</dd>
    </div>
  )
}

function formatTime(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
