import React, { useEffect } from 'react'
import type { DownloadStatus } from '../types'

// --------------------------------------------------------------------------- //
// Progress bar                                                                //
// --------------------------------------------------------------------------- //
export function ProgressBar({ value, status }: { value: number; status?: DownloadStatus }) {
  const clamped = Math.max(0, Math.min(100, value))
  const cls =
    status === 'completed' ? 'complete' : status === 'failed' || status === 'cancelled' ? 'error' : ''
  return (
    <div className="progress-track" role="progressbar" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100}>
      <div className={`progress-fill ${cls}`} style={{ width: `${clamped}%` }} />
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Status pill                                                                 //
// --------------------------------------------------------------------------- //
export function StatusPill({ status }: { status: DownloadStatus }) {
  const labels: Record<DownloadStatus, string> = {
    queued: 'Queued',
    preparing: 'Preparing',
    downloading: 'Downloading',
    completed: 'Completed',
    failed: 'Failed',
    cancelled: 'Cancelled',
    retrying: 'Retrying',
  }
  return (
    <span className={`status-pill ${status}`}>
      <span className="dot" />
      {labels[status] ?? status}
    </span>
  )
}

// --------------------------------------------------------------------------- //
// Spinner                                                                     //
// --------------------------------------------------------------------------- //
export function Spinner({ size = 18 }: { size?: number }) {
  return <div className="spinner" style={{ width: size, height: size }} />
}

// --------------------------------------------------------------------------- //
// Empty state                                                                 //
// --------------------------------------------------------------------------- //
export function EmptyState({ icon, title, subtitle }: { icon?: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="empty-state">
      {icon}
      <h3>{title}</h3>
      {subtitle && <p className="muted">{subtitle}</p>}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Modal                                                                       //
// --------------------------------------------------------------------------- //
export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  open: boolean
  title: React.ReactNode
  onClose: () => void
  children: React.ReactNode
  footer?: React.ReactNode
  wide?: boolean
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={wide ? { maxWidth: 680 } : undefined}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Toggle                                                                      //
// --------------------------------------------------------------------------- //
export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label?: string; hint?: string }) {
  return (
    <div className="toggle-row">
      <div>
        <div className="toggle-label">{label}</div>
        {hint && <div className="faint" style={{ fontSize: 12 }}>{hint}</div>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        className={`toggle ${checked ? 'active' : ''}`}
        onClick={() => onChange(!checked)}
      />
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Format helpers                                                              //
// --------------------------------------------------------------------------- //
export function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)))
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatDate(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fileTitle(job: { title: string; episode?: string | number | null }): string {
  return job.title || 'Unknown'
}

