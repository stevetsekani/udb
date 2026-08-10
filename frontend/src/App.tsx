import { useEffect, useState } from 'react'
import { HashRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Download, History, Home, Info, Menu, Settings, X } from 'lucide-react'
import { useAppStore } from './store/AppStore'
import { DashboardPage } from './pages/Dashboard'
import { DownloadsPage } from './pages/Downloads'
import { HistoryPage } from './pages/History'
import { SettingsPage } from './pages/Settings'
import { AboutPage } from './pages/About'
import { Toasts } from './components/Toasts'
import { DownloadModal } from './components/DownloadModal'
import type { ClientKey } from './types'

function Shell() {
  const { version, downloads, sseConnected, settings } = useAppStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [client, setClient] = useState<ClientKey>('kisskh')

  const activeDownloads = downloads.filter((d) => ['queued', 'preparing', 'downloading', 'retrying'].includes(d.status)).length
  const location = useLocation()

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  const openSearch = (query = '', src?: ClientKey) => {
    setSearchQuery(query)
    if (src) setClient(src)
    setSearchOpen(true)
  }

  return (
    <div className="app-shell">
      <div className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="logo">U</div>
          <div>
            <div className="brand-name">UDB</div>
            <div className="brand-sub">Ultimate Download Bot</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group-label">General</div>
          <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Home /> Dashboard
          </NavLink>
          <NavLink to="/downloads" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Download /> Downloads
            {activeDownloads > 0 && <span className="nav-badge">{activeDownloads}</span>}
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <History /> History
          </NavLink>

          <div className="nav-group-label">Manage</div>
          <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Settings /> Settings
          </NavLink>
          <NavLink to="/about" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Info /> About
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <span>v{version ?? '…'}</span>
          <span title={sseConnected ? 'Live updates connected' : 'Live updates disconnected'}>
            {sseConnected ? '● Live' : '○ Offline'}
          </span>
        </div>
      </div>

      {menuOpen && <div className="sidebar-overlay open" onClick={() => setMenuOpen(false)} />}

      <div className="main-area">
        <div className="topbar">
          <button className="icon-button mobile-menu-btn" onClick={() => setMenuOpen((v) => !v)}>
            {menuOpen ? <X /> : <Menu />}
          </button>
          <span className="topbar-title">
            {location.pathname === '/' && 'Dashboard'}
            {location.pathname === '/downloads' && 'Downloads'}
            {location.pathname === '/history' && 'History'}
            {location.pathname === '/settings' && 'Settings'}
            {location.pathname === '/about' && 'About'}
          </span>
          <div className="topbar-spacer" />
          {settings && (
            <button className="btn btn-primary btn-sm" onClick={() => openSearch('', client)}>
              <Download /> New download
            </button>
          )}
        </div>

        <div className="content-scroll">
          <Routes>
            <Route path="/" element={<DashboardPage onSearch={openSearch} />} />
            <Route path="/downloads" element={<DownloadsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/about" element={<AboutPage />} />
          </Routes>
        </div>
      </div>

      <DownloadModal open={searchOpen} onClose={() => setSearchOpen(false)} initialQuery={searchQuery} client={client} />
      <Toasts />
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <Shell />
    </HashRouter>
  )
}

