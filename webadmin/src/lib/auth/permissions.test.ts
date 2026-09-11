import { describe, expect, it } from 'vitest'
import { canAccessPath, hasPermission, isAdmin, isOrgAdmin } from './permissions'

describe('permissions', () => {
  it('treats sys_admin as admin', () => {
    expect(isAdmin(['end_user'])).toBe(false)
    expect(isAdmin(['sys_admin'])).toBe(true)
    expect(isOrgAdmin(['org_admin'])).toBe(true)
  })

  it('lets members chat but not configure agents', () => {
    const member = ['end_user']
    expect(hasPermission(member, 'course_agent_view')).toBe(true)
    expect(hasPermission(member, 'course_agent_config')).toBe(false)
    expect(canAccessPath(member, '/admin/chat/agt_1')).toBe(true)
    expect(canAccessPath(member, '/admin/course-agents')).toBe(false)
    expect(canAccessPath(member, '/admin/knowledge')).toBe(false)
    expect(canAccessPath(member, '/admin/members')).toBe(false)
    expect(canAccessPath(member, '/users')).toBe(false)
    expect(canAccessPath(member, '/audit')).toBe(false)
  })

  it('lets org admins open the institution workspace but not the platform console', () => {
    const org = ['org_admin']
    expect(canAccessPath(org, '/admin')).toBe(true)
    expect(canAccessPath(org, '/admin/knowledge')).toBe(true)
    expect(canAccessPath(org, '/admin/course-agents/leads')).toBe(true)
    expect(canAccessPath(org, '/admin/members')).toBe(true)
    expect(canAccessPath(org, '/plans')).toBe(true)
    expect(canAccessPath(org, '/admin/course-agents')).toBe(true)
    expect(canAccessPath(org, '/saasadmin')).toBe(false)
    expect(canAccessPath(org, '/saasadmin/tenants')).toBe(false)
    expect(canAccessPath(org, '/users')).toBe(false)
  })

  it('lets platform admins open the saas console but not the org workspace', () => {
    const admin = ['sys_admin']
    expect(canAccessPath(admin, '/saasadmin')).toBe(true)
    expect(canAccessPath(admin, '/saasadmin/tenants')).toBe(true)
    expect(canAccessPath(admin, '/saasadmin/agents')).toBe(true)
    expect(canAccessPath(admin, '/admin/chat/agt_1')).toBe(true)
    expect(canAccessPath(admin, '/admin')).toBe(false)
    expect(canAccessPath(admin, '/admin/knowledge')).toBe(false)
    expect(canAccessPath(admin, '/users')).toBe(true)
  })
})
