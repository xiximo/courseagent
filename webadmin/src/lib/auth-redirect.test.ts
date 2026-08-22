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
    const origin =
      typeof window !== 'undefined'
        ? window.location.origin
        : 'http://localhost:5174'
    expect(resolveAuthRedirect(`${origin}/sync`)).toBe('/sync')
    expect(resolveAuthRedirect(`${origin}/sync?tab=1#logs`)).toBe(
      '/sync?tab=1#logs'
    )
  })

  it('rejects sign-in loops, error pages and external URLs', () => {
    expect(resolveAuthRedirect('/sign-in')).toBe('/')
    expect(resolveAuthRedirect('/403')).toBe('/')
    expect(resolveAuthRedirect('https://evil.example/sync')).toBe('/')
  })
})
