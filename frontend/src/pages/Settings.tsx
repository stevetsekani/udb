import { useEffect, useState } from 'react'
import { Check, ClipboardCopy, Download, Film, Save, Server } from 'lucide-react'
import { api } from '../api'
import { useAppStore } from '../store/AppStore'
import { Toggle } from '../components/ui'
import { applyTheme, watchSystemTheme } from '../utils/theme'
import type { AppSettings } from '../types'

export function SettingsPage() {
  const { settings, refreshSettings, notify, version, system, ffmpeg } = useAppStore()
  const [form, setForm] = useState<AppSettings | null>(null)
  const [saved, setSaved] = useState(false)
  const [logs, setLogs] = useState<string>('')

  useEffect(() => {
    if (settings && !form) setForm(settings)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings])

  // Live theme preview
  useEffect(() => {
    if (form) {
      applyTheme(form.theme)
      if (form.theme === 'system') {
        return watchSystemTheme(() => applyTheme('system'))
      }
    }
  }, [form?.theme])

  useEffect(() => {
    api.logs().then((res) => {
      if (res.logs.length > 0) setLogs(res.logs.map((l) => `── ${l.name} ──\n${l.content}`).join('\n\n'))
    }).catch(() => {})
  }, [])

  if (!form) return null

  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setForm((f) => (f ? { ...f, [key]: value } : f))
    setSaved(false)
  }

  const save = async () => {
    try {
      const updated = await api.updateSettings(form)
      setForm(updated)
      refreshSettings()
      setSaved(true)
      notify('Settings saved', 'success')
      window.setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      notify('Failed to save settings', 'error')
    }
  }

  const copyDiagnostics = () => {
    const text = [
      `UDB Diagnostics`,
      `Version: ${version ?? 'unknown'}`,
      `OS: ${system?.os ?? ''} ${system?.os_release ?? ''} (${system?.arch ?? ''})`,
      `Python: ${system?.python ?? ''}`,
      `Packaged: ${system?.frozen ? 'yes' : 'no'}`,
      `FFmpeg: ${ffmpeg?.version ?? 'unknown'} (${ffmpeg?.source ?? 'missing'})`,
      `Download dir: ${form.download_dir}`,
      `Theme: ${form.theme}`,
    ].join('\n')
    navigator.clipboard.writeText(text).then(() => notify('Diagnostics copied to clipboard', 'success'))
  }

  const diagText = [
    `UDB v${version ?? 'unknown'}`,
    `OS: ${system?.os} ${system?.os_release} (${system?.arch})`,
    `Python: ${system?.python}${system?.frozen ? ' [bundled]' : ''}`,
    `FFmpeg: ${ffmpeg?.version ?? 'unknown'} — ${ffmpeg?.source ?? 'missing'}${ffmpeg?.valid ? '' : ' (below minimum)'}`,
    `Backend: connected`,
    `Download dir: ${form.download_dir}`,
  ].join('\n')

  return (
    <div className="page">
      <div className="page-header flex" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1>Settings</h1>
          <p>Configure downloads, clients, logging and appearance.</p>
        </div>
        <button className="btn btn-primary" onClick={save}>
          {saved ? <Check /> : <Save />} {saved ? 'Saved' : 'Save changes'}
        </button>
      </div>

      {/* FFmpeg status banner */}
      <div className="card" style={{ marginBottom: 22, borderColor: ffmpeg?.valid ? 'var(--success)' : 'var(--danger)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div className="stat-icon" style={{ background: ffmpeg?.valid ? 'var(--success-soft)' : 'var(--danger-soft)', color: ffmpeg?.valid ? 'var(--success)' : 'var(--danger)', marginBottom: 0 }}>
          <Film />
        </div>
        <div className="grow">
          <div style={{ fontWeight: 700 }}>
            FFmpeg {ffmpeg?.valid ? `ready (${ffmpeg.version})` : 'not available'}
          </div>
          <div className="muted" style={{ fontSize: 12.5 }}>
            {ffmpeg?.path || 'No FFmpeg binary found.'} · minimum {ffmpeg?.min_required}
            {ffmpeg?.source === 'bundled' && ' · bundled with UDB'}
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h3><Download style={{ width: 16, height: 16, color: 'var(--accent)' }} /> Download</h3>
        <div className="settings-grid">
          <div className="field">
            <label>Download directory</label>
            <input className="input" value={form.download_dir} onChange={(e) => set('download_dir', e.target.value)} />
            <div className="field-hint">Videos are saved here (sub-folders per series).</div>
          </div>
          <div className="field">
            <label>Temporary download directory</label>
            <input className="input" value={form.temp_download_dir} onChange={(e) => set('temp_download_dir', e.target.value)} />
            <div className="field-hint">Use “auto” for a temp folder beside the target.</div>
          </div>
          <div className="field">
            <label>Concurrency per file</label>
            <input className="input" value={String(form.concurrency_per_file)} onChange={(e) => set('concurrency_per_file', e.target.value)} />
            <div className="field-hint">Parallel segment downloads per file (“auto” recommended).</div>
          </div>
          <div className="field">
            <label>Max parallel downloads</label>
            <input className="input" type="number" min={1} max={10} value={form.max_parallel_downloads} onChange={(e) => set('max_parallel_downloads', Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Request timeout (seconds)</label>
            <input className="input" type="number" min={5} value={form.request_timeout} onChange={(e) => set('request_timeout', Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Preferred quality</label>
            <select className="select" value={form.preferred_quality} onChange={(e) => set('preferred_quality', e.target.value)}>
              {['1080', '720', '480', '360'].map((q) => <option key={q} value={q}>{q}p</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h3><Film style={{ width: 16, height: 16, color: 'var(--accent)' }} /> Sources</h3>
        <div className="settings-grid">
          <div className="field">
            <label>AnimePahe download dir</label>
            <input className="input" value={form.animepahe_download_dir ?? ''} onChange={(e) => set('animepahe_download_dir', e.target.value)} />
          </div>
          <div className="field">
            <label>AnimePahe resolution fallback</label>
            <select className="select" value={form.animepahe_selector} onChange={(e) => set('animepahe_selector', e.target.value)}>
              <option value="lowest">Lowest</option>
              <option value="highest">Highest</option>
            </select>
          </div>
          <div className="field">
            <label>KissKh download dir</label>
            <input className="input" value={form.kisskh_download_dir ?? ''} onChange={(e) => set('kisskh_download_dir', e.target.value)} />
          </div>
          <div className="field">
            <label>KissKh search results</label>
            <input className="input" type="number" min={1} max={50} value={form.kisskh_search_limit} onChange={(e) => set('kisskh_search_limit', Number(e.target.value))} />
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h3><Server style={{ width: 16, height: 16, color: 'var(--accent)' }} /> Logging &amp; diagnostics</h3>
        <div className="settings-grid">
          <div className="field">
            <label>Log level</label>
            <select className="select" value={form.log_level} onChange={(e) => set('log_level', e.target.value)}>
              {['DEBUG', 'INFO', 'WARNING', 'ERROR'].map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Log retention (days)</label>
            <input className="input" type="number" min={1} value={form.log_retention_days} onChange={(e) => set('log_retention_days', Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Log backup count</label>
            <input className="input" type="number" min={1} value={form.log_backup_count} onChange={(e) => set('log_backup_count', Number(e.target.value))} />
          </div>
        </div>

        <div className="card" style={{ marginTop: 14 }}>
          <div className="flex" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5 }}>Diagnostics</div>
            <button className="btn btn-sm" onClick={copyDiagnostics}>
              <ClipboardCopy style={{ width: 13, height: 13 }} /> Copy diagnostics
            </button>
          </div>
          <div className="diagnostics-box">{diagText}</div>
        </div>

        {logs && (
          <div className="card" style={{ marginTop: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, marginBottom: 10 }}>Recent logs</div>
            <details>
              <summary className="muted" style={{ cursor: 'pointer', fontSize: 12.5 }}>View recent log file content</summary>
              <div className="diagnostics-box" style={{ maxHeight: 240, marginTop: 10 }}>{logs}</div>
            </details>
          </div>
        )}
      </div>

      <div className="settings-section">
        <h3>Appearance &amp; behaviour</h3>
        <div className="card">
          <div className="field">
            <label>Theme</label>
            <select className="select" value={form.theme} onChange={(e) => set('theme', e.target.value as AppSettings['theme'])}>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="system">System</option>
            </select>
          </div>
          <Toggle
            label="Desktop notifications"
            hint="Show a notification when downloads finish"
            checked={form.notifications}
            onChange={(v) => set('notifications', v)}
          />
          <Toggle
            label="Check for updates on startup"
            checked={form.check_updates_on_startup}
            onChange={(v) => set('check_updates_on_startup', v)}
          />
        </div>
      </div>
    </div>
  )
}

