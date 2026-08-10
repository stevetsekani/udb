// Shared TypeScript types mirroring the backend API payloads.

export type ClientKey = 'animepahe' | 'kisskh'

export type DownloadStatus =
  | 'queued'
  | 'preparing'
  | 'downloading'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'retrying'

export interface SearchResult {
  id: string
  index: number
  title: string
  year: string | null
  type: string
  episodes: string | number | null
  status: string
  detail: string
}

export interface SearchResponse {
  session_id: string | null
  client: ClientKey
  query: string
  results: SearchResult[]
}

export interface EpisodeItem {
  episode: string | number
  name: string
  extra: string
}

export interface InspectResponse {
  episode_session: string
  client: ClientKey
  title: string
  year: string | number | null
  episodes: EpisodeItem[]
  total_episodes: number
  season_ranges: Record<string, { start: number; end: number }>
  is_tv: boolean
}

export interface EpisodeSelection {
  start?: number
  end?: number
  specific_no?: number[]
}

export interface DownloadJob {
  id: string
  batch_id: string
  title: string
  episode: string | number | null
  season: string | number | null
  quality: string
  client: ClientKey
  status: DownloadStatus
  progress: number
  speed: number
  speed_str: string
  completed: number
  total: number
  unit: string
  destination: string
  error: string
  episodeName: string
  output_path: string
  created: string
  started: string | null
  finished: string | null
}

export interface HistoryRecord {
  id: string
  title: string
  episode: string | number | null
  season: string | number | null
  quality: string
  source: string
  status: DownloadStatus
  destination: string
  file_size: string
  date: string
  error: string
  client: string
  extra: { ep_details?: unknown }
}

export interface HistoryStats {
  counts: { completed: number; failed: number; cancelled: number; other: number }
  total_downloaded_bytes: number
}

export interface AppSettings {
  download_dir: string
  temp_download_dir: string
  concurrency_per_file: string | number
  request_timeout: number
  max_parallel_downloads: number
  log_level: string
  log_retention_days: number
  log_backup_count: number
  log_max_size_kb: number
  animepahe_download_dir: string | null
  animepahe_request_timeout: number
  animepahe_selector: string
  kisskh_download_dir: string | null
  kisskh_request_timeout: number
  kisskh_selector: string
  kisskh_search_limit: number
  theme: 'dark' | 'light' | 'system'
  preferred_quality: string
  notifications: boolean
  check_updates_on_startup: boolean
  start_minimized: boolean
  ffmpeg_configured_path: string | null
}

export interface FFmpegInfo {
  available: boolean
  path: string | null
  version: string
  version_tuple: number[]
  min_required: string
  valid: boolean
  source: 'bundled' | 'configured' | 'system' | 'missing'
}

export interface SystemInfo {
  os: string
  os_release: string
  arch: string
  python: string
  frozen: boolean
  hostname: string
}

export interface DownloadProgressEvent {
  type: 'download_progress'
  download_id: string
  progress: number
  speed: string
  downloaded: number
  total: number
  unit: string
}

export interface DownloadStatusEvent {
  type: 'download_status'
  download_id: string
  status: DownloadStatus
  progress: number
}

export interface VersionInfo {
  version: string
  app: string
}

export interface LogEntry {
  name: string
  content: string
}

