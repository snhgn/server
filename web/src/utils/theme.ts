export type ThemeMode = 'auto' | 'light' | 'dark'

export function getStoredThemeMode(): ThemeMode {
  return (localStorage.getItem('bjfu-theme-mode') || localStorage.getItem('snhgn-theme') || 'auto') as ThemeMode
}

export function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'dark') return 'dark'
  if (mode === 'light') return 'light'
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(mode?: ThemeMode) {
  const m = mode || getStoredThemeMode()
  const resolved = resolveTheme(m)

  localStorage.setItem('bjfu-theme-mode', m)
  localStorage.setItem('snhgn-theme', resolved)

  document.documentElement.setAttribute('data-theme', resolved)
  if (resolved === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

export function initTheme() {
  applyTheme()
  if (typeof window !== 'undefined' && window.matchMedia) {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', () => {
      if (getStoredThemeMode() === 'auto') {
        applyTheme('auto')
      }
    })
  }
}
