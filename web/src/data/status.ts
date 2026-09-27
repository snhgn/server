export interface StatusItem {
  label: string
  value: string
  state: 'online' | 'ready' | 'active' | 'idle'
}

/** Home 首页节点状态指标 */
export const statusList: StatusItem[] = [
  { label: 'Host Node', value: 'snhgn-primary', state: 'online' },
  { label: 'System', value: 'Ubuntu 22.04 LTS', state: 'online' },
  { label: 'AI Engine', value: 'Dual-Engine Ready', state: 'ready' },
  { label: 'Network', value: 'Cloudflare Tunnel', state: 'active' },
]
