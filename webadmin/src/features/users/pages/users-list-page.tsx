import { useEffect, useMemo, useState } from 'react'
import { KeyRound, Plus, Power, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  deleteUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from '@/lib/api/users'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Main } from '@/components/layout/main'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import type { UserAccount } from '../data/types'
import { CreateUserDialog } from '../components/create-user-dialog'

function statusLabel(status: UserAccount['status']) {
  switch (status) {
    case 'enabled':
      return '启用'
    case 'disabled':
      return '停用'
    case 'locked':
      return '锁定'
    case 'terminated':
      return '已注销'
  }
}

function roleLabel(codes: string[]) {
  const set = new Set(codes.map((code) => code.toLowerCase()))
  if (
    set.has('sys_admin') ||
    set.has('system_admin') ||
    set.has('admin')
  ) {
    return '平台管理员'
  }
  if (set.has('org_admin')) return '机构管理员'
  return '成员'
}

function isOrgAdmin(codes: string[]) {
  return codes.some((code) => code.toLowerCase() === 'org_admin')
}

function TenantCell({ user }: { user: UserAccount }) {
  const name = user.tenantName?.trim()
  if (name) {
    return <div className='font-medium'>{name}</div>
  }
  if (user.tenantId) {
    return <div className='font-medium'>未知机构</div>
  }
  if (isOrgAdmin(user.roleCodes)) {
    return (
      <>
        <div className='font-medium'>机构账号</div>
        <div className='text-muted-foreground text-xs'>未关联租户</div>
      </>
    )
  }
  return (
    <>
      <div className='font-medium'>平台</div>
      <div className='text-muted-foreground text-xs'>不属于机构</div>
    </>
  )
}

function formatTime(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function UsersListPage() {
  const { isAdmin } = useAppPermissions()
  const [users, setUsers] = useState<UserAccount[]>([])
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<UserAccount | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const loadUsers = async () => {
    setLoading(true)
    setError(undefined)
    try {
      setUsers(await listUsers())
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadUsers()
  }, [])

  const tenantCount = useMemo(
    () => new Set(users.map((user) => user.tenantId).filter(Boolean)).size,
    [users]
  )

  const handleToggleStatus = async (user: UserAccount) => {
    setBusyId(user.id)
    try {
      const next = user.status === 'enabled' ? 'disabled' : 'enabled'
      await updateUser(user.id, { status: next })
      toast.success(next === 'enabled' ? '已启用' : '已停用')
      await loadUsers()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '更新失败')
    } finally {
      setBusyId(null)
    }
  }

  const handleResetPassword = async (user: UserAccount) => {
    setBusyId(user.id)
    try {
      const result = await resetUserPassword(user.id)
      toast.success(`${user.username} 密码已重置为 ${result.password}`)
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '重置失败')
    } finally {
      setBusyId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setBusyId(deleteTarget.id)
    try {
      await deleteUser(deleteTarget.id)
      toast.success('用户已删除')
      setDeleteTarget(null)
      await loadUsers()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '删除失败')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>用户管理</h2>
            <p className='text-muted-foreground'>
              平台账号与各机构成员。共 {users.length} 人
              {tenantCount > 0 ? `，覆盖 ${tenantCount} 个机构` : ''}。
            </p>
          </div>
          <Button
            type='button'
            disabled={!isAdmin}
            onClick={() => setCreateOpen(true)}
          >
            <Plus className='mr-1 size-4' />
            添加用户
          </Button>
        </div>

        {error ? <AppErrorAlert message={error} /> : null}

        {loading ? (
          <p className='text-muted-foreground text-sm'>加载中…</p>
        ) : users.length === 0 ? (
          <p className='text-muted-foreground text-sm'>暂无用户</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户</TableHead>
                <TableHead>所属机构</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>最近登录</TableHead>
                <TableHead className='text-right'>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className='font-medium'>{user.fullName}</div>
                    <div className='text-muted-foreground font-mono text-xs'>
                      {user.username}
                    </div>
                  </TableCell>
                  <TableCell>
                    <TenantCell user={user} />
                  </TableCell>
                  <TableCell>
                    <div className='flex flex-wrap gap-1'>
                      <Badge variant='secondary'>{roleLabel(user.roleCodes)}</Badge>
                      {user.isSeed ? (
                        <Badge variant='outline'>预置</Badge>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={user.status === 'enabled' ? 'default' : 'outline'}
                    >
                      {statusLabel(user.status)}
                    </Badge>
                  </TableCell>
                  <TableCell className='text-muted-foreground text-sm'>
                    {formatTime(user.lastLoginAt)}
                  </TableCell>
                  <TableCell className='text-right'>
                    <div className='flex justify-end gap-2'>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        disabled={!isAdmin || busyId === user.id}
                        onClick={() => void handleResetPassword(user)}
                      >
                        <KeyRound className='mr-1 size-3.5' />
                        重置密码
                      </Button>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        disabled={!isAdmin || busyId === user.id}
                        onClick={() => void handleToggleStatus(user)}
                      >
                        <Power className='mr-1 size-3.5' />
                        {user.status === 'enabled' ? '停用' : '启用'}
                      </Button>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        className='text-destructive hover:text-destructive'
                        disabled={!isAdmin || busyId === user.id}
                        onClick={() => setDeleteTarget(user)}
                      >
                        <Trash2 className='mr-1 size-3.5' />
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

      <CreateUserDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => void loadUsers()}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title='删除用户'
        desc={
          deleteTarget
            ? `确定删除用户 ${deleteTarget.username} 吗？此操作无法撤销。`
            : ''
        }
        confirmText='删除'
        destructive
        isLoading={Boolean(deleteTarget && busyId === deleteTarget.id)}
        handleConfirm={handleDelete}
      />
    </>
  )
}
