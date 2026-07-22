import type { ReactNode } from 'react'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'

type AppPageHeaderProps = {
  children?: ReactNode
}

export function AppPageHeader({ children }: AppPageHeaderProps) {
  return (
    <Header fixed>
      {children}
      <div className='ms-auto flex items-center gap-3 sm:gap-4'>
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </div>
    </Header>
  )
}
