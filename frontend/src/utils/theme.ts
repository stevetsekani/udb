export type Theme = 'dark' | 'light' | 'system'

export function resolveTheme(theme: Theme): 'dark' | 'light' {
  if (theme === 'system') {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  return theme
}

export function applyTheme(theme: Theme = 'dark') {
  const resolved = resolveTheme(theme)
  document.documentElement.setAttribute('data-theme', resolved)
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  if (meta) meta.content = resolved === 'dark' ? '#0d1117' : '#f5f7fa'
}

export function watchSystemTheme(callback: () => void): () => void {
  const mq = window.matchMedia('(prefers-color-scheme: light)')
  mq.addEventListener('change', callback)
  return () => mq.removeEventListener('change', callback)
}

