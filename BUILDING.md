# Building standalone releases

OpenMATB can be compiled into a self-contained build per OS (no Python
install needed by the end user) using [Nuitka](https://nuitka.net/).

## Automatic builds (recommended)

Push a version tag and GitHub Actions builds all three OSes and attaches
them to a GitHub Release automatically:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Or trigger a build without tagging: go to the repo's **Actions** tab →
"Build standalone releases" → **Run workflow**. Artifacts (`OpenMATB-macos`,
`OpenMATB-windows`, `OpenMATB-linux`) show up under that run once it finishes.

Nuitka cannot cross-compile: each OS's build only runs on that OS. The
workflow handles this by building on GitHub's own macOS/Windows/Linux
runners in parallel — no physical machines needed.

## Manual builds

Same steps the CI runs, if you want to build locally on a given OS.

### macOS

```bash
source .venv/bin/activate
pip install nuitka
python3 -m nuitka --standalone --macos-create-app-bundle \
  --include-data-dir="./includes"="includes" \
  --include-data-dir="./locales"="locales" \
  --include-data-file="config.ini"="config.ini" \
  --include-data-file="LICENSE"="LICENSE" \
  --include-data-file="README.md"="README.md" \
  --include-data-file="VERSION"="VERSION" \
  --output-dir=build_macos \
  main.py
```
Output: `build_macos/main.app`. Zip it before sharing (`.app` is a folder):
```bash
cd build_macos && ditto -c -k --sequesterRsrc --keepParent main.app OpenMATB-mac.zip
```

### Windows

Run from a regular (non-admin) `cmd.exe` or PowerShell with the venv active:
```bat
windows_compilation.bat
```
Output: `main.dist\` folder, containing `main.exe`. Zip the whole folder to share it.

### Linux

```bash
source .venv/bin/activate
bash linux_compilation.sh
```
Output: `main.dist/`, containing the `main` executable. Zip the whole folder to share it.

## Notes for all platforms

- Each completed test session writes a CSV to `sessions/<date>/<id>_<timestamp>.csv`,
  created next to the running executable (inside `Contents/MacOS/` on the
  macOS bundle). Collect this folder back from testers after they finish.
- Don't run the build from a read-only/protected system directory (e.g.
  `Program Files`) — the app writes session logs next to itself, so it
  needs write access to its own folder. Desktop/Downloads/a normal user
  folder is fine.
- `config.ini` and the two `transparency_*.txt` scenario files are baked
  into the build at compile time. To ship a different config, edit those
  files before building (or before tagging, for the automated path).
