import type { ReactNode } from 'react'
import { AppPageHeader } from '@/components/app-page-header'
import { Main } from '@/components/layout/main'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useAppPermissions } from '@/hooks/use-app-permissions'

type KnowledgePageShellProps = {
  children: ReactNode
  title?: string
  description?: string
}

export function KnowledgePageShell({
  children,
  title,
  description,
}: KnowledgePageShellProps) {
  const { can, isAdmin } = useAppPermissions()
  const canConfig = can('course_agent_config')

  return (
    <>
      <AppPageHeader />
      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        {title ? (
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>{title}</h1>
            {description ? (
              <p className='text-muted-foreground mt-1'>{description}</p>
            ) : null}
          </div>
        ) : null}
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
