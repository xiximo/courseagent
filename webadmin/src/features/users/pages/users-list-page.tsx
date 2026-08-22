import { useEffect, useMemo, useState } from 'react'
import { Copy, KeyRound, Plus, Power, Trash2 } from 'lucide-react'
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
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import type { UserAccount } from '../data/types'
import { TEST_USER_PASSWORD } from '../data/types'
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

function personaLabel(user: UserAccount) {
  if (user.profile.personaLabel) return user.profile.personaLabel
  if (user.roleCodes.some((code) => code.toLowerCase().includes('admin'))) {
    return '管理员'
  }
  return '未设置画像'
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

  const personaCount = useMemo(
    () => users.filter((user) => user.isSeed || user.profile.persona).length,
    [users]
  )

  const copyText = async (text: string, ok: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(ok)
    } catch {
      toast.error('复制失败')
    }
  }

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
              管理登录账号与赛题测试画像。预置用户密码均为{' '}
              <code className='rounded bg-muted px-1 py-0.5 text-xs'>
                {TEST_USER_PASSWORD}
              </code>
              ，可直接登录对话。
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

        <div className='grid gap-4 sm:grid-cols-3'>
          <Card>
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium'>账号总数</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{users.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium'>画像用户</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{personaCount}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className='pb-2'>
              <CardTitle className='text-sm font-medium'>测试口令</CardTitle>
            </CardHeader>
            <CardContent>
              <div className='text-2xl font-bold'>{TEST_USER_PASSWORD}</div>
            </CardContent>
          </Card>
        </div>

        {loading ? (
          <p className='text-sm text-muted-foreground'>加载中…</p>
        ) : users.length === 0 ? (
          <p className='text-sm text-muted-foreground'>暂无用户</p>
        ) : (
          <div className='grid gap-4 lg:grid-cols-2'>
            {users.map((user) => (
              <Card key={user.id}>
                <CardHeader className='space-y-3'>
                  <div className='flex flex-wrap items-start justify-between gap-2'>
                    <div>
                      <CardTitle className='text-lg'>{user.fullName}</CardTitle>
                      <CardDescription className='mt-1 font-mono'>
                        {user.username}
                      </CardDescription>
                    </div>
                    <div className='flex flex-wrap gap-1'>
                      <Badge variant='secondary'>{personaLabel(user)}</Badge>
                      <Badge
                        variant={
                          user.status === 'enabled' ? 'default' : 'outline'
                        }
                      >
                        {statusLabel(user.status)}
                      </Badge>
                      {user.isSeed ? <Badge variant='outline'>预置</Badge> : null}
                    </div>
                  </div>
                  {user.profile.summary ? (
                    <p className='text-sm text-muted-foreground'>
                      {user.profile.summary}
                    </p>
                  ) : null}
                </CardHeader>
                <CardContent className='space-y-4'>
                  {user.profile.goals.length > 0 ? (
                    <div className='text-sm'>
                      <div className='mb-1 font-medium'>目标</div>
                      <p className='text-muted-foreground'>
                        {user.profile.goals.join(' · ')}
                      </p>
                    </div>
                  ) : null}
                  {user.profile.constraints.length > 0 ? (
                    <div className='text-sm'>
                      <div className='mb-1 font-medium'>约束</div>
                      <p className='text-muted-foreground'>
                        {user.profile.constraints.join(' · ')}
                      </p>
                    </div>
                  ) : null}
                  {(user.profile.conditions ?? []).length > 0 ? (
                    <div className='text-sm'>
                      <div className='mb-1 font-medium'>健康状况</div>
                      <p className='text-muted-foreground'>
                        {user.profile.conditions?.join(' · ')}
                      </p>
                    </div>
                  ) : null}
                  {(user.profile.allergies ?? []).length > 0 ? (
                    <div className='text-sm'>
                      <div className='mb-1 font-medium'>过敏</div>
                      <p className='text-muted-foreground'>
                        {user.profile.allergies?.join(' · ')}
                      </p>
                    </div>
                  ) : null}
                  {user.profile.sampleQuestions.length > 0 ? (
                    <div className='space-y-2'>
                      <div className='text-sm font-medium'>推荐提问</div>
                      <div className='flex flex-col gap-2'>
                        {user.profile.sampleQuestions.map((question) => (
                          <button
                            key={question}
                            type='button'
                            className='flex items-start justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm hover:bg-muted/50'
                            onClick={() =>
                              copyText(question, '已复制提问，可粘贴到对话')
                            }
                          >
                            <span>{question}</span>
                            <Copy className='mt-0.5 size-3.5 shrink-0 text-muted-foreground' />
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className='flex flex-wrap gap-2'>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      disabled={!isAdmin || busyId === user.id}
                      onClick={() =>
                        copyText(
                          `${user.username} / ${TEST_USER_PASSWORD}`,
                          '已复制账号口令'
                        )
                      }
                    >
                      复制账号
                    </Button>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      disabled={!isAdmin || busyId === user.id}
                      onClick={() => handleResetPassword(user)}
                    >
                      <KeyRound className='mr-1 size-3.5' />
                      重置密码
                    </Button>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      disabled={!isAdmin || busyId === user.id}
                      onClick={() => handleToggleStatus(user)}
                    >
                      <Power className='mr-1 size-3.5' />
                      {user.status === 'enabled' ? '停用' : '启用'}
                    </Button>
                    <Button
                      type='button'
                      size='sm'
                      variant='outline'
                      disabled={!isAdmin || busyId === user.id}
                      onClick={() => setDeleteTarget(user)}
                    >
                      <Trash2 className='mr-1 size-3.5' />
                      删除
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
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
