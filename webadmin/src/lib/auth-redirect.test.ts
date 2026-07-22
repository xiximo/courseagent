import { describe, expect, it } from 'vitest'
import { resolveAuthRedirect } from './auth-redirect'

describe('resolveAuthRedirect', () => {
  it('returns fallback when redirect is empty', () => {
    expect(resolveAuthRedirect(undefined, '/qa')).toBe('/qa')
  })

  it('accepts internal paths', () => {
    expect(resolveAuthRedirect('/sync')).toBe('/sync')
    expect(resolveAuthRedirect('/sync?tab=1')).toBe('/sync?tab=1')
  })

  it('extracts path from full same-origin URLs', () => {
    expect(
      resolveAuthRedirect('http://localhost:5174/sync')
    ).toBe('/sync')
    expect(
      resolveAuthRedirect('http://localhost:5174/sync?tab=1#logs')
    ).toBe('/sync?tab=1#logs')
  })

  it('rejects sign-in loops and external URLs', () => {
    expect(resolveAuthRedirect('/sign-in')).toBe('/')
    expect(resolveAuthRedirect('https://evil.example/sync')).toBe('/')
  })
})
