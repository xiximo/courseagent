import { ApiClientError } from '@/lib/api/client'
import type {
  AuthUserProfile,
  ChangePasswordBody,
  ChangePasswordResult,
  LoginBody,
  LoginResponse,
} from '@/lib/api/auth'
import { withMockDelay } from '@/lib/is-dev-mock'

const AUTH_USER_KEY = 'taixing_auth_user'
const MOCK_PASSWORD_KEY = 'taixing_mock_password'

function buildMockUser(username: string): AuthUserProfile {
  return {
    id: 'mock-user-1',
    username,
    fullName: '演示管理员',
    employeeNo: 'MOCK001',
    deptId: null,
    status: 'enabled',
    roleCodes: ['sys_admin', 'SYSTEM_ADMIN'],
    lastLoginAt: new Date().toISOString(),
  }
}

function loadStoredMockUser(): AuthUserProfile | null {
  if (typeof localStorage === 'undefined') return null
  const raw = localStorage.getItem(AUTH_USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUserProfile
  } catch {
    return null
  }
}

function getMockPassword(): string {
  if (typeof localStorage === 'undefined') return 'admin123'
  return localStorage.getItem(MOCK_PASSWORD_KEY) || 'admin123'
}

export async function mockLogin(body: LoginBody): Promise<LoginResponse> {
  const username = body.username.trim()
  if (!username) {
    throw new ApiClientError('INVALID_CREDENTIALS', '请输入用户名')
  }
  if (body.password.length < 6) {
    throw new ApiClientError('INVALID_CREDENTIALS', '密码至少 6 位')
  }

  const user = buildMockUser(username)
  return withMockDelay(
    {
      accessToken: 'mock-access-token',
      tokenType: 'Bearer',
      expiresInSeconds: 86400,
      user,
    },
    400
  )
}

export async function mockFetchCurrentUser(): Promise<AuthUserProfile> {
  const stored = loadStoredMockUser()
  if (stored) {
    return withMockDelay(stored)
  }
  return withMockDelay(buildMockUser('demo'))
}

export async function mockChangePassword(
  body: ChangePasswordBody
): Promise<ChangePasswordResult> {
  const current = body.currentPassword.trim()
  const next = body.newPassword.trim()
  if (!current) {
    throw new ApiClientError('INVALID_PASSWORD', '请输入当前密码')
  }
  if (next.length < 6) {
    throw new ApiClientError('WEAK_PASSWORD', '新密码至少 6 位')
  }
  if (current !== getMockPassword()) {
    throw new ApiClientError('INVALID_PASSWORD', '当前密码不正确')
  }
  if (next === current) {
    throw new ApiClientError('SAME_PASSWORD', '新密码不能与当前密码相同')
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(MOCK_PASSWORD_KEY, next)
  }
  return withMockDelay({ changed: true }, 300)
}
