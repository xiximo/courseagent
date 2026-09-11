import { createFileRoute } from '@tanstack/react-router'
import { UsersListPage } from '@/features/users/pages/users-list-page'
import { appRouteGuard, redirectIfPlatform } from '@/lib/auth/route-guard'

export const Route = createFileRoute('/_authenticated/users/')({
  beforeLoad: () => {
    redirectIfPlatform('/saasadmin/users')
    appRouteGuard('/users')
  },
  component: UsersListPage,
})
