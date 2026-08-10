# Building UDB

This document explains how to build the desktop application from source on
Windows and Linux. GitHub Actions runs these exact commands in CI
(see [RELEASE.md](RELEASE.md)).

## Prerequisites

* **Python 3.11 or 3.12** (3.13+ generally works; CI pins 3.12)
* **Node.js 18+** (for the frontend; 20 recommended)
* **Git**
* ~1.5 GB free disk for the build output

You do **not** need FFmpeg installed — the build downloads static binaries and
bundles them.

## 1. Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## 2. Build the frontend

```bash
cd frontend
npm ci            # exact install from package-lock.json
npm run build     # outputs frontend/dist (bundled by PyInstaller)
cd ..
```

`frontend/dist` is git-ignored; it is produced by this step.

## 3. (Optional) Fetch FFmpeg for bundling

```bash
python packaging/ffmpeg/fetch_ffmpeg.py
```

Downloads static FFmpeg + FFprobe into `packaging/ffmpeg/bin/`:

* Windows → `ffmpeg-master-latest-win64-gpl.zip` (BtbN builds)
* Linux   → `ffmpeg-release-amd64-static.tar.xz` (johnvansickle)

Override the URL with `UDB_FFMPEG_URL` to pin a specific mirror/version.
If you skip this step the app still works, but it will rely on a system FFmpeg.

## 4. Build the app with PyInstaller

The shared spec `packaging/udb.spec` bundles:

* `desktop/main.py` (entry point) + the whole Python engine
* `frontend/dist` (the web UI)
* `config_udb.yaml` and `CHANGELOG.md`
* `packaging/ffmpeg/bin` (when present)

```bash
python -m PyInstaller --noconfirm --clean packaging/udb.spec
```

Output lands in `dist/udb/` (one-dir bundle) with `udb.exe` on Windows or
`udb` on Linux.

### Windows portable ZIP

```bash
python packaging/windows/build_windows.py
# → dist/UDB-Windows-x64.zip  (unzip anywhere, run udb.exe)
```

Flags: `--skip-frontend`, `--skip-ffmpeg`, `--no-zip`.

### Linux AppImage

```bash
# one-time: install appimagetool requirements
sudo apt-get install -y libfuse2 file

python packaging/linux/build_linux.py
# → dist/UDB-x86_64.AppImage
```

Flags: `--skip-frontend`, `--skip-ffmpeg`.

## 5. Verify the build

On Windows:

```powershell
dist\udb\udb.exe
```

The app should open a window, boot the backend on `127.0.0.1`, and load the
dashboard. Check `%APPDATA%\UDB\logs\udb-desktop.log` if anything fails.

## Running tests

```bash
python -m pytest tests/ -q          # backend
cd frontend && npx vitest run        # frontend unit tests
cd frontend && npx tsc --noEmit      # type-check
```

## Notes / troubleshooting

* **Windows: `npm` is a `.cmd` shim** — there is no `npm.exe` on PATH, so
  Python's `subprocess.run(['npm', …])` fails with `FileNotFoundError` unless
  the command is routed through the shell. `packaging/windows/build_windows.py`
  uses `shell=True` on Windows for this reason (`python`/`pip` are real `.exe`
  files and work either way).
* **PyInstaller console=False** — the Windows build is a windowed app; stdout
  goes nowhere. All diagnostics are in the rotating log file under the app-data
  directory.
* **UPX** — disabled in the spec for reproducible builds. Enable it for smaller
  artifacts if you have UPX installed.
* **Version** — the app version is read from the first `## Version` line in
  `CHANGELOG.md` (bundled into the app), so bump that file before tagging a
  release.

