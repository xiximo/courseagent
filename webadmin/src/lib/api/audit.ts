import { apiFetch, readEnvelope } from './client'
import { isDevMock } from '@/lib/is-dev-mock'
import { mockListLoginAudits } from '@/features/audit/mock/audit-handlers'
import type { LoginAuditLog } from '@/features/audit/data/types'

export async function listLoginAudits(): Promise<LoginAuditLog[]> {
  if (isDevMock()) return mockListLoginAudits()
  const res = await apiFetch('GET', '/api/v1/audit/login-logs')
  return readEnvelope<LoginAuditLog[]>(res)
}
