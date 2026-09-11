import { useRouterState } from '@tanstack/react-router'

export function useIsPlatformConsole() {
  return useRouterState({
    select: (state) => state.location.pathname.startsWith('/saasadmin'),
  })
}

export function useAgentConsolePaths() {
  const platform = useIsPlatformConsole()
  return {
    list: platform ? '/saasadmin/agents' : '/admin/course-agents',
    detail: platform
      ? '/saasadmin/agents/$agentId'
      : '/admin/course-agents/$agentId',
  } as const
}

export function useKnowledgeConsolePaths() {
  const platform = useIsPlatformConsole()
  return {
    list: platform ? '/saasadmin/knowledge' : '/admin/knowledge',
    detail: platform
      ? '/saasadmin/knowledge/$kbId'
      : '/admin/knowledge/$kbId',
  } as const
}
