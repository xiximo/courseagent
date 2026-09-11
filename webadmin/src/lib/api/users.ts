import { apiFetch, readEnvelope } from './client'
import { isDevMock } from '@/lib/is-dev-mock'
import {
  mockCreateUser,
  mockDeleteUser,
  mockListUsers,
  mockResetUserPassword,
  mockUpdateUser,
} from '@/features/users/mock/user-handlers'
import type {
  CreateUserInput,
  ResetUserPasswordResult,
  UpdateUserInput,
  UserAccount,
} from '@/features/users/data/types'

type UserAccountPayload = UserAccount & {
  tenant_id?: string | null
  tenant_name?: string | null
}

function asOptionalText(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function normalizeUserAccount(row: UserAccountPayload): UserAccount {
  return {
    ...row,
    tenantId: asOptionalText(row.tenantId) ?? asOptionalText(row.tenant_id),
    tenantName: asOptionalText(row.tenantName) ?? asOptionalText(row.tenant_name),
  }
}

export async function listUsers(): Promise<UserAccount[]> {
  if (isDevMock()) return mockListUsers()
  const res = await apiFetch('GET', '/api/v1/users')
  const rows = await readEnvelope<UserAccountPayload[]>(res)
  return rows.map(normalizeUserAccount)
}

export async function createUser(body: CreateUserInput): Promise<UserAccount> {
  if (isDevMock()) return mockCreateUser(body)
  const res = await apiFetch('POST', '/api/v1/users', body)
  return normalizeUserAccount(await readEnvelope<UserAccountPayload>(res))
}

export async function updateUser(
  userId: string,
  body: UpdateUserInput
): Promise<UserAccount> {
  if (isDevMock()) return mockUpdateUser(userId, body)
  const res = await apiFetch('PATCH', `/api/v1/users/${userId}`, body)
  return normalizeUserAccount(await readEnvelope<UserAccountPayload>(res))
}

export async function deleteUser(userId: string): Promise<{ message: string }> {
  if (isDevMock()) return mockDeleteUser(userId)
  const res = await apiFetch('DELETE', `/api/v1/users/${userId}`)
  return readEnvelope<{ message: string }>(res)
}

export async function resetUserPassword(
  userId: string
): Promise<ResetUserPasswordResult> {
  if (isDevMock()) return mockResetUserPassword(userId)
  const res = await apiFetch('POST', `/api/v1/users/${userId}/reset-password`)
  return readEnvelope<ResetUserPasswordResult>(res)
}
