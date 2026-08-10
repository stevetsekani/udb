# UDB — Ultimate Download Bot

A polished desktop application for downloading **anime, drama, movies and TV
shows**. UDB bundles a beautiful web-style GUI, a local engine that powers the
downloads, and everything needed to run on a clean machine — **no Python, pip,
FFmpeg or PATH configuration required**.

UDB is a fork enhancement of the original
[Prudhvi-pln/udb](https://github.com/Prudhvi-pln/udb) command-line downloader.
The original downloader engine is preserved and shared by both the GUI and the
CLI, so nothing that used to work is removed.

---

## ✨ Highlights

- **Desktop app with a modern GUI** — dark / light / system themes, a dashboard
  with live progress, a persistent download queue, and a searchable history.
- **No setup for end users** — download a single portable build (`.zip` /
  `.exe` / `.AppImage`), double-click, and go. Python, FFmpeg and Node are
  bundled or discovered automatically.
- **Real progress, never fake** — the GUI shows live per-file progress streamed
  from the actual downloader over Server-Sent Events.
- **Local-only** — everything runs on `127.0.0.1` inside your machine. No
  accounts, no remote servers, no telemetry.
- **Persistent settings & history** — your download folder, quality preference,
  theme and every download attempt are stored on disk.
- **Original CLI still works** — `python udb.py` continues to behave exactly as
  before for power users and automation.

## 🖥️ Screenshots / status

| Source | Status |
| :----- | :----: |
| AnimePahe | Active |
| KissKh (anime, drama, movies & TV) | Active |
| GogoAnime | Active (no updates after Nov 2024) |
| MyAsianTV / Asianbxkiun | Inactive |
| Vidsrc / Superembed | Discontinued |

## 🚀 Getting started

### Option 1 — Use the desktop app (recommended)

1. Download the latest build for your OS from
   [Releases](https://github.com/stevetsekani/udb/releases):
   - **Windows**: `UDB-Windows-x64.zip` (portable — unzip and run `udb.exe`)
   - **Linux**: `UDB-x86_64.AppImage`
2. Launch the app. A window opens with the search dashboard.
3. Search for a title, pick a result, choose episodes and quality, and download.

### Option 2 — Run from source (developers)

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python desktop/main.py --debug        # desktop shell with dev tools
python scripts/dev.py                 # backend + Vite hot reload
```

### Option 3 — The original CLI

```bash
python -m pip install -r requirements.txt
python udb.py                         # interactive CLI (unchanged)
python udb.py -h                      # all CLI arguments
```

## 🔍 How it works

The desktop app is three pieces wired together:

```
┌────────────────────────────────────────────────────────┐
│  Desktop shell (PyWebView)                             │
│  opens a native window at http://127.0.0.1:<port>      │
└───────────────┬────────────────────────────────────────┘
                │ serves the built frontend
┌───────────────▼────────────────────────────────────────┐
│  Local backend (Flask, 127.0.0.1 only)                 │
│  REST API + SSE progress + settings + history (SQLite) │
└───────────────┬────────────────────────────────────────┘
                │ calls the same engine the CLI uses
┌───────────────▼────────────────────────────────────────┐
│  UDB engine (udb.py / Clients / Utils)                 │
│  AnimePahe & KissKh clients, m3u8/direct downloaders   │
└────────────────────────────────────────────────────────┘
```

See [GUI_ARCHITECTURE.md](GUI_ARCHITECTURE.md) for the full design, the API
reference, and the security model.

## 📦 Build it yourself

- [BUILDING.md](BUILDING.md) — prerequisites and step-by-step builds for
  Windows, Linux and the desktop shell.
- [RELEASE.md](RELEASE.md) — how CI builds artifacts and how to publish a
  release (SHA256 checksums, GitHub Actions).

## 🗂️ Data & configuration

| Item | Location |
| :--- | :------- |
| Windows app data | `%APPDATA%\UDB\` |
| Linux app data | `~/.config/udb/` |
| macOS app data | `~/Library/Application Support/UDB/` |
| Configuration | `config_udb.yaml` (copied on first run, editable in Settings) |
| History database | `history.db` (SQLite) |
| Logs | `logs/` (rotated, viewable in Settings) |
| FFmpeg | bundled when available; otherwise auto-discovered |

The CLI's `config_udb.yaml` format is unchanged — the GUI Settings page edits
the very same file, so CLI and GUI share your configuration.

## 🧪 Tests

```bash
python -m pytest tests/ -q        # backend tests (42 tests)
cd frontend && npx vitest run      # frontend unit tests
cd frontend && npx tsc --noEmit    # type-check
```

## ❤️ Acknowledgements

This GUI fork builds on the original UDB by **Prudhvi PLN** and the open-source
libraries it relies on: animdl, dra-cla, vidsrc-to-resolver, vidplay-keys,
m3u8downloader, plus Flask, PyWebView, React and friends. See
[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) for bundled binaries and
licenses.

## 📄 License

MIT — see [LICENSE.md](LICENSE.md). Bundled third-party binaries are
redistributed under their own licenses (see THIRD_PARTY_NOTICES.txt).

