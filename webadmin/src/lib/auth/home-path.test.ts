import { beforeEach, describe, expect, it, vi } from 'vitest'
import { resolvePostLoginTarget } from './home-path'

vi.mock('@/lib/api/course-agent', () => ({
  listCourseAgents: vi.fn(),
}))

import { listCourseAgents } from '@/lib/api/course-agent'

const listMock = vi.mocked(listCourseAgents)

describe('resolvePostLoginTarget', () => {
  beforeEach(() => {
    listMock.mockReset()
  })

  it('sends members with a foreign chat redirect to their own published agent', async () => {
    listMock.mockResolvedValue([
      {
        agentId: 'agt_live',
        name: '膳食顾问',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        isDefault: true,
        updatedAt: '2026-01-02T00:00:00Z',
      },
    ])

    await expect(
      resolvePostLoginTarget('/admin/chat/agt_9ab8d9ab', ['end_user'])
    ).resolves.toEqual({
      to: '/admin/chat/$agentId',
      params: { agentId: 'agt_live' },
    })
  })

  it('sends members to the first published chat', async () => {
    listMock.mockResolvedValue([
      {
        agentId: 'agt_draft',
        name: '草稿',
        description: '',
        status: 'draft',
        agentType: 'autonomous',
        updatedAt: '2026-01-01T00:00:00Z',
      },
      {
        agentId: 'agt_live',
        name: '膳食顾问',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        isDefault: true,
        updatedAt: '2026-01-02T00:00:00Z',
      },
    ])

    await expect(
      resolvePostLoginTarget(undefined, ['end_user'])
    ).resolves.toEqual({
      to: '/admin/chat/$agentId',
      params: { agentId: 'agt_live' },
    })
  })

  it('does not send members to agent config even if that was the redirect', async () => {
    listMock.mockResolvedValue([
      {
        agentId: 'agt_live',
        name: '膳食顾问',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        updatedAt: '2026-01-02T00:00:00Z',
      },
    ])

    await expect(
      resolvePostLoginTarget('/admin/course-agents', ['end_user'])
    ).resolves.toEqual({
      to: '/admin/chat/$agentId',
      params: { agentId: 'agt_live' },
    })
  })

  it('skips scheduled-only agents when picking member home chat', async () => {
    listMock.mockResolvedValue([
      {
        agentId: 'agt_job',
        name: '画像刷新',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        runMode: 'scheduled',
        visibleInChat: false,
        updatedAt: '2026-01-02T00:00:00Z',
      },
      {
        agentId: 'agt_live',
        name: '膳食顾问',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        isDefault: true,
        updatedAt: '2026-01-02T00:00:00Z',
      },
    ])

    await expect(
      resolvePostLoginTarget(undefined, ['end_user'])
    ).resolves.toEqual({
      to: '/admin/chat/$agentId',
      params: { agentId: 'agt_live' },
    })
  })

  it('sends platform admins to the saas console', async () => {
    await expect(
      resolvePostLoginTarget(undefined, ['sys_admin'])
    ).resolves.toEqual({ to: '/saasadmin' })
    expect(listMock).not.toHaveBeenCalled()
  })

  it('sends institution admins to /admin', async () => {
    await expect(
      resolvePostLoginTarget(undefined, ['org_admin'])
    ).resolves.toEqual({ to: '/admin' })
    expect(listMock).not.toHaveBeenCalled()
  })

  it('ignores a chat redirect that belongs to another tenant', async () => {
    listMock.mockResolvedValue([
      {
        agentId: 'agt_bb',
        name: 'BB 顾问',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        updatedAt: '2026-01-02T00:00:00Z',
      },
    ])

    await expect(
      resolvePostLoginTarget('/admin/chat/agt_9ab8d9ab', ['org_admin'])
    ).resolves.toEqual({ to: '/admin' })
  })

  it('keeps a chat redirect when the agent belongs to the current tenant', async () => {
    listMock.mockResolvedValue([
      {
        agentId: 'agt_9ab8d9ab',
        name: 'AA 顾问',
        description: '',
        status: 'active',
        agentType: 'autonomous',
        updatedAt: '2026-01-02T00:00:00Z',
      },
    ])

    await expect(
      resolvePostLoginTarget('/admin/chat/agt_9ab8d9ab', ['org_admin'])
    ).resolves.toEqual({
      to: '/admin/chat/$agentId',
      params: { agentId: 'agt_9ab8d9ab' },
    })
  })
})
