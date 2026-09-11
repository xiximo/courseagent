import { apiFetch, readEnvelope } from './client'

export type TenantSummary = {
  id: string
  name: string
  slug: string
  ownerUsername: string
  planCode: string
  userCount: number
  createdAt: string
}

export async function listPlatformTenants(): Promise<TenantSummary[]> {
  const res = await apiFetch('GET', '/api/v1/platform/tenants')
  return readEnvelope<TenantSummary[]>(res)
}

export async function updatePlatformTenantPlan(
  tenantId: string,
  planCode: 'free' | 'pro'
): Promise<TenantSummary> {
  const res = await apiFetch('PATCH', `/api/v1/platform/tenants/${tenantId}/plan`, {
    planCode,
  })
  return readEnvelope<TenantSummary>(res)
}

export async function deletePlatformTenant(
  tenantId: string
): Promise<{ message: string }> {
  const res = await apiFetch('DELETE', `/api/v1/platform/tenants/${tenantId}`)
  return readEnvelope<{ message: string }>(res)
}
