import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listCourseAgents } from '@/lib/api/course-agent'
import { courseAgentKeys } from '../lib/query-keys'

export function useCourseAgentsQuery(enabled = true) {
  return useQuery({
    queryKey: courseAgentKeys.list(),
    queryFn: listCourseAgents,
    enabled,
  })
}

export function useInvalidateCourseAgents() {
  const queryClient = useQueryClient()
  return () =>
    queryClient.invalidateQueries({ queryKey: courseAgentKeys.all })
}
