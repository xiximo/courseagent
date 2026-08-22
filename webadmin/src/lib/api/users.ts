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

export async function listUsers(): Promise<UserAccount[]> {
  if (isDevMock()) return mockListUsers()
  const res = await apiFetch('GET', '/api/v1/users')
  return readEnvelope<UserAccount[]>(res)
}

export async function createUser(body: CreateUserInput): Promise<UserAccount> {
  if (isDevMock()) return mockCreateUser(body)
  const res = await apiFetch('POST', '/api/v1/users', body)
  return readEnvelope<UserAccount>(res)
}

export async function updateUser(
  userId: string,
  body: UpdateUserInput
): Promise<UserAccount> {
  if (isDevMock()) return mockUpdateUser(userId, body)
  const res = await apiFetch('PATCH', `/api/v1/users/${userId}`, body)
  return readEnvelope<UserAccount>(res)
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
