// API client for the local UDB backend.
//
// The backend binds strictly to 127.0.0.1. In production the desktop shell
// serves the frontend from the same origin, so relative /api paths work. In
// dev the Vite proxy forwards /api to the backend.

import type {
  AppSettings,
  ClientKey,
  DownloadJob,
  EpisodeSelection,
  FFmpegInfo,
  HistoryRecord,
  HistoryStats,
  InspectResponse,
  LogEntry,
  SearchResponse,
  SystemInfo,
  VersionInfo,
} from '../types'

const API_BASE = '/api'

function authToken(): string {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="udb-token"]')
  return meta?.content || ''
}

export class ApiError extends Error {
  status: number
  details: string
  constructor(message: string, status: number, details = '') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  const token = authToken()
  if (token) headers['X-UDB-Token'] = token

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    let details = ''
    try {
      const data = await res.json()
      if (data?.error?.message) message = data.error.message
      if (data?.error?.details) details = data.error.details
    } catch {
      // non-JSON error body
    }
    throw new ApiError(message, res.status, details)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  // meta
  health: () => request<{ status: string }>('/health'),
  version: () => request<VersionInfo>('/version'),
  system: () => request<SystemInfo>('/system'),
  ffmpeg: () => request<FFmpegInfo>('/ffmpeg'),
  config: () => request<{ version: string; token_required: boolean; token: string }>('/config'),

  // search / inspect
  search: (client: ClientKey, query: string) =>
    request<SearchResponse>('/search', { method: 'POST', body: JSON.stringify({ client, query }) }),
  inspect: (client: ClientKey, result_id: string) =>
    request<InspectResponse>('/inspect', { method: 'POST', body: JSON.stringify({ client, result_id }) }),

  // downloads
  createDownload: (payload: {
    episode_session: string
    resolution: string
    selection: EpisodeSelection | Record<string, EpisodeSelection>
    download_dir?: string
  }) => request<{ jobs: DownloadJob[]; created: number }>('/download', { method: 'POST', body: JSON.stringify(payload) }),
  downloads: (status?: string) =>
    request<{ downloads: DownloadJob[] }>(`/downloads${status ? `?status=${status}` : ''}`),
  download: (id: string) => request<DownloadJob>(`/downloads/${id}`),
  cancelDownload: (id: string) => request<{ ok: boolean }>(`/downloads/${id}/cancel`, { method: 'POST' }),
  retryDownload: (id: string) => request<{ ok: boolean }>(`/downloads/${id}/retry`, { method: 'POST' }),
  removeDownload: (id: string) => request<{ ok: boolean }>(`/downloads/${id}`, { method: 'DELETE' }),
  openFolder: (id: string) => request<{ ok: boolean }>(`/downloads/${id}/open-folder`, { method: 'POST' }),

  // history
  history: (params?: { status?: string; search?: string; limit?: number; sort_by?: string; order?: string }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.search) qs.set('search', params.search)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.sort_by) qs.set('sort_by', params.sort_by)
    if (params?.order) qs.set('order', params.order)
    const q = qs.toString()
    return request<{ history: HistoryRecord[] }>(`/history${q ? `?${q}` : ''}`)
  },
  historyStats: () => request<HistoryStats>('/history/stats'),
  deleteHistory: (id: string) => request<{ ok: boolean }>(`/history/${id}`, { method: 'DELETE' }),
  clearHistory: () => request<{ ok: boolean }>('/history', { method: 'DELETE' }),
  retryHistory: (id: string) => request<{ ok: boolean; job?: DownloadJob }>(`/history/${id}/retry`, { method: 'POST' }),

  // settings
  settings: () => request<AppSettings>('/settings'),
  updateSettings: (patch: Partial<AppSettings>) =>
    request<AppSettings>('/settings', { method: 'PUT', body: JSON.stringify(patch) }),
  logs: () => request<{ logs: LogEntry[] }>('/logs'),
}

// --------------------------------------------------------------------------- //
// Server-Sent Events                                                          //
// --------------------------------------------------------------------------- //
export type BackendEvent =
  | { type: 'download_progress'; download_id: string; progress: number; speed: string; downloaded: number; total: number; unit: string }
  | { type: 'download_status'; download_id: string; status: string; progress: number }
  | { type: string; [key: string]: unknown }

export function connectEvents(onEvent: (event: BackendEvent) => void, onStatus?: (connected: boolean) => void): () => void {
  let closed = false
  let retryTimer: number | undefined

  const connect = () => {
    const token = authToken()
    const url = `${API_BASE}/events${token ? `?token=${encodeURIComponent(token)}` : ''}`
    const source = new EventSource(url)
    onStatus?.(true)

    const openHandlers = ['download_progress', 'download_status'] as const
    const handle = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        onEvent(data as BackendEvent)
      } catch {
        // ignore malformed frames
      }
    }
    openHandlers.forEach((type) => source.addEventListener(type, handle))
    source.addEventListener('hello', () => onStatus?.(true))

    source.onerror = () => {
      source.close()
      onStatus?.(false)
      if (!closed) {
        // exponential backoff capped at 10s
        retryTimer = window.setTimeout(connect, 2000)
      }
    }
  }

  connect()

  return () => {
    closed = true
    if (retryTimer) window.clearTimeout(retryTimer)
  }
}

