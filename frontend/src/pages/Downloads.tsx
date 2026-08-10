import { useState } from 'react'
import { Inbox } from 'lucide-react'
import { useAppStore } from '../store/AppStore'
import { DownloadCard } from '../components/DownloadCard'
import { EmptyState } from '../components/ui'

type Filter = 'all' | 'active' | 'completed' | 'failed' | 'cancelled'

export function DownloadsPage() {
  const { downloads } = useAppStore()
  const [filter, setFilter] = useState<Filter>('all')

  const filtered = downloads.filter((d) => {
    if (filter === 'all') return true
    if (filter === 'active') return ['queued', 'preparing', 'downloading', 'retrying'].includes(d.status)
    return d.status === filter
  })

  const counts = {
    all: downloads.length,
    active: downloads.filter((d) => ['queued', 'preparing', 'downloading', 'retrying'].includes(d.status)).length,
    completed: downloads.filter((d) => d.status === 'completed').length,
    failed: downloads.filter((d) => d.status === 'failed').length,
    cancelled: downloads.filter((d) => d.status === 'cancelled').length,
  }

  const tabs: { key: Filter; label: string }[] = [
    { key: 'all', label: `All (${counts.all})` },
    { key: 'active', label: `Active (${counts.active})` },
    { key: 'completed', label: `Completed (${counts.completed})` },
    { key: 'failed', label: `Failed (${counts.failed})` },
    { key: 'cancelled', label: `Cancelled (${counts.cancelled})` },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h1>Downloads</h1>
        <p>Track and manage your download queue.</p>
      </div>

      <div className="tabs">
        {tabs.map((t) => (
          <button key={t.key} className={`tab ${filter === t.key ? 'active' : ''}`} onClick={() => setFilter(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={<Inbox />}
            title="No downloads here"
            subtitle="Downloads you start will appear in this list"
          />
        </div>
      ) : (
        filtered.map((job) => <DownloadCard key={job.id} job={job} />)
      )}
    </div>
  )
}

