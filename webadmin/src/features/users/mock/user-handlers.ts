import { withMockDelay } from '@/lib/is-dev-mock'
import { ApiClientError } from '@/lib/api/client'
import type {
  CreateUserInput,
  ResetUserPasswordResult,
  UpdateUserInput,
  UserAccount,
  UserPersonaProfile,
} from '../data/types'
import { TEST_USER_PASSWORD } from '../data/types'

const emptyProfile: UserPersonaProfile = {
  persona: '',
  personaLabel: '',
  summary: '',
  goals: [],
  constraints: [],
  sampleQuestions: [],
}

let users: UserAccount[] = [
  {
    id: 'mock-admin',
    username: 'admin',
    fullName: '系统管理员',
    status: 'enabled',
    roleCodes: ['sys_admin', 'SYSTEM_ADMIN'],
    profile: {
      persona: 'admin',
      personaLabel: '管理员',
      summary: '平台管理员，负责智能体、知识库与测试用户。',
      goals: [],
      constraints: [],
      sampleQuestions: [],
    },
    lastLoginAt: null,
    createdAt: new Date().toISOString(),
    isSeed: false,
  },
]

export async function mockListUsers(): Promise<UserAccount[]> {
  return withMockDelay(
    users.map((item) => ({ ...item })),
    200
  )
}

export async function mockCreateUser(body: CreateUserInput): Promise<UserAccount> {
  if (users.some((item) => item.username === body.username.trim())) {
    throw new ApiClientError('USERNAME_TAKEN', '用户名已存在')
  }
  const created: UserAccount = {
    id: `mock-${crypto.randomUUID()}`,
    username: body.username.trim(),
    fullName: body.fullName.trim(),
    status: body.status ?? 'enabled',
    roleCodes: body.roleCodes ?? ['end_user'],
    profile: body.profile ?? emptyProfile,
    lastLoginAt: null,
    createdAt: new Date().toISOString(),
    isSeed: false,
  }
  users = [...users, created]
  return withMockDelay(created, 200)
}

export async function mockUpdateUser(
  userId: string,
  body: UpdateUserInput
): Promise<UserAccount> {
  const current = users.find((item) => item.id === userId)
  if (!current) throw new ApiClientError('NOT_FOUND', '用户不存在')
  const next: UserAccount = {
    ...current,
    fullName: body.fullName ?? current.fullName,
    status: body.status ?? current.status,
    roleCodes: body.roleCodes ?? current.roleCodes,
    profile: body.profile ?? current.profile,
  }
  users = users.map((item) => (item.id === userId ? next : item))
  return withMockDelay(next, 200)
}

export async function mockDeleteUser(
  userId: string
): Promise<{ message: string }> {
  const current = users.find((item) => item.id === userId)
  if (!current) throw new ApiClientError('NOT_FOUND', '用户不存在')
  if (current.roleCodes.some((code) => code.toLowerCase().includes('admin'))) {
    throw new ApiClientError('LAST_ADMIN', '不能删除最后一个管理员')
  }
  users = users.filter((item) => item.id !== userId)
  return withMockDelay({ message: '用户已删除' }, 200)
}

export async function mockResetUserPassword(
  _userId: string
): Promise<ResetUserPasswordResult> {
  return withMockDelay(
    { message: '密码已重置为测试口令', password: TEST_USER_PASSWORD },
    200
  )
}
