import { useMemo } from 'react'
import { useAuthStore } from '@/stores/auth-store'
import {
  canAccessPath,
  hasPermission,
  isAdmin,
  isOrgAdmin,
  isPlatformAdmin,
  type AppPermission,
} from '@/lib/auth/permissions'

export function useAppPermissions() {
  const user = useAuthStore((s) => s.auth.user)
  const roleCodes = user?.roleCodes ?? []

  const admin = useMemo(() => isAdmin(roleCodes), [roleCodes])
  const platform = useMemo(() => isPlatformAdmin(roleCodes), [roleCodes])
  const org = useMemo(() => isOrgAdmin(roleCodes), [roleCodes])

  return {
    isAdmin: admin,
    isPlatformAdmin: platform,
    isOrgAdmin: org,
    can: (permission: AppPermission) => hasPermission(roleCodes, permission),
    canAccess: (path: string) => canAccessPath(roleCodes, path),
  }
}
