import { redirect } from '@tanstack/react-router'
import type { AuthUserProfile } from '@/lib/api/auth'
import { canAccessPath, isPlatformAdmin } from './permissions'

export function loadAuthUser(): AuthUserProfile | null {
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
  const roleCodes = loadAuthUser()?.roleCodes ?? []
  if (!canAccessPath(roleCodes, path)) {
    throw redirect({ to: '/403' })
  }
}

export function redirectIfPlatform(to: string, params?: Record<string, string>) {
  const roleCodes = loadAuthUser()?.roleCodes ?? []
  if (!isPlatformAdmin(roleCodes)) return
  throw redirect({
    to,
    params,
  })
}
