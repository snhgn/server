export type ScriptType = 'crawler' | 'ai_task' | 'service' | 'automation'
export type ScriptStatus = 'running' | 'waiting' | 'failed' | 'disabled'
export type ScriptVisibility = 'public' | 'private'

export interface ScriptLastRun {
  start_time: string
  end_time: string | null
  status: string
  duration_ms: number | null
}

export interface ScriptListItem {
  id: number
  name: string
  description: string
  type: ScriptType
  status: ScriptStatus
  visibility: ScriptVisibility
  enabled: boolean
  /** Admin 字段 */
  command?: string
  cron?: string | null
  owner_id?: number
  created_at?: string
  next_run?: string | null
  last_run?: ScriptLastRun | null
}

export interface ScriptRunRecord {
  id: number
  script_id: number
  trigger: string
  start_time: string
  end_time: string | null
  status: 'running' | 'success' | 'failed'
  duration_ms: number | null
}

export interface ScriptSummary {
  script_id: number
  total_runs: number
  success: number
  failed: number
  avg_duration_ms: number | null
  recent_runs: ScriptRunRecord[]
}

export interface ScriptLogResult {
  date: string
  path: string
  lines: string[]
  latest_run: {
    id: number
    status: string
    start_time: string
    end_time: string | null
    duration_ms: number | null
    output?: string
    error?: string
  } | null
}

export const TYPE_LABELS: Record<ScriptType, string> = {
  crawler: 'Crawler',
  ai_task: 'AI Task',
  service: 'Service',
  automation: 'Automation',
}

export const STATUS_LABELS: Record<ScriptStatus, string> = {
  running: 'Running',
  waiting: 'Waiting',
  failed: 'Failed',
  disabled: 'Disabled',
}
