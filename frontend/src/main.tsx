import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AppStoreProvider } from './store/AppStore'
import { applyTheme } from './utils/theme'
import './styles/global.css'

// Apply the persisted theme before first paint to avoid a flash.
applyTheme()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppStoreProvider>
      <App />
    </AppStoreProvider>
  </React.StrictMode>,
)

