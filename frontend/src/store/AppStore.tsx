import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, connectEvents, ApiError } from '../api'
import type { BackendEvent } from '../api'
import type {
  AppSettings,
  DownloadJob,
  FFmpegInfo,
  HistoryRecord,
  HistoryStats,
  SystemInfo,
} from '../types'

interface Toast {
  id: number
  kind: 'success' | 'error' | 'info'
  message: string
}

interface AppStoreValue {
  version: string | null
  system: SystemInfo | null
  ffmpeg: FFmpegInfo | null
  settings: AppSettings | null
  downloads: DownloadJob[]
  history: HistoryRecord[]
  historyStats: HistoryStats | null
  sseConnected: boolean
  toasts: Toast[]

  refreshDownloads: () => Promise<void>
  refreshHistory: () => Promise<void>
  refreshSettings: () => Promise<AppSettings | undefined>
  refreshStats: () => Promise<void>
  refreshAll: () => Promise<void>

  showToast: (message: string, kind?: Toast['kind']) => void
  dismissToast: (id: number) => void
  notify: (message: string, kind?: Toast['kind']) => void
}

const AppStoreContext = createContext<AppStoreValue | null>(null)

export function AppStoreProvider({ children }: { children: React.ReactNode }) {
  const [version, setVersion] = useState<string | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [ffmpeg, setFfmpeg] = useState<FFmpegInfo | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [downloads, setDownloads] = useState<DownloadJob[]>([])
  const [history, setHistory] = useState<HistoryRecord[]>([])
  const [historyStats, setHistoryStats] = useState<HistoryStats | null>(null)
  const [sseConnected, setSseConnected] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(0)
  const settingsRef = useRef<AppSettings | null>(null)

  const showToast = useCallback((message: string, kind: Toast['kind'] = 'info') => {
    const id = ++toastId.current
    setToasts((prev) => [...prev.slice(-3), { id, kind, message }])
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  const notify = useCallback(
    (message: string, kind: Toast['kind'] = 'info') => {
      showToast(message, kind)
      const s = settingsRef.current
      if (s && s.notifications && 'Notification' in window) {
        try {
          if (Notification.permission === 'granted') {
            new Notification('UDB', { body: message })
          } else if (Notification.permission === 'default') {
            Notification.requestPermission()
          }
        } catch {
          // notifications unsupported
        }
      }
    },
    [showToast],
  )

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const refreshDownloads = useCallback(async () => {
    try {
      const res = await api.downloads()
      setDownloads(res.downloads)
    } catch (err) {
      console.error('Failed to load downloads', err)
    }
  }, [])

  const refreshHistory = useCallback(async () => {
    try {
      const res = await api.history({ limit: 200 })
      setHistory(res.history)
    } catch (err) {
      console.error('Failed to load history', err)
    }
  }, [])

  const refreshStats = useCallback(async () => {
    try {
      setHistoryStats(await api.historyStats())
    } catch {
      // ignore
    }
  }, [])

  const refreshSettings = useCallback(async () => {
    try {
      const s = await api.settings()
      settingsRef.current = s
      setSettings(s)
      return s
    } catch (err) {
      console.error('Failed to load settings', err)
    }
  }, [])

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshDownloads(), refreshHistory(), refreshSettings(), refreshStats()])
  }, [refreshDownloads, refreshHistory, refreshSettings, refreshStats])

  // Initial load
  useEffect(() => {
    api.version().then((v) => setVersion(v.version)).catch(() => {})
    api.system().then(setSystem).catch(() => {})
    api.ffmpeg().then(setFfmpeg).catch(() => {})
    refreshAll()
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // SSE live updates
  useEffect(() => {
    const disconnect = connectEvents(
      (event: BackendEvent) => {
        if (event.type === 'download_progress') {
          setDownloads((prev) =>
            prev.map((d) =>
              d.id === (event as { download_id: string }).download_id
                ? {
                    ...d,
                    progress: Number((event as { progress: number }).progress),
                    speed_str: (event as { speed: string }).speed,
                    completed: Number((event as { downloaded: number }).downloaded),
                    total: Number((event as { total: number }).total),
                    unit: (event as { unit: string }).unit,
                  }
                : d,
            ),
          )
        } else if (event.type === 'download_status') {
          const evt = event as { download_id: string; status: string }
          setDownloads((prev) =>
            prev.map((d) => (d.id === evt.download_id ? { ...d, status: evt.status as DownloadJob['status'] } : d)),
          )
          // On terminal states, refresh history + stats and show a toast
          if (['completed', 'failed', 'cancelled'].includes(evt.status)) {
            refreshHistory()
            refreshStats()
            const job = downloadsRef.current.find((d) => d.id === evt.download_id)
            if (job) {
              if (evt.status === 'completed') notify(`${job.title} — download completed`, 'success')
              else if (evt.status === 'failed') notify(`${job.title} — download failed`, 'error')
            }
          }
        }
      },
      setSseConnected,
    )
    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const downloadsRef = useRef<DownloadJob[]>([])
  downloadsRef.current = downloads

  const value = useMemo<AppStoreValue>(
    () => ({
      version,
      system,
      ffmpeg,
      settings,
      downloads,
      history,
      historyStats,
      sseConnected,
      toasts,
      refreshDownloads,
      refreshHistory,
      refreshSettings,
      refreshStats,
      refreshAll,
      showToast,
      dismissToast,
      notify,
    }),
    [version, system, ffmpeg, settings, downloads, history, historyStats, sseConnected, toasts,
     refreshDownloads, refreshHistory, refreshSettings, refreshStats, refreshAll, showToast, dismissToast, notify],
  )

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}

export function useAppStore(): AppStoreValue {
  const ctx = useContext(AppStoreContext)
  if (!ctx) throw new Error('useAppStore must be used within AppStoreProvider')
  return ctx
}

export { ApiError }

