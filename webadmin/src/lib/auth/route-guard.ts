import { redirect } from '@tanstack/react-router'
import type { AuthUserProfile } from '@/lib/api/auth'
import { canAccessPath } from './permissions'

function loadUser(): AuthUserProfile | null {
  if (typeof localStorage === 'undefined') return null
  const raw = localStorage.getItem('taixing_auth_user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUserProfile
  } catch {
    return null
  }
}

export function appRouteGuard(path: string) {
  const user = loadUser()
  const roleCodes = user?.roleCodes ?? []
  if (!canAccessPath(roleCodes, path)) {
    throw redirect({ to: '/403' })
  }
}
