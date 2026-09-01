<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🪟 Windows Installation
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="INSTALL_WINDOWS.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

Guide to install, configure, start, and get TrinaxAI running on Windows 10/11 with PowerShell.

## Support status

The Windows installer is available and CI validates Python/CLI smoke tests, PowerShell syntax, dry-runs, and the URL-based source download flow. A full install with real dependency/model downloads and first-run behavior still requires the machine-level smoke test in [TESTING.md](../TESTING.md).

## What you'll have running

When done, you should have:

- Ollama installed and responding at `http://localhost:11434`.
- RAG API at `https://localhost:3333` when the managed certificate is available (HTTP is the fallback).
- PWA at `https://localhost:3334`.
- Python `.venv` environment.
- PWA dependencies installed.
- Base models downloaded if you choose that option.
- `.env` generated.
- Optional autostart from the Windows Startup folder: the PWA comes back on boot and the AI respects whether it was left on or off.

## Requirements

| Resource | Minimum | Recommended |
|---|---:|---:|
| Windows | 10/11 | 11 |
| RAM | 8 GB | 16 GB or more |
| Free disk | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 22 | 24 LTS |
| Ollama | Yes | Latest version |
| PowerShell | 5+ | PowerShell 7 |

## Recommended release-pinned install

> Release status: `v1.2.0` is the current candidate, but its GitHub Release assets are not published yet. The command below is ready for the published release; for immediate testing, use the local checkout with `powershell -ExecutionPolicy Bypass -File .\install.ps1`. The installer intentionally refuses to fall back to `main`.

Open PowerShell and run:

```powershell
$ErrorActionPreference = "Stop"
$version = "1.2.0"
if ($version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Invalid release version" }
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

The installer downloads the source ZIP directly from GitHub. It does not need Git, Python, or Node.js beforehand; it installs the required dependencies, configures Ollama, builds the PWA, and starts TrinaxAI. Approve administrator permission when Windows requests it.
The SHA-256 manifest check above is required before execution. Detached GPG verification is an optional additional check only when the signing-key fingerprint was obtained and trusted independently; a key or fingerprint downloaded from the same release is not an authenticity anchor. The repository does not yet ship a pinned public-key trust anchor.

## Optional reviewed PowerShell install

Open PowerShell and download, inspect, then run the guided installer. It downloads TrinaxAI to `%LOCALAPPDATA%\TrinaxAI` by default:

```powershell
$ErrorActionPreference = "Stop"
$version = "1.2.0"
if ($version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Invalid release version" }
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

The installer:

- Detects RAM and selects a profile.
- Creates `.env`.
- Installs dependencies automatically. Ollama tries the official installer first, verifies the signed `OllamaSetup.exe` fallback when needed, and uses `winget` as a final fallback.
- Creates `.venv`.
- Installs Python packages.
- Installs and builds the PWA.
- Asks whether to download Ollama models.
- Asks whether to enable Windows startup.
- Asks whether to start services now.

Required dependencies are installed automatically. Optional choices such as models, startup, and service start are prompted by default. Legacy LAN-system configuration is accepted for compatibility but never grants remote host administration. Use `-NonInteractive` for scripted installs. If the automatic paths cannot finish, the signed official `OllamaSetup.exe` opens in its own window; select **Install**, wait for it to finish, and rerun the installer if PowerShell still cannot find `ollama.exe`.

Use `-NoStart` to leave TrinaxAI stopped; Windows boot autostart is skipped too and can be enabled later after starting TrinaxAI.

If you already have the project or want to select another install directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -InstallDir "D:\Apps\TrinaxAI"
```

Running from a local checkout is an operator/development mode and is intentionally not blocked; review and protect that checkout separately from the verified release-download flow.

After installation, manage TrinaxAI from any directory:

```powershell
trinaxai doctor
trinaxai update
trinaxai uninstall
```

`trinaxai uninstall` is guided. `trinaxai uninstall -y` uses safe defaults and preserves indexes and Ollama models unless their removal is explicitly requested.

## Install dependencies manually

You can install with `winget`:

```powershell
winget install --id Python.Python.3.12 --silent
winget install --id OpenJS.NodeJS.LTS --silent
winget install --id Ollama.Ollama --silent
```

Or download manually:

- Python: `https://python.org`
- Node.js LTS: `https://nodejs.org`
- Ollama: `https://ollama.com/download/windows`

Close and reopen PowerShell after installing to refresh `PATH`.

Verify:

```powershell
python --version
node --version
npm --version
ollama --version
```

## Manual install

### 1. Download the release archive

```powershell
$ErrorActionPreference = "Stop"
$version = "1.2.0"
if ($version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Invalid release version" }
$base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
$zip = "$env:TEMP\TrinaxAI-$version.zip"
$manifest = "$env:TEMP\TrinaxAI-$version-SHA256SUMS"
Invoke-WebRequest -Uri "$base/TrinaxAI-$version.zip" -OutFile $zip
Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
$line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version\.zip$" } | Select-Object -First 1
$expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Source archive SHA-256 verification failed." }
Expand-Archive $zip $env:TEMP -Force
Move-Item "$env:TEMP\TrinaxAI-$version" "$env:USERPROFILE\trinaxai"
cd $env:USERPROFILE\trinaxai
```

### 2. Create Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
```

### 3. Install the PWA

```powershell
cd chat-pwa
npm ci
npm run build
cd ..
```

### 4. Start Ollama

Open the Ollama app or run:

```powershell
ollama serve
```

In another terminal, verify:

```powershell
ollama list
```

### 5. Create `.env`

```powershell
Copy-Item .env.example .env
```

Recommended values (leave the profile automatic unless you need an explicit override):

```text
# Leave unset for CPU/RAM/GPU detection.
#TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=./local_sources
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
TRINAXAI_RAG_HTTPS=1
TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
```

After changing Wi-Fi, renew the local address and HTTPS certificate:

```powershell
trinaxai network refresh
```

Use the IP URL it prints from phones on the same network; the `.local` URL is an alternative when mDNS works on the router.

## Download models

Recommended `16gb` profile:

```powershell
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
```

For every other profile, follow the current
[Models & profiles table](../README.md#models-and-hardware-profiles). The installer selects
and pulls the text/RAG fleet automatically. Vision models download on first
image analysis.

## Index your files

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe index.py
```

You can also open the PWA, go to settings, choose a folder, and assign it to a collection. TrinaxAI will copy the files to `local_sources\collections\` before indexing them.

## Start TrinaxAI

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe service_manager.py start --base-dir "$PWD"
```

The gateway is loopback-only by default. For intentional LAN access, set
`TRINAXAI_PWA_HOST=0.0.0.0` in `.env`, restart TrinaxAI, and pair the remote
browser before using it.

Open:

```text
https://localhost:3334
```

From a phone or tablet on the same Wi-Fi:

```text
https://YOUR-LAN-IP:3334
```

If the browser reports an untrusted certificate, install the public CA printed by
`trinaxai network` and trust it on that device. Do not bypass the warning for a
LAN connection; see [LAN pairing and HTTPS trust](NETWORK_PAIRING.md).

## Shut down, restart, and check status

Shut down the AI and leave the PWA available:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-ai --base-dir "$PWD"
```

Shut down everything:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-all --base-dir "$PWD"
```

This leaves only the loopback recovery page at `https://localhost:3334`; LAN access stays closed until you start TrinaxAI there.

Check status:

```powershell
.\.venv\Scripts\python.exe service_manager.py status --base-dir "$PWD"
```

Manual supervisor:

```powershell
.\.venv\Scripts\python.exe service_manager.py watch --base-dir "$PWD"
```

## Autostart on Windows

The installer enables it automatically. The supervisor always tries to keep the PWA available; if you shut down the AI from the PWA or with `service_manager.py stop-ai`, the next boot will not start Ollama/RAG until you turn the AI back on.

Enable:

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe service_manager.py enable-autostart --base-dir "$PWD"
```

This creates `TrinaxAI.vbs` in the Windows Startup folder so no console window stays visible.

Disable:

```powershell
.\.venv\Scripts\python.exe service_manager.py disable-autostart --base-dir "$PWD"
```

You can also browse the Startup folder directly:

```powershell
explorer "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
```

## Verify everything works

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe test_system.py --verbose
```

Manual checks:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
Invoke-RestMethod https://localhost:3333/health
```

If your PowerShell does not support `-SkipCertificateCheck`, open in a browser:

```text
https://localhost:3333/health
```

## Daily use

1. Open `https://localhost:3334`.
2. Use Ollama for general chat.
3. Use RAG to query indexed files.
4. Use collections to separate projects.
5. Install the PWA from Chrome or Edge using the install icon in the address bar.

## Update

Use the native Windows updater:

```powershell
cd $env:USERPROFILE\trinaxai
powershell -ExecutionPolicy Bypass -File .\update.ps1
```

The updater asks whether to create a backup, pull latest code, update models, change autostart, restart services, and run the readiness audit. Python/npm dependencies and the PWA build still run automatically.

The installer creates a weekly Windows task named `TrinaxAI Weekly Update`.
Despite the historical name, it is check-only: it records update availability
in `logs\auto-update.log` and never downloads/executes an updater or changes the
installation. Review the tagged release and run `update.ps1` manually.

## Backups

Back up manually:

- `.env`
- `storage\`
- `local_sources\`

If Bash is available:

```bash
./backup.sh create
```

The archive contains `.env`, chats, attachments, sources and indexes. The
script makes it private (`0600` where supported); encrypt off-host copies. A
restore validates paths/types, stages extraction and rolls back failed
replacement. Test restoration before upgrading.

## Uninstall

Use the native Windows uninstaller:

```powershell
cd $env:USERPROFILE\trinaxai
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

It asks which runtime files to remove. RAG data and Ollama models are kept unless you choose to remove them.

## Firewall and local network

| Port | Service | Purpose |
|---:|---|---|
| 11434 | Ollama | Local models |
| 3333 | RAG API | Backend |
| 3334 | PWA | Web interface |

To access from a phone/tablet, allow the PWA gateway on port `3334` on private
networks only. Keep FastAPI `3333` and Ollama `11434` on loopback and do not
allow them on public networks.

## Common issues

| Problem | Solution |
|---|---|
| `python` not recognized | Reinstall Python with `Add python.exe to PATH` checked. |
| `npm` not recognized | Install Node.js LTS and open a new terminal. |
| `ollama` not recognized | Re-run `install.ps1`; it refreshes PATH and opens the signed official installer if the automatic paths fail. |
| PowerShell permission error | Run with `-ExecutionPolicy Bypass`. |
| PWA cannot open from phone | Run `trinaxai network refresh`, open the reported `https://HOST-LAN-IP:3334` URL, and allow the gateway on the private-network firewall. |
| HTTPS API shows invalid certificate | Install/trust the public CA from `trinaxai network` on the device; do not bypass TLS on a LAN. See [LAN pairing and HTTPS trust](NETWORK_PAIRING.md). |
| Out of memory | Use the `8gb` profile. Its text roles use `qwen3.5:2b` plus `qwen3-embedding:0.6b`; reduce context if necessary. |

## Note on WSL

You can run TrinaxAI inside WSL2 using the Linux guide, but for Windows users the most direct path is PowerShell + `install.ps1`. If you use WSL2, keep in mind that networking, firewall, and file access work differently between Windows and Linux.

## Security

Keep FastAPI `3333` and Ollama `11434` on loopback; expose only the PWA
gateway on `3334` to a trusted private network. Do not expose these ports to the
internet. Use a VPN for remote access. System administration is always
localhost-only; the legacy variable below is accepted for old `.env` files but
cannot grant LAN authority:

```text
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=a-long-token
```
