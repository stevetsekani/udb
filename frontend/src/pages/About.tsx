import { useState } from 'react'
import { ExternalLink, Github, RefreshCw, X } from 'lucide-react'
import { useAppStore } from '../store/AppStore'

const UPSTREAM = 'https://github.com/Prudhvi-pln/udb'
const RELEASES = 'https://github.com/stevetsekani/udb/releases'

export function AboutPage() {
  const { version, system, ffmpeg } = useAppStore()
  const [latest, setLatest] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  const checkUpdate = async () => {
    setChecking(true)
    try {
      const res = await fetch(
        'https://api.github.com/repos/stevetsekani/udb/releases/latest',
        { headers: { Accept: 'application/vnd.github+json' } },
      )
      if (!res.ok) throw new Error('bad status')
      const data = await res.json()
      const tag = (data.tag_name || '').replace(/^v/i, '')
      setLatest(tag)
    } catch {
      setLatest('unavailable')
    } finally {
      setChecking(false)
    }
  }

  const isNewer = latest && latest !== 'unavailable' && version ? compareVersions(latest, version) > 0 : false

  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <div className="card" style={{ textAlign: 'center', padding: '40px 24px' }}>
        <div
          className="logo"
          style={{
            width: 64,
            height: 64,
            fontSize: 28,
            borderRadius: 18,
            margin: '0 auto 16px',
            background: 'linear-gradient(135deg, var(--accent), #7c3aed)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 800,
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          U
        </div>
        <h1 style={{ fontSize: 26, fontWeight: 800 }}>UDB</h1>
        <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>Ultimate Download Bot</div>
        <div className="mono muted" style={{ marginTop: 8 }}>v{version ?? 'unknown'}</div>

        <p style={{ color: 'var(--text-muted)', maxWidth: 460, margin: '18px auto 0', lineHeight: 1.6 }}>
          A modern desktop application for downloading anime, drama, movies and TV shows — built as a
          GUI contribution over the original <b>UDB</b> command-line downloader. All downloading happens
          locally using the original UDB engine.
        </p>

        <div className="flex center" style={{ gap: 10, marginTop: 20 }}>
          <a className="btn" href={UPSTREAM} target="_blank" rel="noreferrer">
            <Github style={{ width: 14, height: 14 }} /> Original project
          </a>
          <button className="btn" onClick={checkUpdate} disabled={checking}>
            {checking ? <RefreshCw className="spinning" style={{ width: 14, height: 14 }} /> : <RefreshCw style={{ width: 14, height: 14 }} />}
            Check for updates
          </button>
        </div>

        {latest && (
          <div style={{ marginTop: 14 }}>
            {latest === 'unavailable' ? (
              <span className="muted" style={{ fontSize: 13 }}>Could not reach GitHub Releases.</span>
            ) : isNewer ? (
              <span className="success-text" style={{ fontSize: 13, fontWeight: 600 }}>
                New version available: v{latest} ·{' '}
                <a href={RELEASES} target="_blank" rel="noreferrer">
                  View release <ExternalLink style={{ width: 11, height: 11, verticalAlign: 'middle' }} />
                </a>
              </span>
            ) : (
              <span className="muted" style={{ fontSize: 13 }}>You are on the latest version.</span>
            )}
          </div>
        )}

        <div style={{ marginTop: 22 }}>
          <button className="btn btn-danger" onClick={quitApp}>
            <X style={{ width: 14, height: 14 }} /> Quit UDB
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Environment</div>
        <div className="diagnostics-box">
          {`UDB v${version ?? 'unknown'}
OS: ${system?.os} ${system?.os_release} (${system?.arch})
Python: ${system?.python ?? ''}${system?.frozen ? ' [bundled]' : ''}
FFmpeg: ${ffmpeg?.version ?? 'unknown'} (${ffmpeg?.source ?? 'missing'})`}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Acknowledgements</div>
        <p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>
          This GUI is a fork enhancement and would not exist without the original UDB project by{' '}
          <b>Prudhvi PLN</b> and the open-source libraries it relies on: animdl, dra-cla,
          vidsrc-to-resolver, vidplay-keys and m3u8downloader.
        </p>
        <div style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 10 }}>
          License: MIT · Bundled binaries are redistributed under their own licenses (see
          THIRD_PARTY_NOTICES.txt).
        </div>
      </div>
    </div>
  )
}

function quitApp() {
  // Native quit via the desktop shell bridge; falls back to closing the window.
  const w = window as unknown as {
    pywebview?: { api?: { quit?: () => unknown } }
  }
  if (w.pywebview?.api?.quit) {
    w.pywebview.api.quit()
    return
  }
  window.close()
}

function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    const x = pa[i] || 0
    const y = pb[i] || 0
    if (x !== y) return x - y
  }
  return 0
}

