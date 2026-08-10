import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  HardDrive,
  History,
  Search,
  XCircle,
} from 'lucide-react'
import { useAppStore } from '../store/AppStore'
import { DownloadCard } from '../components/DownloadCard'
import { EmptyState, formatBytes, formatDate } from '../components/ui'
import type { ClientKey } from '../types'

interface Props {
  onSearch: (query?: string, client?: ClientKey) => void
}

export function DashboardPage({ onSearch }: Props) {
  const { downloads, historyStats, settings, version, ffmpeg } = useAppStore()
  const [query, setQuery] = useState('')
  const [client, setClient] = useState<ClientKey>('kisskh')
  const navigate = useNavigate()

  const active = downloads.filter((d) => ['queued', 'preparing', 'downloading', 'retrying'].includes(d.status))
  const completed = downloads.filter((d) => d.status === 'completed')
  const recentHistory = historyStats?.counts ?? { completed: 0, failed: 0, cancelled: 0, other: 0 }
  const totalBytes = historyStats?.total_downloaded_bytes ?? 0

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) onSearch(query.trim(), client)
  }

  return (
    <div className="page">
      {/* Hero / search */}
      <div className="search-hero">
        <h1>Download Anime, Movies &amp; Shows</h1>
        <p>Search your favourite series and let UDB grab every episode for you.</p>
        <form className="search-bar" onSubmit={submit}>
          <input
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search or paste a title…"
            autoFocus
          />
          <button className="btn btn-primary btn-lg" type="submit">
            <Search /> Search
          </button>
        </form>
        <div className="source-toggle">
          <button className={client === 'kisskh' ? 'active' : ''} onClick={() => setClient('kisskh')}>
            KissKh · All in one
          </button>
          <button className={client === 'animepahe' ? 'active' : ''} onClick={() => setClient('animepahe')}>
            AnimePahe · Anime
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
            <Activity />
          </div>
          <div className="stat-value">{active.length}</div>
          <div className="stat-label">Active downloads</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--success-soft)', color: 'var(--success)' }}>
            <CheckCircle2 />
          </div>
          <div className="stat-value">{recentHistory.completed}</div>
          <div className="stat-label">Completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--danger-soft)', color: 'var(--danger)' }}>
            <XCircle />
          </div>
          <div className="stat-value">{recentHistory.failed}</div>
          <div className="stat-label">Failed</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--info)', color: '#fff' }}>
            <HardDrive />
          </div>
          <div className="stat-value">{formatBytes(totalBytes)}</div>
          <div className="stat-label">Total downloaded</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* Active downloads */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ fontSize: 16 }}>Active downloads</h2>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/downloads')}>
              View all <ArrowRight style={{ width: 13, height: 13 }} />
            </button>
          </div>
          {active.length === 0 ? (
            <div className="card">
              <EmptyState
                icon={<Download />}
                title="Nothing downloading"
                subtitle="Search for a title above to start downloading"
              />
            </div>
          ) : (
            active.slice(0, 4).map((job) => <DownloadCard key={job.id} job={job} />)
          )}
        </div>

        {/* Right rail */}
        <div style={{ width: 280, flexShrink: 0 }}>
          <div className="card" style={{ marginBottom: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>Recent activity</div>
            {downloads.length === 0 ? (
              <div className="faint" style={{ fontSize: 12.5 }}>No downloads yet.</div>
            ) : (
              downloads.slice(0, 6).map((d) => (
                <div key={d.id} className="flex" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {d.title}
                    </div>
                    <div className="faint" style={{ fontSize: 11 }}>{formatDate(d.created)}</div>
                  </div>
                  <span className={`status-pill ${d.status}`}>
                    <span className="dot" />
                    {d.status}
                  </span>
                </div>
              ))
            )}
          </div>

          {completed.length > 0 && (
            <div className="card">
              <div className="flex" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>Completed</div>
                <button className="btn btn-ghost btn-sm" onClick={() => navigate('/history')}>
                  <History style={{ width: 13, height: 13 }} />
                </button>
              </div>
              {completed.slice(0, 3).map((d) => (
                <div key={d.id} className="flex" style={{ padding: '4px 0' }}>
                  <Clock style={{ width: 14, height: 14, color: 'var(--success)' }} />
                  <span style={{ fontSize: 12.5 }}>{d.title}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {settings?.download_dir && (
        <div className="faint" style={{ marginTop: 24, fontSize: 12 }}>
          Downloads saved to <span className="mono">{settings.download_dir}</span> · UDB v{version ?? '…'}
          {ffmpeg && ` · FFmpeg ${ffmpeg.version}`}
        </div>
      )}
    </div>
  )
}

