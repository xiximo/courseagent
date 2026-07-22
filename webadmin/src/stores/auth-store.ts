import { create } from 'zustand'
import type { AuthUserProfile } from '@/lib/api/auth'
import { getCookie, setCookie, removeCookie } from '@/lib/cookies'
import { ACCESS_TOKEN_COOKIE } from '@/lib/api/client'

const AUTH_USER_KEY = 'taixing_auth_user'

function loadStoredUser(): AuthUserProfile | null {
  if (typeof localStorage === 'undefined') return null
  const raw = localStorage.getItem(AUTH_USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUserProfile
  } catch {
    return null
  }
}

function persistUser(user: AuthUserProfile | null) {
  if (typeof localStorage === 'undefined') return
  if (user) {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
  } else {
    localStorage.removeItem(AUTH_USER_KEY)
  }
}

interface AuthState {
  auth: {
    user: AuthUserProfile | null
    setUser: (user: AuthUserProfile | null) => void
    accessToken: string
    setAccessToken: (accessToken: string) => void
    resetAccessToken: () => void
    reset: () => void
    setSession: (token: string, user: AuthUserProfile) => void
  }
}

export const useAuthStore = create<AuthState>()((set) => {
  const cookieState = getCookie(ACCESS_TOKEN_COOKIE)
  const initToken = cookieState ? JSON.parse(cookieState) : ''
  return {
    auth: {
      user: loadStoredUser(),
      setUser: (user) => {
        persistUser(user)
        set((state) => ({ ...state, auth: { ...state.auth, user } }))
      },
      accessToken: initToken,
      setAccessToken: (accessToken) =>
        set((state) => {
          setCookie(ACCESS_TOKEN_COOKIE, JSON.stringify(accessToken))
          return { ...state, auth: { ...state.auth, accessToken } }
        }),
      resetAccessToken: () =>
        set((state) => {
          removeCookie(ACCESS_TOKEN_COOKIE)
          return { ...state, auth: { ...state.auth, accessToken: '' } }
        }),
      reset: () =>
        set((state) => {
          removeCookie(ACCESS_TOKEN_COOKIE)
          persistUser(null)
          return {
            ...state,
            auth: { ...state.auth, user: null, accessToken: '' },
          }
        }),
      setSession: (token, user) => {
        setCookie(ACCESS_TOKEN_COOKIE, JSON.stringify(token))
        persistUser(user)
        set((state) => ({
          ...state,
          auth: { ...state.auth, accessToken: token, user },
        }))
      },
    },
  }
})
