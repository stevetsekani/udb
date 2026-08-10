import { useEffect, useMemo, useState } from 'react'
import { Clapperboard, Download, Film, Search, SearchX, Tv, X } from 'lucide-react'
import { api, ApiError } from '../api'
import { useAppStore } from '../store/AppStore'
import type { ClientKey, EpisodeSelection, InspectResponse, SearchResult } from '../types'
import { EmptyState, Modal, Spinner } from './ui'

type Step = 'search' | 'results' | 'inspect' | 'configure' | 'submitting'

interface Props {
  open: boolean
  onClose: () => void
  initialQuery: string
  client: ClientKey
}

export function DownloadModal({ open, onClose, initialQuery, client }: Props) {
  const { settings, refreshDownloads, notify } = useAppStore()
  const [step, setStep] = useState<Step>('search')
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState<SearchResult[]>([])
  const [inspect, setInspect] = useState<InspectResponse | null>(null)
  const [error, setError] = useState('')
  const [searching, setSearching] = useState(false)

  // configure state
  const [rangeMode, setRangeMode] = useState<'all' | 'range' | 'specific'>('all')
  const [rangeStart, setRangeStart] = useState('')
  const [rangeEnd, setRangeEnd] = useState('')
  const [specificEps, setSpecificEps] = useState('')
  const [quality, setQuality] = useState(settings?.preferred_quality || '1080')
  const [downloadDir, setDownloadDir] = useState(settings?.download_dir || '')

  useEffect(() => {
    if (open) {
      setQuery(initialQuery)
      setStep('search')
      setResults([])
      setInspect(null)
      setError('')
      setQuality(settings?.preferred_quality || '1080')
      setDownloadDir(settings?.download_dir || '')
      if (initialQuery.trim()) doSearch(initialQuery)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const doSearch = async (q?: string) => {
    const term = (q ?? query).trim()
    if (!term) return
    setSearching(true)
    setError('')
    setStep('search')
    try {
      const res = await api.search(client, term)
      setResults(res.results)
      setStep('results')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Search failed')
      setStep('results')
    } finally {
      setSearching(false)
    }
  }

  const doInspect = async (result: SearchResult) => {
    setStep('inspect')
    setError('')
    try {
      const data = await api.inspect(client, result.id)
      setInspect(data)
      setRangeStart('')
      setRangeEnd('')
      setSpecificEps('')
      setRangeMode('all')
      setStep('configure')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load episodes')
      setStep('results')
    }
  }

  const selection = useMemo<EpisodeSelection | Record<string, EpisodeSelection>>(() => {
    if (rangeMode === 'all') {
      // no start/end -> server defaults to full range
      return { specific_no: [] }
    }
    if (rangeMode === 'specific') {
      const numbers = specificEps
        .split(',')
        .map((s) => Number(s.trim()))
        .filter((n) => !Number.isNaN(n))
      return { specific_no: numbers }
    }
    return {
      start: rangeStart ? Number(rangeStart) : 1,
      end: rangeEnd ? Number(rangeEnd) : undefined,
      specific_no: [],
    }
  }, [rangeMode, rangeStart, rangeEnd, specificEps])

  const canDownload =
    step === 'configure' && inspect && downloadDir.trim() && (rangeMode !== 'specific' || specificEps.trim())

  const startDownload = async () => {
    if (!inspect) return
    setStep('submitting')
    setError('')
    try {
      const res = await api.createDownload({
        episode_session: inspect.episode_session,
        resolution: quality,
        selection: selection,
        download_dir: downloadDir.trim(),
      })
      notify(`Added ${res.created} download${res.created === 1 ? '' : 's'} to the queue`, 'success')
      refreshDownloads()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start download')
      setStep('configure')
    }
  }

  const totalEpisodes = inspect?.total_episodes ?? 0
  const selectedCount =
    rangeMode === 'all'
      ? totalEpisodes
      : rangeMode === 'specific'
        ? specificEps.split(',').filter((s) => s.trim() !== '').length
        : (rangeEnd ? Number(rangeEnd) : totalEpisodes) - (rangeStart ? Number(rangeStart) : 1) + 1

  const close = () => {
    if (step !== 'submitting') onClose()
  }

  return (
    <Modal open={open} onClose={close} title="Download" wide footer={undefined}>
      {/* ---- Search ---- */}
      {(step === 'search' || step === 'results') && (
        <div>
          <div className="search-bar" style={{ maxWidth: 'none', marginTop: 0 }}>
            <input
              className="input"
              value={query}
              placeholder="Search for anime, drama, movies or TV shows…"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doSearch()}
              autoFocus
            />
            <button className="btn btn-primary" onClick={() => doSearch()} disabled={searching}>
              {searching ? <Spinner size={15} /> : <Search />} Search
            </button>
          </div>

          {searching && (
            <div className="flex center" style={{ padding: 40 }}>
              <Spinner /> <span className="muted">Searching…</span>
            </div>
          )}

          {error && <div className="error-text" style={{ marginTop: 14 }}>{error}</div>}

          {!searching && step === 'results' && results.length === 0 && !error && (
            <EmptyState icon={<SearchX />} title="No results found" subtitle="Try a different keyword" />
          )}

          {!searching && results.length > 0 && (
            <div className="search-results">
              <div className="faint" style={{ fontSize: 12, marginBottom: 8 }}>
                {results.length} result{results.length === 1 ? '' : 's'} for “{query}”
              </div>
              {results.map((r) => (
                <button key={r.id} className="result-card" onClick={() => doInspect(r)}>
                  <div className="result-icon">
                    {r.type.toLowerCase().includes('movie') || r.type.toLowerCase().includes('hollywood') ? <Film /> : <Tv />}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div className="result-title">{r.title}</div>
                    <div className="result-sub">
                      {[r.year, r.type, r.episodes ? `${r.episodes} episodes` : '', r.status, r.detail]
                        .filter(Boolean)
                        .join(' · ')}
                    </div>
                  </div>
                  <span style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>→</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ---- Inspect (loading) ---- */}
      {step === 'inspect' && (
        <div className="flex center" style={{ padding: 40 }}>
          <Spinner /> <span className="muted">Loading episodes…</span>
        </div>
      )}

      {/* ---- Configure ---- */}
      {step === 'configure' && inspect && (
        <div>
          <div className="flex" style={{ marginBottom: 16 }}>
            <div className="result-icon">
              <Clapperboard />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{inspect.title}</div>
              <div className="muted" style={{ fontSize: 12.5 }}>
                {[inspect.year, inspect.is_tv ? 'TV Series' : 'Movie', `${totalEpisodes} episodes`]
                  .filter(Boolean)
                  .join(' · ')}
              </div>
            </div>
          </div>

          <div className="field">
            <label>Episodes</label>
            <div className="source-toggle" style={{ marginTop: 0 }}>
              <button className={rangeMode === 'all' ? 'active' : ''} onClick={() => setRangeMode('all')}>
                All ({totalEpisodes})
              </button>
              <button className={rangeMode === 'range' ? 'active' : ''} onClick={() => setRangeMode('range')}>
                Range
              </button>
              <button className={rangeMode === 'specific' ? 'active' : ''} onClick={() => setRangeMode('specific')}>
                Specific
              </button>
            </div>
          </div>

          {rangeMode === 'range' && (
            <div className="flex" style={{ gap: 10, marginBottom: 14 }}>
              <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                <label>From episode</label>
                <input className="input" type="number" min={1} value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} placeholder="1" />
              </div>
              <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                <label>To episode</label>
                <input className="input" type="number" min={1} value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} placeholder={String(totalEpisodes)} />
              </div>
            </div>
          )}

          {rangeMode === 'specific' && (
            <div className="field">
              <label>Episode numbers (comma separated, e.g. 1,3,5)</label>
              <input className="input" value={specificEps} onChange={(e) => setSpecificEps(e.target.value)} placeholder="1,3,5-7" />
            </div>
          )}

          <div className="flex" style={{ gap: 12 }}>
            <div className="field" style={{ flex: 1 }}>
              <label>Quality</label>
              <select className="select" value={quality} onChange={(e) => setQuality(e.target.value)}>
                {['1080', '720', '480', '360'].map((q) => (
                  <option key={q} value={q}>{q}p</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ flex: 1.6 }}>
              <label>Download to</label>
              <input className="input" value={downloadDir} onChange={(e) => setDownloadDir(e.target.value)} placeholder="Download directory" />
            </div>
          </div>

          <div className="faint" style={{ fontSize: 12 }}>
            Will download <b>{selectedCount}</b> episode{selectedCount === 1 ? '' : 's'} at {quality}p to{' '}
            <span className="mono">{downloadDir || '…'}</span>
          </div>

          {error && <div className="error-text" style={{ marginTop: 10 }}>{error}</div>}

          <div className="flex end" style={{ marginTop: 18 }}>
            <button className="btn" onClick={() => setStep('results')}>
              <X /> Back
            </button>
            <button className="btn btn-primary" disabled={!canDownload} onClick={startDownload}>
              <Download /> Add to downloads
            </button>
          </div>
        </div>
      )}

      {/* ---- Submitting ---- */}
      {step === 'submitting' && (
        <div className="flex center" style={{ padding: 40 }}>
          <Spinner /> <span className="muted">Preparing downloads…</span>
        </div>
      )}
    </Modal>
  )
}

