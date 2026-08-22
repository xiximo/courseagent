const SIGN_IN_PREFIX = '/sign-in'
const BLOCKED_AUTH_PATHS = new Set(['/403', '/401', '/404', '/500'])

function isBlockedAuthPath(path: string): boolean {
  const base = path.split('?')[0] ?? path
  if (base.startsWith(SIGN_IN_PREFIX)) return true
  return BLOCKED_AUTH_PATHS.has(base)
}

function isSafeInternalPath(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//')
}

function normalizeRedirectUrl(value: string): string {
  return value
    .replace(/^http:\/(?!\/)/, 'http://')
    .replace(/^https:\/(?!\/)/, 'https://')
}

export function buildAuthRedirectPath(
  pathname: string,
  search = '',
  hash = ''
): string {
  const path = pathname || '/'
  return `${path}${search}${hash}`
}

export function resolveAuthRedirect(
  redirect: string | undefined,
  fallback = '/'
): string {
  const trimmed = redirect?.trim()
  if (!trimmed) return fallback

  if (isSafeInternalPath(trimmed)) {
    return isBlockedAuthPath(trimmed) ? fallback : trimmed
  }

  try {
    const base =
      typeof window !== 'undefined'
        ? window.location.origin
        : 'http://localhost'
    const url = new URL(normalizeRedirectUrl(trimmed), base)
    if (
      typeof window !== 'undefined' &&
      url.origin !== window.location.origin
    ) {
      return fallback
    }
    const path = buildAuthRedirectPath(
      url.pathname || '/',
      url.search,
      url.hash
    )
    return isBlockedAuthPath(path) ? fallback : path
  } catch {
    return fallback
  }
}

export function currentAuthRedirectPath(): string {
  if (typeof window === 'undefined') return '/'
  return buildAuthRedirectPath(
    window.location.pathname,
    window.location.search,
    window.location.hash
  )
}
