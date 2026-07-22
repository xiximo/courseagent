import { useMemo } from 'react'
import { useAuthStore } from '@/stores/auth-store'
import {
  canAccessPath,
  hasPermission,
  isAdmin,
  type AppPermission,
} from '@/lib/auth/permissions'

export function useAppPermissions() {
  const user = useAuthStore((s) => s.auth.user)
  const roleCodes = user?.roleCodes ?? []

  const admin = useMemo(() => isAdmin(roleCodes), [roleCodes])

  return {
    isAdmin: admin,
    can: (permission: AppPermission) => hasPermission(roleCodes, permission),
    canAccess: (path: string) => canAccessPath(roleCodes, path),
  }
}
