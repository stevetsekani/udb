# UDB GUI Architecture

This document describes how the desktop GUI is put together, how the local API
works, and the security model. It is aimed at contributors extending the app.

## 1. High-level layout

```
┌──────────────────────────────────────────────────────────────────┐
│ desktop/main.py        PyWebView shell                            │
│  - starts the backend thread                                      │
│  - opens a native window at http://127.0.0.1:<ephemeral port>     │
│  - exposes window.pywebview.api (open_folder, quit)               │
│  - shuts the backend down when the window closes                  │
└───────────────────────────────┬──────────────────────────────────┘
                                │ serves the built frontend (frontend/dist)
┌───────────────────────────────▼──────────────────────────────────┐
│ backend/ (Flask, bound to 127.0.0.1)                              │
│  app.py          app factory, token gate, frontend serving        │
│  server.py       ephemeral port, readiness probe, clean shutdown  │
│  api/routes.py   REST endpoints + SSE event stream                │
│  services/                                                       │
│    config_service    user config_udb.yaml + gui_settings.json     │
│    history           SQLite download history (persistent)         │
│    events            in-process pub/sub for SSE progress          │
│    udb_service       bridge to the existing downloader engine     │
│    download_manager  download queue / job lifecycle               │
│    ffmpeg_service    FFmpeg discovery: bundled > configured > sys │
└───────────────────────────────┬──────────────────────────────────┘
                                │ calls the SAME engine the CLI uses
┌───────────────────────────────▼──────────────────────────────────┐
│ udb.py · Clients/ · Utils/       (original downloader, unchanged) │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Request flow (search → download)

1. **Search** — `POST /api/search {client, query}`. The backend asks the cached
   client (`AnimePaheClient` / `KissKhClient`) and caches raw results.
2. **Inspect** — `POST /api/inspect {client, result_id}`. Fetches the episode
   list for a title and caches it as an “episode session”.
3. **Download** — `POST /api/download {episode_session, resolution, selection,
   download_dir}`. The `DownloadManager` creates one job per selected episode,
   then a background thread resolves per-episode links (`prepare_downloads`)
   and starts downloading through the original downloader.
4. **Progress** — the downloader reports progress through a
   `progress_callback`; the manager publishes to the `EventBus`; each SSE
   subscriber (`GET /api/events`) receives `download_progress` /
   `download_status` events. **Progress is always real** — it comes from the
   actual downloader.

## 3. The download queue (lifecycle)

```
queued → preparing → downloading → completed
                    → failed
                    → cancelled
                    → retrying
```

The underlying downloader has **no true pause/resume**, so the GUI intentionally
exposes only operations the engine actually supports:

| Action   | What happens                                              |
| :------- | :-------------------------------------------------------- |
| Cancel   | sets a per-job `threading.Event`; the download loop checks it between segments/chunks and aborts cleanly |
| Retry    | re-runs a failed/cancelled job, reusing already-downloaded segments |
| Remove   | cancels (if active) and drops the job from the queue       |
| Open     | opens the containing folder in the OS file manager         |

Job state changes are persisted to `history.db` (SQLite) so the History page
survives restarts.

## 4. Configuration

* The CLI's `config_udb.yaml` is copied to the app-data directory on first run
  and the download folder is defaulted to the user's `Downloads`.
* The Settings page maps flat GUI fields to nested YAML sections via
  `ConfigService.get_settings()/update_settings()`. CLI and GUI therefore
  share the exact same configuration file.

## 5. FFmpeg

Discovery order (see `backend/services/ffmpeg_service.py`):

1. Bundled FFmpeg (inside the app bundle, `ffmpeg/bin/`)
2. Explicitly configured path (Settings)
3. System `ffmpeg` on `PATH`

`ensure_ffmpeg_on_path()` prepends the winning directory to `PATH` so the
existing downloader (which shells out to `ffmpeg`/`ffprobe`) picks the right
binary automatically. End users never install FFmpeg themselves.

## 6. Security model

* The backend **binds strictly to `127.0.0.1`** on an **ephemeral port**.
* An optional random **auth token** (persisted per install) is injected into the
  served page and required on `/api/*` requests from other origins.
* **No arbitrary shell execution** — the API never runs user-supplied commands;
  paths are validated (`os.path.isdir`, `os.path.isfile`) before use.
* Errors never leak tracebacks to the UI; they return
  `{error: {message, details}}`.
* No remote backend, no telemetry, no cloud dependency — the app works fully
  offline.

## 7. Frontend

* React 18 + TypeScript + Vite, served by the Flask backend in production and
  by the Vite dev server (with a proxy to the backend) in development.
* State lives in a single context store (`frontend/src/store/AppStore.tsx`)
  which consumes the REST API and the SSE stream for live updates.
* Routing uses `HashRouter` so deep links work inside the webview / file origins.

## 8. Dev workflow

```bash
python scripts/dev.py              # backend (ephemeral port) + Vite hot reload
python scripts/dev.py --no-vite    # backend only
python desktop/main.py --dev-url http://127.0.0.1:5173   # shell against Vite
```

The backend writes `backend_port.json` into the app-data directory so the Vite
proxy knows where to forward `/api`.

