<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🧪 Installer Testing
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="TESTING.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="docs/README.md">Documentation</a> · <a href="README.md">Home</a> · <a href="docs/CHANGELOG.md">Changelog</a></sub></p>

These checks cover the URL-based lifecycle scripts, CLI behavior, and real-machine tests. Dry-run never downloads the source package or Ollama, installs packages, starts services, changes PATH, edits launch agents, or removes files.

> Release status: `v1.2.1` is Production/Stable. Its GitHub Release assets are published and the release-pinned installers never fall back to `main`.

## URL installer smoke test

Test the normal user journey on a clean machine with the published stable release. The SHA-256 manifest check in each download block is required before execution. The pinned public key and GPG verification procedure are documented in [Release signing](docs/RELEASE_SIGNING.md).

1. Download, inspect, and run a release-pinned installer.
   Linux/macOS:
   ```bash
   set -eu
   version="1.2.1"
   base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
   installer="$(mktemp)"
   manifest="$(mktemp)"
   trap 'rm -f "$installer" "$manifest"' EXIT
   curl --fail --location --output "$installer" "${base}/TrinaxAI-${version}-installer.sh"
   curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
   expected="$(awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
   if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$installer" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$installer" | awk '{print $1}')"; else echo "A SHA-256 tool (sha256sum or shasum) is required." >&2; exit 2; fi
   if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Installer SHA-256 verification failed." >&2; exit 1; fi
   bash -n "$installer"
   bash "$installer"
   ```
   Windows PowerShell:
   ```powershell
   $ErrorActionPreference = "Stop"
   $version = "1.2.1"
   $base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
   $installer = Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"
   $manifest = Join-Path $env:TEMP "TrinaxAI-$version-SHA256SUMS"
   Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer
   Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
   $line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1
   $expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
   $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
   if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }
   Get-Content -Path $installer
   & $installer
   ```
2. Confirm that the source archive is downloaded directly and Git is neither installed nor requested.
3. Open `https://localhost:3334`, then run `trinaxai update` and `trinaxai uninstall`.
4. Confirm that the detected profile is one of `8gb`, `16gb`, `32gb`, or `64gb`.

## Local Dry-Run

From the repository root:

```bash
chmod +x test-installers.sh
./test-installers.sh
./install.sh --dry-run
./update.sh --dry-run
./uninstall.sh --dry-run
```

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -DryRun
.\update.ps1 -DryRun
.\uninstall.ps1 -DryRun
```

The output must contain the localized access-links label: `Links to enter` in English or `Enlaces de acceso` in Spanish. The Windows install simulation also prints the official Ollama fallback instructions.

## Advanced script test: macOS real machine

Use a normal user account with Homebrew available or allow the installer to offer Homebrew installation. Review the script before running a network installer.

```bash
set -eu
version="1.2.1"
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
installer="$(mktemp)"
manifest="$(mktemp)"
trap 'rm -f "$installer" "$manifest"' EXIT
curl --fail --location --output "$installer" "${base}/TrinaxAI-${version}-installer.sh"
curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
expected="$(awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$installer" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$installer" | awk '{print $1}')"; else echo "A SHA-256 tool (sha256sum or shasum) is required." >&2; exit 2; fi
if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Installer SHA-256 verification failed." >&2; exit 1; fi
bash -n "$installer"
bash "$installer" --dry-run
bash "$installer"

cd "$HOME/Library/Application Support/TrinaxAI"
./update.sh --dry-run
./update.sh
./uninstall.sh --dry-run
./uninstall.sh
```

For a destructive removal of runtime data, models, certificates, and Ollama, use `./uninstall.sh --purge` only after confirming the data is backed up.

Verify the real install with `ollama list`, `curl -kfsS https://127.0.0.1:3333/health`, the localhost link, and the LAN link from another device on the same network.

## Advanced script test: Windows real machine

Run PowerShell as the user who will run TrinaxAI. The installer may request Administrator permission for firewall rules.

```powershell
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process Bypass
$version = "1.2.1"
$base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
$installer = Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"
$manifest = Join-Path $env:TEMP "TrinaxAI-$version-SHA256SUMS"
Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer
Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
$line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1
$expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }
Get-Content -Path $installer
& $installer
```

For a safe simulation from a downloaded script:

```powershell
$ErrorActionPreference = "Stop"
$version = "1.2.1"
$base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
$installer = Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"
$manifest = Join-Path $env:TEMP "TrinaxAI-$version-SHA256SUMS"
Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer
Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
$line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1
$expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -DryRun
```

After installation, run from the installation directory:

```powershell
.\update.ps1 -DryRun
.\update.ps1
.\uninstall.ps1 -DryRun
.\uninstall.ps1
```

If automatic Ollama installation fails, the official `OllamaSetup.exe` is opened. Click `Install`, wait for completion, then press Enter in the installer window. Confirm with `Get-Command ollama` and `& (Get-Command ollama).Source list`.

## GitHub Actions

`.github/workflows/test-installers.yml` runs syntax and dry-run checks on the pinned `ubuntu-24.04`, `macos-15`, and `windows-2025` runners. It does not install Ollama or attempt to emulate another operating system. The release workflow publishes source archives and URL installers and verifies every published download URL.

## RAG quality evaluation

The mandatory CI gate is deterministic and explicitly does not claim model
quality:

```bash
python scripts/evaluate_rag.py --deterministic --output rag-eval-report.json
```

For real evidence, start Ollama and the TrinaxAI backend, then upload and index
the heterogeneous fixture through the public API before evaluating it:

```bash
python scripts/evaluate_rag.py \
  --golden tests/fixtures/rag_live_golden.json \
  --api-url http://127.0.0.1:3333 \
  --index-corpus tests/fixtures/rag_eval/corpus \
  --collection-id rag-eval \
  --embed-model qwen3-embedding:0.6b \
  --timeout 900 \
  --output live-backend-rag-report.json
```

Alternatively, with the full golden corpus already indexed into `rag-eval`, run:

```bash
make rag-eval RAG_API_URL=http://127.0.0.1:3333
```

The live command fails when retrieval, grounding, citations, or abstention fall
below the configured thresholds. The manual `Live backend RAG` GitHub Actions
job performs this full path with Ollama; it is opt-in because model downloads
and inference are hardware-dependent.

## Documentation checks

For documentation-only changes, run the smallest relevant checks plus the PWA
documentation test:

```bash
cd chat-pwa
npx vitest run src/components/Docs.test.tsx
npx tsc --noEmit
cd ..
git diff --check
```

Review local Markdown targets manually after moving a file. Keep English and
`.es.md` counterparts aligned, verify every command against the current source
rather than copying an old example, and confirm that the recovery guide still
matches the actions exposed by `api_errors.ts` and `MessageList.tsx`.
