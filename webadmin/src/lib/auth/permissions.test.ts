import { describe, expect, it } from 'vitest'
import { canAccessPath, hasPermission, isAdmin } from './permissions'

describe('permissions', () => {
  it('treats sys_admin as admin', () => {
    expect(isAdmin(['end_user'])).toBe(false)
    expect(isAdmin(['sys_admin'])).toBe(true)
  })

  it('lets members chat but not configure agents', () => {
    const member = ['end_user']
    expect(hasPermission(member, 'course_agent_view')).toBe(true)
    expect(hasPermission(member, 'course_agent_config')).toBe(false)
    expect(canAccessPath(member, '/admin/chat/agt_1')).toBe(true)
    expect(canAccessPath(member, '/admin/course-agents')).toBe(false)
    expect(canAccessPath(member, '/admin/knowledge')).toBe(false)
    expect(canAccessPath(member, '/users')).toBe(false)
    expect(canAccessPath(member, '/audit')).toBe(false)
  })

  it('lets admins open config and user management', () => {
    const admin = ['sys_admin']
    expect(canAccessPath(admin, '/admin/course-agents')).toBe(true)
    expect(canAccessPath(admin, '/admin/chat/agt_1')).toBe(true)
    expect(canAccessPath(admin, '/users')).toBe(true)
    expect(canAccessPath(admin, '/audit')).toBe(true)
  })
})
