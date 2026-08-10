import { useEffect, useMemo, useState } from 'react'
import { Download, FolderOpen, RefreshCw, Search, Trash2 } from 'lucide-react'
import { api } from '../api'
import { useAppStore } from '../store/AppStore'
import { EmptyState, StatusPill, formatDate } from '../components/ui'
import type { HistoryRecord } from '../types'

export function HistoryPage() {
  const { history, refreshHistory, refreshStats, notify } = useAppStore()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [confirmClear, setConfirmClear] = useState(false)

  useEffect(() => {
    refreshHistory()
    refreshStats()
  }, [refreshHistory, refreshStats])

  const filtered = useMemo(() => {
    let items = history
    if (status) items = items.filter((h) => h.status === status)
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      items = items.filter((h) => (h.title || '').toLowerCase().includes(q) || (h.episode || '').toString().includes(q))
    }
    const sorted = [...items]
    sorted.sort((a, b) => {
      const av = a[sortBy as keyof HistoryRecord] ?? ''
      const bv = b[sortBy as keyof HistoryRecord] ?? ''
      const cmp = typeof av === 'number' ? av - (bv as number) : String(av).localeCompare(String(bv))
      return order === 'asc' ? cmp : -cmp
    })
    return sorted
  }, [history, search, status, sortBy, order])

  const toggleSort = (key: string) => {
    if (sortBy === key) setOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
    else {
      setSortBy(key)
      setOrder('desc')
    }
  }

  const clearAll = async () => {
    try {
      await api.clearHistory()
      notify('History cleared', 'success')
      refreshHistory()
      refreshStats()
      setConfirmClear(false)
    } catch (err) {
      notify('Failed to clear history', 'error')
    }
  }

  const retry = async (id: string) => {
    try {
      await api.retryHistory(id)
      notify('Download restarted', 'success')
      refreshHistory()
    } catch (err) {
      notify('This download cannot be retried automatically. Please re-add it.', 'error')
    }
  }

  const remove = async (id: string) => {
    try {
      await api.deleteHistory(id)
      refreshHistory()
      refreshStats()
    } catch {
      notify('Failed to remove record', 'error')
    }
  }

  return (
    <div className="page">
      <div className="page-header flex" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1>History</h1>
          <p>Every download attempt, persisted locally.</p>
        </div>
        {history.length > 0 && (
          <button className="btn btn-danger" onClick={() => setConfirmClear(true)}>
            <Trash2 /> Clear history
          </button>
        )}
      </div>

      <div className="flex" style={{ marginBottom: 16, gap: 10, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200, maxWidth: 320 }}>
          <Search style={{ position: 'absolute', left: 10, top: 9, width: 15, height: 15, color: 'var(--text-faint)' }} />
          <input
            className="input"
            style={{ paddingLeft: 32 }}
            placeholder="Search title or episode…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="select" style={{ width: 150 }} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {confirmClear && (
        <div className="card" style={{ borderColor: 'var(--danger)', marginBottom: 14 }}>
          <div className="flex" style={{ justifyContent: 'space-between' }}>
            <span>Clear all {history.length} history records? This cannot be undone.</span>
            <div className="flex">
              <button className="btn btn-sm" onClick={() => setConfirmClear(false)}>Cancel</button>
              <button className="btn btn-danger btn-sm" onClick={clearAll}>Clear all</button>
            </div>
          </div>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<Download />}
            title="No history yet"
            subtitle="Completed and failed downloads will appear here"
          />
        </div>
      ) : (
        <div className="card" style={{ padding: 8, overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th onClick={() => toggleSort('title')}>Title</th>
                <th>Episode</th>
                <th onClick={() => toggleSort('quality')}>Quality</th>
                <th>Source</th>
                <th onClick={() => toggleSort('status')}>Status</th>
                <th>Size</th>
                <th onClick={() => toggleSort('date')}>Date</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((h) => (
                <tr key={h.id}>
                  <td style={{ fontWeight: 600, maxWidth: 220, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {h.title}
                  </td>
                  <td className="muted">{h.episode != null ? `Ep ${h.episode}` : '—'}</td>
                  <td className="muted">{h.quality ? `${h.quality}P` : '—'}</td>
                  <td className="muted">{h.source}</td>
                  <td>
                    <StatusPill status={h.status} />
                  </td>
                  <td className="muted">{h.file_size || '—'}</td>
                  <td className="muted" style={{ whiteSpace: 'nowrap' }}>{formatDate(h.date)}</td>
                  <td>
                    <div className="actions">
                      {h.status === 'failed' && (
                        <button className="icon-button" title="Retry" onClick={() => retry(h.id)}>
                          <RefreshCw />
                        </button>
                      )}
                      <button className="icon-button" title="Open containing folder" onClick={() => openFolder(h.destination)}>
                        <FolderOpen />
                      </button>
                      <button className="icon-button" title="Remove from history" onClick={() => remove(h.id)}>
                        <Trash2 />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function openFolder(path: string) {
  // Best-effort: reuse the API open-folder endpoint via a temporary mechanism.
  // The backend exposes no generic open-folder for arbitrary paths; fall back to
  // a platform command injected by the desktop shell.
  const win = window as unknown as { udbOpenFolder?: (p: string) => boolean }
  if (win.udbOpenFolder) {
    win.udbOpenFolder(path)
    return
  }
  // In browser dev, attempt a location change to the file path (works on some systems)
  try {
    window.location.href = `file://${path.replace(/\\/g, '/')}`
  } catch {
    // ignore
  }
}

