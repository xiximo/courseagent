import { useState } from 'react'
import { toast } from 'sonner'
import { ApiClientError } from '@/lib/api/client'
import { createUser } from '@/lib/api/users'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { PERSONA_PRESETS } from '../data/persona-presets'
import { TEST_USER_PASSWORD } from '../data/types'
import type { UserPersonaProfile } from '../data/types'

type CreateUserDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: () => void
}

const defaultProfile = PERSONA_PRESETS[0].profile

export function CreateUserDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateUserDialogProps) {
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState(TEST_USER_PASSWORD)
  const [personaId, setPersonaId] = useState(PERSONA_PRESETS[0].id)
  const [summary, setSummary] = useState(defaultProfile.summary)
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setUsername('')
    setFullName('')
    setPassword(TEST_USER_PASSWORD)
    setPersonaId(PERSONA_PRESETS[0].id)
    setSummary(defaultProfile.summary)
  }

  const applyPersona = (id: string) => {
    setPersonaId(id)
    const preset = PERSONA_PRESETS.find((item) => item.id === id)
    if (preset) setSummary(preset.profile.summary)
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
    const preset =
      PERSONA_PRESETS.find((item) => item.id === personaId) ?? PERSONA_PRESETS[0]
    const profile: UserPersonaProfile = {
      ...preset.profile,
      summary: summary.trim() || preset.profile.summary,
    }
    setSubmitting(true)
    try {
      await createUser({
        username: trimmedName,
        password: password.trim(),
        fullName: trimmedFullName,
        roleCodes: ['end_user'],
        profile,
      })
      toast.success('用户已创建')
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
          <DialogTitle>添加用户</DialogTitle>
          <DialogDescription>
            选择画像后可直接用测试口令登录对话，验证减脂、增肌、调理或平台咨询路径。
          </DialogDescription>
        </DialogHeader>
        <div className='grid gap-4'>
          <div className='grid gap-2'>
            <Label htmlFor='user-username'>用户名</Label>
            <Input
              id='user-username'
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder='如：fatloss2'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='user-fullname'>姓名</Label>
            <Input
              id='user-fullname'
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder='如：林晓'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='user-password'>密码</Label>
            <Input
              id='user-password'
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div className='grid gap-2'>
            <Label>画像</Label>
            <Select value={personaId} onValueChange={applyPersona}>
              <SelectTrigger className='w-full'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERSONA_PRESETS.map((preset) => (
                  <SelectItem key={preset.id} value={preset.id}>
                    {preset.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='user-summary'>画像说明</Label>
            <Textarea
              id='user-summary'
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              rows={3}
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
          <Button type='button' disabled={submitting} onClick={handleSubmit}>
            {submitting ? '创建中…' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
