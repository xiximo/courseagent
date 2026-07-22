import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import useDialogState from '@/hooks/use-dialog-state'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SignOutDialog } from '@/components/sign-out-dialog'

type AvatarDisplay = {
  text: string
  shape: 'circle' | 'pill'
  textClass?: string
}

function avatarDisplay(name: string): AvatarDisplay {
  const trimmed = name.trim()
  if (!trimmed) return { text: '?', shape: 'circle' }
  if (/[\u4e00-\u9fff]/.test(trimmed)) {
    const text = [...trimmed.replace(/\s/g, '')].join('')
    const len = text.length
    if (len <= 2) return { text, shape: 'circle' }
    if (len === 3) {
      return {
        text,
        shape: 'circle',
        textClass: 'text-[10px] leading-none tracking-tight',
      }
    }
    return {
      text,
      shape: 'pill',
      textClass: cn(
        'leading-none whitespace-nowrap px-0.5',
        len <= 4 ? 'text-[11px]' : 'text-[10px]'
      ),
    }
  }
  const parts = trimmed.split(/\s+/)
  if (parts.length >= 2) {
    return {
      text: `${parts[0][0]}${parts[1][0]}`.toUpperCase(),
      shape: 'circle',
    }
  }
  return { text: trimmed.slice(0, 2).toUpperCase(), shape: 'circle' }
}

export function ProfileDropdown() {
  const { t } = useTranslation()
  const [open, setOpen] = useDialogState()
  const user = useAuthStore((s) => s.auth.user)

  const displayName = user?.fullName || user?.username || t('auth.guest')
  const subtitle = user?.username ?? ''
  const avatar = avatarDisplay(displayName)
  const isPill = avatar.shape === 'pill'

  return (
    <>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button
            variant='ghost'
            className={cn(
              'relative h-8 rounded-full p-0',
              isPill ? 'w-auto max-w-[7rem] px-1' : 'w-8'
            )}
          >
            <Avatar
              className={cn(
                'rounded-full',
                isPill ? 'size-auto h-8 w-auto min-w-8 max-w-full' : 'size-8'
              )}
            >
              <AvatarFallback className={cn(avatar.textClass)}>
                {avatar.text}
              </AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className='w-56' align='end' forceMount>
          <DropdownMenuLabel className='font-normal'>
            <div className='flex flex-col gap-1.5'>
              <p className='text-sm leading-none font-medium'>{displayName}</p>
              <p className='text-xs leading-none text-muted-foreground'>
                {subtitle}
              </p>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem asChild>
              <Link to='/settings/account'>{t('nav.link.account')}</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link to='/settings/appearance'>{t('nav.link.appearance')}</Link>
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant='destructive' onClick={() => setOpen(true)}>
            {t('auth.signOut')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <SignOutDialog open={!!open} onOpenChange={setOpen} />
    </>
  )
}
