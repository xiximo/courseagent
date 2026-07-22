import type { ReactNode } from 'react'
import { AppPageHeader } from '@/components/app-page-header'
import { AppErrorAlert } from '@/components/app-error-alert'
import { Main } from '@/components/layout/main'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useAppPermissions } from '@/hooks/use-app-permissions'
import { AgentConfigProvider, useAgentConfig } from '../context/agent-config-context'
import { PLATFORM_AGENT_ID } from '../lib/platform-agent'

type PlatformAgentPageShellProps = {
  children: ReactNode
}

function PlatformAgentPageBody({ children }: PlatformAgentPageShellProps) {
  const { can, isAdmin } = useAppPermissions()
  const canConfig = can('course_agent_config')
  const { loading, error } = useAgentConfig()

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

        {error ? <AppErrorAlert message={error} /> : null}

        {loading ? (
          <p className='text-muted-foreground'>加载中…</p>
        ) : (
          children
        )}
      </Main>
    </>
  )
}

export function PlatformAgentPageShell({ children }: PlatformAgentPageShellProps) {
  const { can } = useAppPermissions()

  return (
    <AgentConfigProvider
      agentId={PLATFORM_AGENT_ID}
      canConfig={can('course_agent_config')}
    >
      <PlatformAgentPageBody>{children}</PlatformAgentPageBody>
    </AgentConfigProvider>
  )
}
