# Publishing a UDB Release

Releases are built and published automatically by GitHub Actions. This document
describes the process and what CI does under the hood.

## CI (`.github/workflows/ci.yml`)

Runs on every push to `main` and on pull requests:

1. **Backend tests** (Python 3.12) — `pytest tests/` + compile check.
2. **Frontend** (Node 20) — `tsc --noEmit`, `vitest run`, production build.
3. **Packaging check** — syntax-check the packaging scripts.

## Release workflow (`.github/workflows/release.yml`)

Triggered when a tag matching `v*` is pushed (e.g. `v2.17.0`).

| Job | Runner | Artifact |
| :-- | :----- | :------- |
| `build-windows` | `windows-latest` | `UDB-Windows-x64.zip` |
| `build-linux` | `ubuntu-latest` | `UDB-x86_64.AppImage` |
| `release` | `ubuntu-latest` | Creates the GitHub Release with auto-generated notes + `SHA256SUMS.txt` |

Each build job:

1. Checks out the tag.
2. Installs Python deps and runs `pip install pyinstaller`.
3. Runs the platform build script (`packaging/windows/build_windows.py` or
   `packaging/linux/build_linux.py`), which builds the frontend, downloads and
   bundles FFmpeg, and runs PyInstaller.
4. Uploads the artifact.

The `release` job downloads both artifacts, computes SHA256 checksums, and
publishes them together.

## How to publish a release

1. **Bump the version** in `CHANGELOG.md` — add a `## Version x.y.z` heading at
   the top. The app reads this for its version string and CI uses it for the
   release tag.
2. Commit and push:

   ```bash
   git add CHANGELOG.md
   git commit -m "x.y.z"
   git push origin main
   ```

3. Tag and push the tag:

   ```bash
   git tag v2.17.0
   git push origin v2.17.0
   ```

4. Watch the **Release** workflow run. When it finishes, a GitHub Release
   appears with:
   * `UDB-Windows-x64.zip`
   * `UDB-x86_64.AppImage`
   * `SHA256SUMS.txt`

## Verify the checksums

```bash
# download the artifacts, then:
sha256sum -c SHA256SUMS.txt          # Linux / macOS
Get-FileHash UDB-Windows-x64.zip     # Windows (compare manually)
```

## Local release dry-run

You can reproduce the Windows artifact locally without CI:

```bash
python packaging/windows/build_windows.py
sha256sum dist/UDB-Windows-x64.zip
```

