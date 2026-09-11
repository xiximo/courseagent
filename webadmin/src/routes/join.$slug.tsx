import { createFileRoute } from '@tanstack/react-router'
import { JoinOrgPage } from '@/features/auth/join'

export const Route = createFileRoute('/join/$slug')({
  component: JoinOrgPage,
})
