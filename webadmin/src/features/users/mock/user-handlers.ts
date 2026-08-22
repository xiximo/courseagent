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

const seedPersonas: UserAccount[] = [
  {
    id: 'mock-fatloss',
    username: 'fatloss',
    fullName: '林晓（减脂塑形）',
    status: 'enabled',
    roleCodes: ['end_user'],
    profile: {
      persona: 'fat_loss',
      personaLabel: '减脂塑形',
      summary:
        '32 岁互联网运营，久坐，BMI 偏高、体脂率超标，希望科学减重、控制热量并搭配三餐。',
      goals: ['12 周减重 6–8kg', '午餐外食可控热量'],
      constraints: ['工作日几乎不做饭', '对乳糖轻微不耐受'],
      sampleQuestions: [
        '我想减重，每天大概吃多少热量合适？',
        '轻盈减脂方案怎么安排三餐？',
      ],
    },
    lastLoginAt: null,
    createdAt: new Date().toISOString(),
    isSeed: true,
  },
  {
    id: 'mock-muscle',
    username: 'muscle',
    fullName: '周凯（增肌强化）',
    status: 'enabled',
    roleCodes: ['end_user'],
    profile: {
      persona: 'muscle_gain',
      personaLabel: '增肌强化',
      summary:
        '28 岁，每周力量训练 4 次，希望增加肌肉量、改善体成分。',
      goals: ['增肌不猛增脂肪', '力量增肌方案落地'],
      constraints: ['训练日晚饭较晚'],
      sampleQuestions: [
        '增肌期蛋白质一天要吃多少？',
        '力量增肌方案训练日怎么吃？',
      ],
    },
    lastLoginAt: null,
    createdAt: new Date().toISOString(),
    isSeed: true,
  },
  {
    id: 'mock-wellness',
    username: 'wellness',
    fullName: '陈敏（慢病调理）',
    status: 'enabled',
    roleCodes: ['end_user'],
    profile: {
      persona: 'chronic_care',
      personaLabel: '慢病调理',
      summary:
        '41 岁，体检血糖偏高、血压临界，关注低 GI、控盐控糖与饮食禁忌。',
      goals: ['稳糖调理', '控盐控糖'],
      constraints: ['对海鲜过敏', '不接受极端生酮'],
      sampleQuestions: [
        '我血糖有点高，早餐怎么吃？',
        '稳糖调理方案和控糖 321 餐盘怎么用？',
      ],
    },
    lastLoginAt: null,
    createdAt: new Date().toISOString(),
    isSeed: true,
  },
  {
    id: 'mock-member',
    username: 'member',
    fullName: '赵倩（平台咨询）',
    status: 'enabled',
    roleCodes: ['end_user'],
    profile: {
      persona: 'platform',
      personaLabel: '平台咨询',
      summary:
        '企业 HR，想了解健康优选会员订阅、企业健康管理 SaaS 与营养师 1 对 1。',
      goals: ['对比标准版/专业版会员', '评估企业合作'],
      constraints: ['问题应走平台白皮书'],
      sampleQuestions: [
        '标准版和专业版会员有什么区别？',
        '企业健康管理 SaaS 怎么合作？',
      ],
    },
    lastLoginAt: null,
    createdAt: new Date().toISOString(),
    isSeed: true,
  },
]

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
  ...seedPersonas,
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
