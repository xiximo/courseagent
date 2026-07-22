import type { ReactNode } from 'react'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useAppPermissions } from '@/hooks/use-app-permissions'

type KnowledgePageShellProps = {
  children: ReactNode
}

export function KnowledgePageShell({ children }: KnowledgePageShellProps) {
  const { can, isAdmin } = useAppPermissions()
  const canConfig = can('course_agent_config')

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        {!canConfig && can('course_agent_view') ? (
          <Alert>
            <AlertDescription>
              当前账号为只读；配置修改需管理员权限。
              {!isAdmin ? '（请联系系统管理员）' : null}
            </AlertDescription>
          </Alert>
        ) : null}
        {children}
      </Main>
    </>
  )
}
