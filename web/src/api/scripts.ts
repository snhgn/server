import { api } from '@/api'
import type { ScriptListItem, ScriptLogResult, ScriptSummary } from '@/data/scripts'

/** User：公开脚本列表 */
export const fetchScripts = () => api.get<{ scripts: ScriptListItem[] }>('/api/scripts')

/** User：脚本状态 */
export const fetchScriptStatus = (id: number) =>
  api.get<{
    id: number
    status: string
    enabled: boolean
    next_run: string | null
    last_run_status: string | null
    last_run_time: string | null
  }>(`/api/scripts/${id}/status`)

/** User：运行摘要 */
export const fetchScriptSummary = (id: number) =>
  api.get<ScriptSummary>(`/api/scripts/${id}/summary`)

/** Admin：完整列表 */
export const fetchAdminScripts = () => api.get<{ scripts: ScriptListItem[] }>('/api/admin/scripts')

/** Admin：运行摘要（含 private 脚本） */
export const fetchAdminScriptSummary = (id: number) =>
  api.get<ScriptSummary>(`/api/admin/scripts/${id}/summary`)

/** Admin：创建（command 手写 / code 由 AI 生成，二选一） */
export const createScript = (body: {
  name: string
  description: string
  type: string
  command?: string | null
  code?: string | null
  visibility: string
  cron?: string | null
  enabled: boolean
}) => api.post<ScriptListItem>('/api/admin/scripts', body)

/** Admin：更新 */
export const updateScript = (id: number, body: Record<string, any>) =>
  api.put<ScriptListItem>(`/api/admin/scripts/${id}`, body)

/** Admin：删除 */
export const deleteScript = (id: number) => api.delete<{ deleted: number }>(`/api/admin/scripts/${id}`)

/** Admin：手动运行 */
export const runScript = (id: number) =>
  api.post<{ run_id: number; status: string }>(`/api/admin/scripts/${id}/run`)

/** Admin：停止 */
export const stopScript = (id: number) =>
  api.post<{ stopped: number; killed: boolean }>(`/api/admin/scripts/${id}/stop`)

/** Admin：日志 */
export const fetchScriptLogs = (id: number, date?: string) =>
  api.get<ScriptLogResult>(`/api/admin/scripts/${id}/logs${date ? `?date=${date}` : ''}`)

/** Admin：AI 错误分析 */
export const analyzeScriptError = (id: number) =>
  api.post<{ script_id: number; analysis: string }>(`/api/admin/scripts/${id}/analyze-error`)

/** Admin：AI 生成脚本代码（提示词 → 代码） */
export const generateScriptCode = (body: { name: string; prompt: string }) =>
  api.post<{ code: string; syntax_ok: boolean; syntax_error: string; generator: string }>(
    '/api/admin/scripts/generate',
    body,
  )

/** Admin：AI 审查脚本代码（另一个 provider 交叉验证） */
export const reviewScriptCode = (body: { code: string; name?: string; description?: string }) =>
  api.post<{
    verdict: 'pass' | 'warn' | 'fail'
    issues: string[]
    summary: string
    reviewer: string
    syntax_ok: boolean
    syntax_error: string
  }>('/api/admin/scripts/review', body)
