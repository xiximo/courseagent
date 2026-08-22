import { createFileRoute } from '@tanstack/react-router'
import { UsersListPage } from '@/features/users/pages/users-list-page'
import { appRouteGuard } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/users/')({
  beforeLoad: () => {
    appRouteGuard('/users')
  },
  component: UsersListPage,
})
