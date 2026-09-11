import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listCourseAgents } from '@/lib/api/course-agent'
import { useAuthStore } from '@/stores/auth-store'
import { courseAgentKeys } from '../lib/query-keys'

export function useCourseAgentsQuery(enabled = true) {
  const tenantId = useAuthStore((s) => s.auth.user?.tenantId ?? null)
  return useQuery({
    queryKey: [...courseAgentKeys.list(), tenantId ?? 'platform'],
    queryFn: listCourseAgents,
    enabled,
  })
}

export function useInvalidateCourseAgents() {
  const queryClient = useQueryClient()
  return () =>
    queryClient.invalidateQueries({ queryKey: courseAgentKeys.all })
}
