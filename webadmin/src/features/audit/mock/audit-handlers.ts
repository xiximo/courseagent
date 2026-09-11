import { withMockDelay } from '@/lib/is-dev-mock'
import type { LoginAuditLog } from '../data/types'

const MOCK_LOGS: LoginAuditLog[] = [
  {
    id: 'mock-audit-1',
    username: 'admin',
    fullName: '系统管理员',
    ipAddress: '127.0.0.1',
    loggedInAt: new Date().toISOString(),
  },
  {
    id: 'mock-audit-2',
    username: 'qiming',
    fullName: '启明',
    ipAddress: '10.0.0.18',
    loggedInAt: new Date(Date.now() - 36e5).toISOString(),
  },
  {
    id: 'mock-audit-3',
    username: 'aaa',
    fullName: 'eee',
    ipAddress: '192.168.1.24',
    loggedInAt: new Date(Date.now() - 864e5).toISOString(),
  },
]

export async function mockListLoginAudits(): Promise<LoginAuditLog[]> {
  return withMockDelay(MOCK_LOGS, 200)
}
