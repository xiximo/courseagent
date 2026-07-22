/** 与后端 ApiResponse 一致 */

export type ApiEnvelope<T> = {

  ok: boolean

  code: string

  message?: string | null

  data?: T

}



export class ApiClientError extends Error {

  readonly code: string



  constructor(code: string, message: string) {

    super(message)

    this.code = code

    this.name = 'ApiClientError'

  }

}



export function getApiErrorMessage(error: unknown, fallback: string): string {

  if (error instanceof ApiClientError && error.message) {

    return error.message

  }

  return fallback

}



export function isNotImplementedError(error: unknown): boolean {

  if (error instanceof ApiClientError && error.code === 'NOT_IMPLEMENTED') {

    return true

  }

  if (error instanceof Error && /尚未实现|NOT_IMPLEMENTED/i.test(error.message)) {

    return true

  }

  return false

}



async function parseJson<T>(response: Response): Promise<T | null> {

  const txt = await response.text()

  if (!txt.length) return null

  try {

    return JSON.parse(txt) as T

  } catch {

    throw new ApiClientError('PARSE_ERROR', '响应无法解析为 JSON')

  }

}



export async function readEnvelope<T>(response: Response): Promise<T> {

  if (response.status === 204) {

    return undefined as T

  }

  const body = await parseJson<ApiEnvelope<T>>(response)

  if (!body || typeof body.ok !== 'boolean') {

    throw new ApiClientError('INVALID_BODY', `HTTP ${response.status}`)

  }

  if (!body.ok) {

    throw new ApiClientError(body.code, body.message ?? body.code ?? '请求失败')

  }

  return body.data as T

}



export const ACCESS_TOKEN_COOKIE = 'taixing_access_token'



export function readAccessToken(): string {

  if (typeof document === 'undefined') return ''

  const match = document.cookie.match(

    new RegExp(`(?:^|; )${ACCESS_TOKEN_COOKIE}=([^;]*)`)

  )

  if (!match?.[1]) return ''

  try {

    return JSON.parse(decodeURIComponent(match[1])) as string

  } catch {

    return ''

  }

}



function redirectToSignIn() {

  if (typeof window === 'undefined') return

  if (window.location.pathname.startsWith('/sign-in')) return

  document.cookie = `${ACCESS_TOKEN_COOKIE}=; Max-Age=0; path=/`

  localStorage.removeItem('taixing_auth_user')

  const redirectPath = `${window.location.pathname}${window.location.search}${window.location.hash}`

  const redirect = encodeURIComponent(redirectPath)

  window.location.assign(`/sign-in?redirect=${redirect}`)

}



export type ApiFetchOptions = {

  skipAuth?: boolean

}



export async function apiFetch(

  method: string,

  url: string,

  body?: unknown,

  options?: ApiFetchOptions

): Promise<Response> {

  const headers: Record<string, string> = { Accept: 'application/json' }

  if (body !== undefined) {

    headers['Content-Type'] = 'application/json'

  }

  if (!options?.skipAuth) {

    const token = readAccessToken()

    if (token) {

      headers.Authorization = `Bearer ${token}`

    }

  }



  const init: RequestInit = {

    method,

    headers,

    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),

  }

  const response = await fetch(url, init)



  if (

    response.status === 401 &&

    !options?.skipAuth &&

    !url.includes('/auth/login')

  ) {

    redirectToSignIn()

  }



  return response

}



export async function apiFetchForm(

  method: string,

  url: string,

  form: FormData,

  options?: ApiFetchOptions

): Promise<Response> {

  const headers: Record<string, string> = { Accept: 'application/json' }

  if (!options?.skipAuth) {

    const token = readAccessToken()

    if (token) {

      headers.Authorization = `Bearer ${token}`

    }

  }

  const response = await fetch(url, { method, headers, body: form })

  if (

    response.status === 401 &&

    !options?.skipAuth &&

    !url.includes('/auth/login')

  ) {

    redirectToSignIn()

  }

  return response

}


