import { createFileRoute, redirect } from '@tanstack/react-router'
import { resolveLoggedInHome } from '@/lib/auth/home-path'

export const Route = createFileRoute('/_authenticated/')({
  beforeLoad: async () => {
    const dest = await resolveLoggedInHome()
    if (dest.params?.agentId) {
      throw redirect({
        to: '/admin/chat/$agentId',
        params: { agentId: dest.params.agentId },
      })
    }
    throw redirect({ to: dest.to as '/admin/course-agents' | '/settings/account' })
  },
})
