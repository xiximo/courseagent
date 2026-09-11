import { apiFetch, readEnvelope } from './client'

export type PublicTenant = {
  name: string
  slug: string
}

export type OrgWorkspace = {
  tenantId: string
  tenantName: string
  slug: string
  planCode: string
  userCount: number
  joinPath: string
}

export type OrgMember = {
  id: string
  username: string
  fullName: string
  status: string
  roleCodes: string[]
  lastLoginAt: string | null
  createdAt: string | null
}

export type CreateOrgMemberInput = {
  fullName: string
  username: string
  password: string
}

export async function getPublicTenant(slug: string): Promise<PublicTenant> {
  const res = await apiFetch('GET', `/api/v1/org/public/${encodeURIComponent(slug)}`, undefined, {
    skipAuth: true,
  })
  return readEnvelope<PublicTenant>(res)
}

export async function getOrgWorkspace(): Promise<OrgWorkspace> {
  const res = await apiFetch('GET', '/api/v1/org/me')
  return readEnvelope<OrgWorkspace>(res)
}

export async function listOrgMembers(): Promise<OrgMember[]> {
  const res = await apiFetch('GET', '/api/v1/org/members')
  return readEnvelope<OrgMember[]>(res)
}

export async function createOrgMember(
  body: CreateOrgMemberInput
): Promise<OrgMember> {
  const res = await apiFetch('POST', '/api/v1/org/members', body)
  return readEnvelope<OrgMember>(res)
}
