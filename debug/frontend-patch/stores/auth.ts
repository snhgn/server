import { computed, ref } from 'vue'

/**
 * 登录状态管理(Server-side Session + HttpOnly Cookie)
 *
 * - 凭证只存后端下发的 HttpOnly Cookie,前端不再向 localStorage 写任何登录凭证
 * - 应用启动时调 GET /api/auth/me 恢复当前用户(authReady 标记初始化完成,防 UI 闪烁)
 * - 旧版 localStorage JWT(snhgn_token)仅作一次性过渡:恢复成功或失败后即清除
 */

// 旧版 localStorage key(仅用于迁移清理)
const LEGACY_KEYS = ['snhgn_token', 'snhgn_role', 'snhgn_user']

interface CurrentUser {
  id: number
  username: string
  role: string
}

const user = ref<CurrentUser | null>(null)
// 过渡用:老用户的 JWT 在本次启动的 /me 请求中兜底一次,之后清空
const token = ref<string | null>(localStorage.getItem('snhgn_token'))
const authReady = ref(false)
let initPromise: Promise<void> | null = null

function cleanLegacyStorage() {
  LEGACY_KEYS.forEach((k) => localStorage.removeItem(k))
}

export function useAuth() {
  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isUser = computed(() => ['user', 'admin'].includes(user.value?.role ?? ''))
  const username = computed(() => user.value?.username ?? null)
  const role = computed(() => user.value?.role ?? null)

  /**
   * 启动时恢复登录状态:GET /api/auth/me。
   * - 200 → 恢复用户;401 → 未登录(不视为错误)
   * - 多处调用共享同一个 Promise;完成后 authReady = true
   */
  async function init(): Promise<void> {
    if (authReady.value) return
    if (!initPromise) {
      initPromise = (async () => {
        try {
          const headers: Record<string, string> = {}
          if (token.value) headers['Authorization'] = `Bearer ${token.value}`
          const resp = await fetch('/api/auth/me', {
            headers,
            credentials: 'same-origin',
          })
          if (resp.ok) {
            const data = await resp.json()
            if (data.authenticated && data.user) {
              user.value = {
                id: data.user.id,
                username: data.user.username,
                role: data.user.role,
              }
            }
          }
        } catch {
          /* 网络异常按未登录处理,不阻塞渲染 */
        } finally {
          // 旧 JWT 完成历史使命,此后登录状态完全由 HttpOnly Cookie 承载
          token.value = null
          cleanLegacyStorage()
          authReady.value = true
        }
      })()
    }
    return initPromise
  }

  async function login(u: string, password: string): Promise<void> {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ username: u, password }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || '登录失败')
    }
    const data = await resp.json()
    if (!data.success) {
      throw new Error('登录返回异常')
    }
    // Session 由响应 Set-Cookie 写入 HttpOnly Cookie;此处只保存非敏感的用户基本信息
    user.value = { id: data.user_id, username: data.username, role: data.role }
    token.value = null
  }

  /** 退出登录:服务端删除 Session + 清 Cookie,再清理本地状态 */
  async function logout(): Promise<void> {
    try {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })
    } catch {
      /* 后端不可达时也要清理本地状态 */
    }
    user.value = null
    token.value = null
    cleanLegacyStorage()
  }

  /** 兼容旧调用:等待状态恢复后返回是否已登录 */
  async function verify(): Promise<boolean> {
    await init()
    return isAuthenticated.value
  }

  return {
    user,
    token,
    username,
    role,
    authReady,
    isAuthenticated,
    isAdmin,
    isUser,
    init,
    login,
    logout,
    verify,
  }
}
