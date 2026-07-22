import { isDevMock } from '@/lib/is-dev-mock'
import {
  mockChangePassword,
  mockFetchCurrentUser,
  mockLogin,
} from '@/lib/mock/auth-handlers'
import { apiFetch, readEnvelope } from './client'

export type AccountStatus = 'enabled' | 'disabled' | 'locked' | 'terminated'

export type AuthUserProfile = {
  id: string
  username: string
  fullName: string
  employeeNo: string | null
  deptId: string | null
  status: AccountStatus
  roleCodes: string[]
  lastLoginAt: string | null
}

export type LoginResponse = {
  accessToken: string
  tokenType: string
  expiresInSeconds: number
  user: AuthUserProfile
}

export type LoginBody = {
  username: string
  password: string
}

export type ChangePasswordBody = {
  currentPassword: string
  newPassword: string
}

export type ChangePasswordResult = {
  changed: boolean
}

export async function login(body: LoginBody): Promise<LoginResponse> {
  if (isDevMock()) return mockLogin(body)
  const res = await apiFetch('POST', '/api/v1/auth/login', body, {
    skipAuth: true,
  })
  return readEnvelope<LoginResponse>(res)
}

export async function fetchCurrentUser(): Promise<AuthUserProfile> {
  if (isDevMock()) return mockFetchCurrentUser()
  const res = await apiFetch('GET', '/api/v1/auth/me')
  return readEnvelope<AuthUserProfile>(res)
}

export async function changePassword(
  body: ChangePasswordBody
): Promise<ChangePasswordResult> {
  if (isDevMock()) return mockChangePassword(body)
  const res = await apiFetch('POST', '/api/v1/auth/change-password', body)
  return readEnvelope<ChangePasswordResult>(res)
}
