# TrinaxAI on macOS

Guide to install, configure, start, and get TrinaxAI running on macOS, both Apple Silicon and Intel.

## Support status

The macOS installer is available and CI now validates Python tests, CLI smoke tests, and bash syntax on macOS. Full end-to-end installer validation on real macOS hardware is still pending.

## What you'll have running

When done, you should have:

- Ollama running locally at `http://localhost:11434`.
- TrinaxAI RAG API at `http://localhost:3333`.
- PWA at `https://localhost:3334`.
- Python `.venv` environment ready.
- PWA dependencies installed.
- Base models downloaded if you choose that option.
- `.env` generated.
- Optional autostart with LaunchAgent: the PWA comes back on boot and the AI respects whether it was left on or off.

## Requirements

| Resource | Minimum | Recommended |
|---|---:|---:|
| macOS | A version supported by Homebrew/Ollama | Latest stable |
| RAM | 8 GB | 16 GB or more |
| Free disk | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 18 | 20 LTS |
| Homebrew | Recommended | Yes |
| Ollama | Yes | Latest version |

Apple Silicon uses Metal automatically through Ollama when the model supports it.

## Install base tools

Install Xcode Command Line Tools:

```bash
xcode-select --install
```

Install Homebrew if you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install dependencies:

```bash
brew install python@3.12 node git curl ollama
```

You can also install Ollama from the official macOS app and keep it open.

## Recommended guided install

If you already have the repository:

```bash
cd /path/to/TrinaxAI
bash install.sh
```

If you don't have it yet, use the guided one-command installer. New installs live in `~/Library/Application Support/TrinaxAI`:

```bash
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash
```

The installer detects RAM, creates `.env`, sets up Python, and installs the PWA automatically. Optional choices such as model downloads, LAN system control, autostart, and starting services are prompted by default. Use `bash install.sh --non-interactive` for scripted installs.

The profile is chosen automatically. In interactive mode, choose `Normal` to use the recommended profile. Use `Advanced` only if you want to force `8gb`, `16gb`, `max`, or `ultra`.

After installation, manage it from any directory:

```bash
trinaxai doctor
trinaxai update
trinaxai uninstall
```

The uninstaller removes the TrinaxAI launcher and, when requested, its local trusted certificate. User data and Ollama models remain opt-in removals.

## Manual install

### 1. Clone the project

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git ~/trinaxai
cd ~/trinaxai
```

### 2. Create Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Install the PWA

```bash
cd chat-pwa
npm install
npm run build
cd ..
```

### 4. Start Ollama

If you installed Ollama with Homebrew:

```bash
ollama serve
```

Leave that process open or use TrinaxAI's autostart. If you installed the official Ollama app, open the app and verify:

```bash
ollama list
```

### 5. Create `.env`

```bash
cp .env.example .env
```

Recommended values:

```bash
TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
VITE_TRINAXAI_RAG_TARGET=http://localhost:3333
```

To use a phone on the same Wi-Fi, find your IP:

```bash
ipconfig getifaddr en0
```

If `en0` returns nothing:

```bash
ipconfig getifaddr en1
```

Add that IP to `TRINAXAI_CORS_ORIGINS`, for example:

```bash
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://192.168.1.25:3334,http://192.168.1.25:3334
```

## Download models

Recommended `16gb` profile:

```bash
ollama pull qwen2.5-coder:3b
ollama pull qwen3.5:9b
ollama pull granite4:3b
ollama pull bge-m3
```

For every other profile, follow the current
[Models & profiles table](../README.md#-models--profiles). The installer selects
and pulls the text/RAG fleet automatically. Vision models download on first
image analysis.

## Index your files

```bash
cd ~/trinaxai
source .venv/bin/activate
python index.py
```

You can also do it from the PWA in settings: choose a folder, assign it to a collection, and wait for the upload/indexing progress to complete.

macOS may ask for permission to access folders such as Documents, Desktop, or Downloads. Accept the permission if you want to index those locations.

## Start TrinaxAI

```bash
cd ~/trinaxai
./startup_ai.sh
```

Alternative:

```bash
.venv/bin/python service_manager.py start --base-dir "$PWD"
```

Open:

```text
https://localhost:3334
```

From a phone/tablet on the same Wi-Fi:

```text
https://YOUR-LAN-IP:3334
```

Accept the local certificate warning if it appears.

## Shut down, restart, and check status

Shut down the AI and leave the PWA available:

```bash
./shutdown_ai.sh
```

Shut down everything:

```bash
.venv/bin/python service_manager.py stop-all --base-dir "$PWD"
```

Check status:

```bash
.venv/bin/python service_manager.py status --base-dir "$PWD"
```

Manual supervisor:

```bash
.venv/bin/python service_manager.py watch --base-dir "$PWD"
```

## Autostart on macOS

The installer enables it automatically. TrinaxAI uses a LaunchAgent in `~/Library/LaunchAgents/`. The supervisor always tries to keep the PWA available; if you shut down the AI with `./shutdown_ai.sh` or from the PWA, the next boot will not start Ollama/RAG until you turn the AI back on.

Enable:

```bash
cd ~/trinaxai
.venv/bin/python service_manager.py enable-autostart --base-dir "$PWD"
```

Disable:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

Verify with `launchctl`:

```bash
launchctl list | grep trinax
```

Logs:

```bash
tail -f logs/supervisor.log
tail -f logs/rag_api.log
tail -f logs/frontend.log
```

## Verify everything works

```bash
cd ~/trinaxai
.venv/bin/python test_system.py --verbose
```

Manual checks:

```bash
curl http://localhost:11434/api/tags
curl http://localhost:3333/health
```

The PWA should open at:

```text
https://localhost:3334
```

## Daily use

1. Open `https://localhost:3334`.
2. Use Ollama for general chat.
3. Use RAG to query indexed folders and collections.
4. Install the PWA from Chrome/Edge or add it to the home screen from Safari on iPhone/iPad.

## Update

```bash
cd ~/trinaxai
./update.sh
```

The updater asks whether to create a backup, pull latest code, update models, change autostart, restart services, and run the readiness audit. Python/npm dependencies and the PWA build still run automatically.

The installer also creates a weekly check-only LaunchAgent. It records update
availability in `logs/auto-update.log` but never downloads/executes an updater
or changes the install. Review the tagged release and run the local updater
manually; disable checks with `python scripts/auto_update.py disable`.

Manual update:

```bash
git pull
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
cd chat-pwa
npm ci
npm run build
cd ..
```

## Backups

```bash
./backup.sh create
```

The archive is published with mode `0600` and contains `.env`, chats,
attachments, sources and indexes. Encrypt off-host copies. Restore validates
paths/types, stages extraction and rolls back a failed replacement; test it
before upgrading.

Important data:

- `.env`
- `storage/`
- `local_sources/`

## Uninstall

```bash
./uninstall.sh
```

The uninstaller asks which runtime files to remove. RAG data and Ollama models are kept unless you choose to remove them.

To preselect removing models:

```bash
./uninstall.sh --remove-models
```

If you enabled autostart:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

## Common issues

| Problem | Solution |
|---|---|
| `brew` not found | Install Homebrew and open a new terminal. |
| `python3` points to an old version | Install `python@3.12` and use `python3.12 -m venv .venv`. |
| Ollama does not respond | Open the Ollama app or run `ollama serve`. |
| macOS blocks folder access | Check System Settings > Privacy & Security > Files and Folders. |
| PWA cannot connect from iPhone | Make sure you're on the same Wi-Fi, LAN IP is in CORS, and firewall allows it. |
| Untrusted certificate | Accept the local certificate for `localhost` or your LAN IP. |
| Slow responses | Use 3B or 7B models depending on available RAM. |

## Security

Do not expose `3333`, `3334`, or `11434` to the internet. Use a VPN for remote access. If you need to restrict system actions to localhost only, configure:

```bash
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=a-long-token
```
