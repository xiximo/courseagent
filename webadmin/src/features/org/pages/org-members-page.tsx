import { useEffect, useState } from 'react'
import { Copy, Plus, Users } from 'lucide-react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import {
  getOrgWorkspace,
  listOrgMembers,
  type OrgMember,
  type OrgWorkspace,
} from '@/lib/api/org'
import { AppErrorAlert } from '@/components/app-error-alert'
import { AppPageHeader } from '@/components/app-page-header'
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
import { CreateOrgMemberDialog } from '../components/create-org-member-dialog'

function roleLabel(codes: string[]) {
  const set = new Set(codes.map((code) => code.toLowerCase()))
  if (set.has('org_admin')) return '机构管理员'
  return '成员'
}

function formatTime(value: string | null) {
  if (!value) return '尚未登录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function OrgMembersPage() {
  const [members, setMembers] = useState<OrgMember[]>([])
  const [workspace, setWorkspace] = useState<OrgWorkspace | null>(null)
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(undefined)
    try {
      const [nextMembers, nextWorkspace] = await Promise.all([
        listOrgMembers(),
        getOrgWorkspace(),
      ])
      setMembers(nextMembers)
      setWorkspace(nextWorkspace)
    } catch (e) {
      setError(e instanceof ApiClientError ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const joinUrl = workspace
    ? `${window.location.origin}${workspace.joinPath}`
    : ''

  const copyJoinLink = async () => {
    if (!joinUrl) return
    try {
      await navigator.clipboard.writeText(joinUrl)
      toast.success('邀请链接已复制')
    } catch {
      toast.error('复制失败，请手动复制地址栏链接')
    }
  }

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>成员</h2>
            <p className='text-muted-foreground'>
              教师、咨询顾问或家长通过邀请链接注册后，即可使用本机构顾问。
            </p>
          </div>
          <div className='flex flex-wrap gap-2'>
            <Button
              type='button'
              variant='outline'
              disabled={!joinUrl}
              onClick={() => void copyJoinLink()}
            >
              <Copy className='mr-1 size-4' />
              复制邀请链接
            </Button>
            <Button type='button' onClick={() => setCreateOpen(true)}>
              <Plus className='mr-1 size-4' />
              添加成员
            </Button>
          </div>
        </div>

        {workspace ? (
          <p className='text-muted-foreground flex items-center gap-2 text-sm'>
            <Users className='size-4' />
            {workspace.tenantName} · {workspace.userCount} 人 · {joinUrl}
          </p>
        ) : null}

        {error ? <AppErrorAlert message={error} /> : null}

        {loading ? (
          <p className='text-muted-foreground text-sm'>加载中…</p>
        ) : members.length === 0 ? (
          <p className='text-muted-foreground text-sm'>暂无成员</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>最近登录</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>
                    <div className='font-medium'>{member.fullName}</div>
                    <div className='text-muted-foreground font-mono text-xs'>
                      {member.username}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant='secondary'>{roleLabel(member.roleCodes)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={member.status === 'enabled' ? 'default' : 'outline'}
                    >
                      {member.status === 'enabled' ? '启用' : '停用'}
                    </Badge>
                  </TableCell>
                  <TableCell className='text-muted-foreground text-sm'>
                    {formatTime(member.lastLoginAt)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Main>

      <CreateOrgMemberDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => void load()}
      />
    </>
  )
}
