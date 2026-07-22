import { ApiClientError, readAccessToken } from './client'

export type SseHandlers = {
  onThinking?: (data: unknown) => void
  onResult?: (data: unknown) => void
  onReport?: (data: unknown) => void
  onDelta?: (data: { text?: string }) => void
  onDone?: (data: unknown) => void
  onPing?: (data: unknown) => void
  onError?: (data: {
    code?: string
    message?: string
    statusCode?: number
  }) => void
}

function parseSseChunk(chunk: string, handlers: SseHandlers): void {
  const blocks = chunk.split('\n\n')
  for (const block of blocks) {
    const trimmed = block.trim()
    if (!trimmed) continue

    let event = 'message'
    const dataLines: string[] = []
    for (const line of trimmed.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }
    if (!dataLines.length) continue

    let payload: unknown
    try {
      payload = JSON.parse(dataLines.join('\n'))
    } catch {
      throw new ApiClientError('PARSE_ERROR', 'SSE 数据无法解析为 JSON')
    }

    if (event === 'thinking') handlers.onThinking?.(payload)
    else if (event === 'result') handlers.onResult?.(payload)
    else if (event === 'report') handlers.onReport?.(payload)
    else if (event === 'delta')
      handlers.onDelta?.(payload as { text?: string })
    else if (event === 'done') handlers.onDone?.(payload)
    else if (event === 'ping') handlers.onPing?.(payload)
    else if (event === 'error')
      handlers.onError?.(
        payload as {
          code?: string
          message?: string
          statusCode?: number
        }
      )
  }
}

export async function postSse(
  url: string,
  init: {
    method?: string
    body?: BodyInit
    headers?: Record<string, string>
    skipAuth?: boolean
  },
  handlers: SseHandlers
): Promise<void> {
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    ...init.headers,
  }
  if (!init.skipAuth) {
    const token = readAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(url, {
    method: init.method ?? 'POST',
    headers,
    body: init.body,
  })

  if (!response.ok) {
    const txt = await response.text()
    try {
      const body = JSON.parse(txt) as { code?: string; message?: string }
      throw new ApiClientError(
        body.code ?? 'REQUEST_FAILED',
        body.message ?? `HTTP ${response.status}`
      )
    } catch (e) {
      if (e instanceof ApiClientError) throw e
      throw new ApiClientError(
        'REQUEST_FAILED',
        txt || `HTTP ${response.status}`
      )
    }
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new ApiClientError('INVALID_BODY', '响应不支持流式读取')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let streamError: ApiClientError | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lastDelimiter = buffer.lastIndexOf('\n\n')
    if (lastDelimiter < 0) continue

    const complete = buffer.slice(0, lastDelimiter + 2)
    buffer = buffer.slice(lastDelimiter + 2)

    const prevOnError = handlers.onError
    handlers.onError = (data) => {
      streamError = new ApiClientError(
        data.code ?? 'UNKNOWN',
        data.message ?? '请求失败'
      )
      prevOnError?.(data)
    }
    parseSseChunk(complete, handlers)
    handlers.onError = prevOnError
    if (streamError) throw streamError
  }

  if (buffer.trim()) {
    parseSseChunk(buffer, handlers)
  }
  if (streamError) throw streamError
}
