import { FolderOpen, RefreshCw, Trash2, XCircle } from 'lucide-react'
import type { DownloadJob } from '../types'
import { api } from '../api'
import { useAppStore } from '../store/AppStore'
import { ProgressBar, StatusPill, formatBytes } from './ui'

export function DownloadCard({ job }: { job: DownloadJob }) {
  const { notify, refreshDownloads } = useAppStore()

  const busy = ['queued', 'preparing', 'downloading', 'retrying'].includes(job.status)

  const run = async (action: () => Promise<unknown>, okMsg: string, errMsg: string) => {
    try {
      await action()
      notify(okMsg, 'success')
      refreshDownloads()
    } catch (err) {
      notify(errMsg, 'error')
    }
  }

  return (
    <div className="dl-card">
      <div className="dl-card-top">
        <div style={{ minWidth: 0 }}>
          <div className="dl-title">{job.title}</div>
          <div className="dl-meta">
            {job.episode != null && `Episode ${job.episode}`}
            {job.quality ? ` · ${job.quality}P` : ''}
            {job.client ? ` · ${job.client}` : ''}
          </div>
        </div>
        <div className="dl-right">
          <StatusPill status={job.status} />
          <div className="dl-actions" style={{ display: 'flex', gap: 4 }}>
            {busy && (
              <button
                className="icon-button"
                title="Cancel"
                onClick={() => run(() => api.cancelDownload(job.id), 'Download cancelled', 'Could not cancel')}
              >
                <XCircle />
              </button>
            )}
            {(job.status === 'failed' || job.status === 'cancelled') && (
              <button
                className="icon-button"
                title="Retry"
                onClick={() => run(() => api.retryDownload(job.id), 'Retrying download', 'Could not retry')}
              >
                <RefreshCw />
              </button>
            )}
            <button
              className="icon-button"
              title="Open folder"
              onClick={() => api.openFolder(job.id).catch(() => notify('Folder not available', 'error'))}
            >
              <FolderOpen />
            </button>
            <button
              className="icon-button"
              title="Remove from list"
              onClick={() => run(() => api.removeDownload(job.id), 'Removed from list', 'Could not remove')}
            >
              <Trash2 />
            </button>
          </div>
        </div>
      </div>

      <div className="dl-progress-row">
        <ProgressBar value={job.progress} status={job.status} />
        <span className="dl-percent">{Math.round(job.progress)}%</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
        <div className="dl-meta">
          {job.status === 'downloading' && job.speed_str && (
            <span>{job.speed_str}</span>
          )}
          {job.status === 'downloading' && job.total > 0 && (
            <span style={{ marginLeft: 10 }}>
              {formatBytes(job.completed)} / {formatBytes(job.total)}
              {job.unit && job.unit !== 'iB' ? ` ${job.unit}` : ''}
            </span>
          )}
          {job.status === 'failed' && job.error && <span className="error-text">{job.error}</span>}
        </div>
        <span className="dl-meta mono">{job.episodeName}</span>
      </div>
    </div>
  )
}

