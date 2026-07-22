import { createFileRoute, redirect } from '@tanstack/react-router'
import { buildAuthRedirectPath } from '@/lib/auth-redirect'
import { ACCESS_TOKEN_COOKIE } from '@/lib/api/client'
import { getCookie } from '@/lib/cookies'
import { AuthenticatedLayout } from '@/components/layout/authenticated-layout'

function hasAccessToken(): boolean {
  const raw = getCookie(ACCESS_TOKEN_COOKIE)
  if (!raw) return false
  try {
    const token = JSON.parse(raw) as string
    return Boolean(token)
  } catch {
    return false
  }
}

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: ({ location }) => {
    if (!hasAccessToken()) {
      throw redirect({
        to: '/sign-in',
        search: {
          redirect: buildAuthRedirectPath(
            location.pathname,
            location.searchStr,
            location.hash
          ),
        },
      })
    }
  },
  component: AuthenticatedLayout,
})
