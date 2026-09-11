import { useState } from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import { createOrgMember } from '@/lib/api/org'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { TEST_USER_PASSWORD } from '@/features/users/data/types'

type CreateOrgMemberDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: () => void
}

export function CreateOrgMemberDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateOrgMemberDialogProps) {
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState(TEST_USER_PASSWORD)
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setUsername('')
    setFullName('')
    setPassword(TEST_USER_PASSWORD)
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) reset()
    onOpenChange(next)
  }

  const handleSubmit = async () => {
    const trimmedName = username.trim()
    const trimmedFullName = fullName.trim()
    if (trimmedName.length < 2) {
      toast.error('用户名至少 2 位')
      return
    }
    if (!trimmedFullName) {
      toast.error('请填写姓名')
      return
    }
    if (password.trim().length < 6) {
      toast.error('密码至少 6 位')
      return
    }
    setSubmitting(true)
    try {
      await createOrgMember({
        username: trimmedName,
        fullName: trimmedFullName,
        password: password.trim(),
      })
      toast.success('成员已创建，对方可用该账号登录')
      handleOpenChange(false)
      onCreated?.()
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.message : '创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className='max-w-lg'>
        <DialogHeader>
          <DialogTitle>添加成员</DialogTitle>
          <DialogDescription>
            成员属于本机构，登录后只能使用已发布的顾问，不能改配置。
          </DialogDescription>
        </DialogHeader>
        <div className='grid gap-4'>
          <div className='grid gap-2'>
            <Label htmlFor='org-member-username'>用户名</Label>
            <Input
              id='org-member-username'
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder='如：teacher01'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='org-member-fullname'>姓名</Label>
            <Input
              id='org-member-fullname'
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder='如：李老师'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='org-member-password'>初始密码</Label>
            <Input
              id='org-member-password'
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            type='button'
            variant='outline'
            onClick={() => handleOpenChange(false)}
          >
            取消
          </Button>
          <Button type='button' disabled={submitting} onClick={() => void handleSubmit()}>
            {submitting ? '创建中…' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
