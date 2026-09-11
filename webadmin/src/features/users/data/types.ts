import type { AccountStatus } from '@/lib/api/auth'

export type UserPersonaProfile = {
  persona: string
  personaLabel: string
  summary: string
  goals: string[]
  constraints: string[]
  conditions?: string[]
  allergies?: string[]
  sampleQuestions: string[]
  notes?: string[]
}

export type UserAccount = {
  id: string
  username: string
  fullName: string
  status: AccountStatus
  roleCodes: string[]
  profile: UserPersonaProfile
  lastLoginAt: string | null
  createdAt: string | null
  isSeed: boolean
  tenantId?: string | null
  tenantName?: string | null
}

export type CreateUserInput = {
  username: string
  password: string
  fullName: string
  status?: AccountStatus
  roleCodes?: string[]
  profile?: UserPersonaProfile
}

export type UpdateUserInput = {
  fullName?: string
  status?: AccountStatus
  roleCodes?: string[]
  profile?: UserPersonaProfile
  password?: string
}

export type ResetUserPasswordResult = {
  message: string
  password: string
}

export const TEST_USER_PASSWORD = 'test1234'
