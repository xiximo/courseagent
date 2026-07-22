const SIGN_IN_PREFIX = '/sign-in'

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
    return trimmed.startsWith(SIGN_IN_PREFIX) ? fallback : trimmed
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
    return path.startsWith(SIGN_IN_PREFIX) ? fallback : path
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
