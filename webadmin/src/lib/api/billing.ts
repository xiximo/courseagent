import { apiFetch, readEnvelope } from './client'

export type BillingPlan = {
  code: string
  name: string
  priceLabel: string
  priceCents: number
  chatLimit: number | null
  knowledgeBaseLimit?: number | null
  features: string[]
  highlighted: boolean
}

export type BillingUsage = {
  yearMonth: string
  used: number
  limit: number | null
  remaining: number | null
}

export type BillingMe = {
  planCode: string
  planName: string
  planUpgradedAt: string | null
  usage: BillingUsage
  canManageKnowledge: boolean
  canUseHarnessAgent: boolean
  knowledgeBaseLimit?: number | null
  knowledgeBaseUsed?: number
  canCreateKnowledgeBase?: boolean
}

export type BillingOrder = {
  id: string
  planCode: string
  amountCents: number
  status: string
  channel?: string
  providerTradeNo?: string | null
  createdAt: string
  paidAt: string | null
}

export type BillingPayOptions = {
  alipaySandbox: boolean
  alipayReady: boolean
  mockPayEnabled: boolean
  gateway: string
  stripeReady: boolean
  stripeMode: string
  stripeCurrency: string
}

export type AlipayPagePay = {
  orderId: string
  payUrl: string
  gateway: string
}

export type StripeCheckout = {
  orderId: string
  payUrl: string
  sessionId: string
  mode: string
}

export type UsageTrendPoint = {
  date: string
  chatCount: number
  activeUsers: number
}

export type UsageUserRank = {
  userId: string
  username: string
  fullName: string
  chatCount: number
}

export type AdminUsageStats = {
  totalChats: number
  activeUsers: number
  freeUsers: number
  proUsers: number
  trend: UsageTrendPoint[]
  topUsers?: UsageUserRank[]
}

export async function listBillingPlans(): Promise<BillingPlan[]> {
  const res = await apiFetch('GET', '/api/v1/billing/plans')
  return readEnvelope<BillingPlan[]>(res)
}

export async function getBillingMe(): Promise<BillingMe> {
  const res = await apiFetch('GET', '/api/v1/billing/me')
  return readEnvelope<BillingMe>(res)
}

export async function createBillingOrder(planCode = 'pro'): Promise<BillingOrder> {
  const res = await apiFetch('POST', '/api/v1/billing/orders', { planCode })
  return readEnvelope<BillingOrder>(res)
}

export async function getBillingPayOptions(): Promise<BillingPayOptions> {
  const res = await apiFetch('GET', '/api/v1/billing/pay-options')
  return readEnvelope<BillingPayOptions>(res)
}

export async function startAlipayPagePay(orderId: string): Promise<AlipayPagePay> {
  const res = await apiFetch('POST', `/api/v1/billing/orders/${orderId}/alipay/page-pay`)
  return readEnvelope<AlipayPagePay>(res)
}

export async function startStripeCheckout(orderId: string): Promise<StripeCheckout> {
  const res = await apiFetch('POST', `/api/v1/billing/orders/${orderId}/stripe/checkout`)
  return readEnvelope<StripeCheckout>(res)
}

export async function mockPayBillingOrder(orderId: string): Promise<BillingOrder> {
  const res = await apiFetch('POST', `/api/v1/billing/orders/${orderId}/mock-pay`)
  return readEnvelope<BillingOrder>(res)
}

export async function getAdminUsageStats(days = 30): Promise<AdminUsageStats> {
  const res = await apiFetch('GET', `/api/v1/admin/usage-stats?days=${days}`)
  return readEnvelope<AdminUsageStats>(res)
}
