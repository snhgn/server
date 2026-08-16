import { useAuth } from './stores/auth'
import router from './router'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** 401 统一处理:清理登录状态;若当前在受保护页则跳登录页(带回来路径) */
function handle401(): never {
  const { logout } = useAuth()
  logout()
  const current = router.currentRoute.value
  if (current.meta.requiresAuth) {
    router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
  throw new ApiError(401, '未登录或登录已过期')
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { token } = useAuth()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token.value) {
    headers['Authorization'] = `Bearer ${token.value}`
  }

  const resp = await fetch(path, { ...options, headers, credentials: 'same-origin' })

  // 401：清除登录状态并跳转登录页
  if (resp.status === 401) {
    handle401()
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new ApiError(resp.status, err.detail || `请求失败 (${resp.status})`)
  }

  return resp.json()
}

export const api = {
  get: <T = any>(path: string) => apiFetch<T>(path),
  post: <T = any>(path: string, body?: any) =>
    apiFetch<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T = any>(path: string, body?: any) =>
    apiFetch<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T = any>(path: string, body?: any) =>
    apiFetch<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    }),
  delete: <T = any>(path: string) =>
    apiFetch<T>(path, { method: 'DELETE' }),
  /**
   * 上传文件（multipart/form-data），返回 JSON
   */
  upload: async <T = any>(path: string, file: File, extra?: Record<string, string>) => {
    const { token } = useAuth()
    const form = new FormData()
    form.append('file', file)
    if (extra) {
      for (const [k, v] of Object.entries(extra)) form.append(k, v)
    }
    const headers: Record<string, string> = {}
    if (token.value) headers['Authorization'] = `Bearer ${token.value}`
    const resp = await fetch(path, {
      method: 'POST',
      headers,
      body: form,
      credentials: 'same-origin',
    })
    if (resp.status === 401) {
      handle401()
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new ApiError(resp.status, err.detail || `上传失败 (${resp.status})`)
    }
    return resp.json() as Promise<T>
  },
}

/**
 * SSE 流式 POST：消费 text/event-stream，逐事件回调。
 * 使用 fetch + ReadableStream 手动解析（避免 EventSource 不支持 POST 的限制）。
 */
export interface SSEHandlers {
  onStatus?: (data: any) => void
  onToken?: (text: string) => void
  onComplete?: (data: any) => void
  onError?: (data: any) => void
  onUnknown?: (event: string, data: any) => void
}

export async function apiStreamPost(
  path: string,
  body: any,
  handlers: SSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const { token } = useAuth()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (token.value) headers['Authorization'] = `Bearer ${token.value}`

  const resp = await fetch(path, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
    credentials: 'same-origin',
  })

  if (resp.status === 401) {
    handle401()
  }
  if (!resp.ok || !resp.body) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new ApiError(resp.status, err.detail || `流式请求失败 (${resp.status})`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  // SSE 事件以 \n\n 分隔；每个事件包含 event: xxx 和 data: yyy 行
  const parseEvent = (raw: string) => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of raw.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    const dataStr = dataLines.join('\n')
    let data: any = dataStr
    try {
      data = JSON.parse(dataStr)
    } catch {
      /* 保留原始字符串 */
    }
    return { event, data }
  }

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // 按事件分隔符切分
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        if (!raw.trim()) continue
        const { event, data } = parseEvent(raw)
        switch (event) {
          case 'status':
            handlers.onStatus?.(data)
            break
          case 'token':
            handlers.onToken?.(typeof data === 'string' ? data : data?.text || '')
            break
          case 'complete':
            handlers.onComplete?.(data)
            return
          case 'error':
            handlers.onError?.(data)
            return
          default:
            handlers.onUnknown?.(event, data)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
