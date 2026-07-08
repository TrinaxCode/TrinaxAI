# TrinaxAI on Windows

Guide to install, configure, start, and get TrinaxAI running on Windows 10/11 with PowerShell.

## Support status

The Windows installer is available and CI now validates Python smoke tests, CLI smoke tests, and PowerShell syntax on Windows. Full end-to-end installer validation on a real Windows machine is still pending.

## What you'll have running

When done, you should have:

- Ollama installed and responding at `http://localhost:11434`.
- RAG API at `http://localhost:3333`.
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
| Node.js | 18 | 20 LTS |
| Git | Yes | Yes |
| Ollama | Yes | Latest version |
| PowerShell | 5+ | PowerShell 7 |

Install Python with the `Add python.exe to PATH` option checked.

## Recommended guided install

Open PowerShell in the project folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer:

- Detects RAM and selects a profile.
- Creates `.env`.
- Installs dependencies automatically. Ollama uses `winget` first, then the official silent installer fallback if needed.
- Creates `.venv`.
- Installs Python packages.
- Installs and builds the PWA.
- Asks whether to download Ollama models.
- Asks whether to enable Windows startup.
- Asks whether to start services now.

Required dependencies are installed automatically. Optional choices such as models, LAN system control, startup, and service start are prompted by default. Use `-NonInteractive` for scripted installs. The installer should not send you to a browser to download Ollama manually.

If you don't have the project yet:

```powershell
git clone https://github.com/TrinaxCode/TrinaxAI.git $env:USERPROFILE\trinaxai
cd $env:USERPROFILE\trinaxai
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

## Install dependencies manually

You can install with `winget`:

```powershell
winget install --id Python.Python.3.12 --silent
winget install --id Git.Git --silent
winget install --id OpenJS.NodeJS.LTS --silent
winget install --id Ollama.Ollama --silent
```

Or download manually:

- Python: `https://python.org`
- Git: `https://git-scm.com`
- Node.js LTS: `https://nodejs.org`
- Ollama: `https://ollama.com/download/windows`

Close and reopen PowerShell after installing to refresh `PATH`.

Verify:

```powershell
python --version
git --version
node --version
npm --version
ollama --version
```

## Manual install

### 1. Clone the project

```powershell
git clone https://github.com/TrinaxCode/TrinaxAI.git $env:USERPROFILE\trinaxai
cd $env:USERPROFILE\trinaxai
```

### 2. Create Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Install the PWA

```powershell
cd chat-pwa
npm install
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

Recommended values:

```text
TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=0.0.0.0
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
TRINAXAI_RAG_HTTPS=1
TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
```

To use a phone/tablet, find your LAN IP:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -match "^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[0-1]))" } |
  Select-Object -First 1 IPAddress
```

Add that IP to `TRINAXAI_CORS_ORIGINS`, for example:

```text
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://192.168.1.25:3334,http://192.168.1.25:3334
```

## Download models

Base:

```powershell
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull bge-m3
```

Vision:

```powershell
ollama pull qwen2.5vl:3b
```

Machines with 16 GB or more:

```powershell
ollama pull qwen2.5-coder:7b
```

Machines with 32 GB or more:

```powershell
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5vl:7b
```

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

Open:

```text
https://localhost:3334
```

From a phone or tablet on the same Wi-Fi:

```text
https://YOUR-LAN-IP:3334
```

Accept the local certificate warning if it appears.

## Shut down, restart, and check status

Shut down the AI and leave the PWA available:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-ai --base-dir "$PWD"
```

Shut down everything:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-all --base-dir "$PWD"
```

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
Invoke-RestMethod http://localhost:3333/health
```

If your PowerShell does not support `-SkipCertificateCheck`, open in a browser:

```text
http://localhost:3333/health
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

## Backups

Back up manually:

- `.env`
- `storage\`
- `local_sources\`

If you have Git Bash:

```bash
./backup.sh create
```

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

To access from a phone/tablet, Windows Defender Firewall must allow Node/Python on private networks. Do not allow these ports on public networks.

## Common issues

| Problem | Solution |
|---|---|
| `python` not recognized | Reinstall Python with `Add python.exe to PATH` checked. |
| `npm` not recognized | Install Node.js LTS and open a new terminal. |
| `ollama` not recognized | Re-run `install.ps1`; it refreshes PATH and installs Ollama with the official silent installer if `winget` fails. |
| PowerShell permission error | Run with `-ExecutionPolicy Bypass`. |
| PWA cannot open from phone | Run PowerShell as Administrator and re-run `install.ps1` so it can add Private-network firewall rules for TCP 3333/3334. Also verify same Wi-Fi. |
| HTTPS API shows invalid certificate | Normal with a local certificate; accept the warning. |
| Out of memory | Use the `8gb` profile. It installs `llama3.2:1b`, `qwen2.5-coder:1.5b`, and `nomic-embed-text` by default. |

## Note on WSL

You can run TrinaxAI inside WSL2 using the Linux guide, but for Windows users the most direct path is PowerShell + `install.ps1`. If you use WSL2, keep in mind that networking, firewall, and file access work differently between Windows and Linux.

## Security

Do not expose `3333`, `3334`, or `11434` to the internet. Use a VPN for remote access. If you need to block system actions outside of localhost:

```text
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=a-long-token
```
