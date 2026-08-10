import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'

// The dev backend writes backend_port.json to the app-data dir. Read it so the
// Vite dev server can proxy /api and /api/events to the local Python backend.
function readBackendPort(): number {
  const candidates = [
    process.env.UDB_BACKEND_PORT,
  ]
  const home = homedir()
  const possiblePaths = [
    join(process.env.APPDATA || '', 'UDB', 'backend_port.json'),
    join(home, '.config', 'udb', 'backend_port.json'),
    join(home, 'Library', 'Application Support', 'UDB', 'backend_port.json'),
  ]
  for (const p of possiblePaths) {
    try {
      const data = JSON.parse(readFileSync(p, 'utf-8'))
      if (data.port) return data.port
    } catch {
      // ignore
    }
  }
  for (const p of candidates) {
    if (p) return Number(p)
  }
  return 5566
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${readBackendPort()}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})
