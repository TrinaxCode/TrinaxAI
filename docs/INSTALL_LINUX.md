# TrinaxAI on Linux

Guide to install, configure, start, and get TrinaxAI running on Linux. Applies to Ubuntu, Debian, Fedora, Arch, openSUSE, and similar distributions.

## What you'll have running

When done, you should have:

- Ollama running locally at `http://localhost:11434`.
- TrinaxAI RAG API at `http://localhost:3333`.
- TrinaxAI PWA at `https://localhost:3334`.
- Base models downloaded if you choose that option.
- Python `.venv` environment installed.
- Frontend dependencies installed.
- `.env` generated with your machine's profile.
- Optional user autostart with systemd: the PWA comes back on boot and the AI respects whether it was left on or off.

## Requirements

| Resource | Minimum | Recommended |
|---|---:|---:|
| RAM | 8 GB | 16 GB or more |
| Free disk | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 18 | 20 LTS |
| Git | Yes | Yes |
| Ollama | Yes | Latest version |

If you use NVIDIA, install the drivers before downloading large models. TrinaxAI also works CPU-only, but responses will be slower.

## Recommended guided install

From a terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash
```

The installer clones the project to `~/trinaxai` if it doesn't exist yet, detects your RAM, creates `.env`, installs required dependencies, and prepares the PWA automatically. Optional choices such as model downloads, LAN system control, autostart, and starting services are prompted by default. Use `./install.sh --non-interactive` for scripted installs.

If you already cloned the repository:

```bash
cd /path/to/TrinaxAI
chmod +x install.sh
./install.sh
```

The profile is chosen automatically. In interactive mode, choose `Normal` unless you know you want a specific profile:

- `8gb`: low-memory machines.
- `16gb`: balanced profile.
- `max`: more RAM/CPU, larger models.
- `ultra`: 32 GB+ and powerful hardware.

## Manual install

Use these steps if you prefer to review each part.

### 1. Install system dependencies

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv curl git unzip nodejs npm
```

Fedora:

```bash
sudo dnf install -y python3 python3-pip curl git unzip nodejs npm
```

Arch:

```bash
sudo pacman -Sy --needed python python-pip curl git unzip nodejs npm
```

openSUSE:

```bash
sudo zypper install python3 python3-pip curl git unzip nodejs npm
```

### 2. Clone the project

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git ~/trinaxai
cd ~/trinaxai
```

### 3. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Install the PWA

```bash
cd chat-pwa
npm install
npm run build
cd ..
```

### 5. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify it responds:

```bash
ollama --version
ollama list
```

### 6. Create `.env`

You can copy the template:

```bash
cp .env.example .env
```

Recommended starting values:

```bash
TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=0.0.0.0
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_ALLOW_LAN_SYSTEM=1
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=0.0.0.0
VITE_TRINAXAI_RAG_TARGET=http://localhost:3333
```

If you want to access TrinaxAI from a phone on the same network, add your local IP to `TRINAXAI_CORS_ORIGINS`:

```bash
hostname -I
```

Example:

```bash
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://192.168.1.25:3334,http://192.168.1.25:3334
```

## Download models

Base models:

```bash
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull bge-m3
```

Vision:

```bash
ollama pull qwen2.5vl:3b
```

Machines with more memory:

```bash
ollama pull qwen2.5-coder:7b
```

Ultra profile:

```bash
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5vl:7b
```

## Index your files

Indexing creates the local knowledge base used by RAG.

```bash
cd ~/trinaxai
source .venv/bin/activate
python index.py
```

You can also index from the PWA: open `https://localhost:3334`, go to settings, choose a folder and assign it to a collection.

Files imported through the browser are copied to `local_sources/collections/`. The browser does not expose the original absolute path for security reasons.

## Start TrinaxAI

Recommended way:

```bash
cd ~/trinaxai
./startup_ai.sh
```

Direct alternative:

```bash
.venv/bin/python service_manager.py start --base-dir "$PWD"
```

Open:

```text
https://localhost:3334
```

From a phone or tablet on the same Wi-Fi:

```text
https://YOUR-LAN-IP:3334
```

Accept the certificate warning if it appears. It is a local/self-signed certificate.

## Shut down, restart, and check status

Shut down only the AI services, leaving the PWA available:

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

Supervisor in the foreground:

```bash
.venv/bin/python service_manager.py watch --base-dir "$PWD"
```

## Autostart

The installer enables it automatically. The supervisor always tries to keep the PWA available; if you shut down the AI with `./shutdown_ai.sh` or from the PWA, the next boot will not start Ollama/RAG until you turn the AI back on.

### Safe per-user option

This creates a user systemd service and does not require writing to `/etc`:

```bash
cd ~/trinaxai
.venv/bin/python service_manager.py enable-autostart --base-dir "$PWD"
```

Disable:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

### Advanced option with system systemd

`setup_trinaxai.sh` is Linux-only. It creates systemd units in `/etc/systemd/system`, configures Ollama, and adds a sudoers rule to allow starting/stopping from the PWA without a password prompt.

Run it only if you understand that permission change:

```bash
cd ~/trinaxai
sudo ./setup_trinaxai.sh
```

Check services:

```bash
systemctl status ollama
systemctl status ai-rag
systemctl status trinaxai-frontend
```

Logs:

```bash
journalctl -u ai-rag -f
journalctl -u trinaxai-frontend -f
```

## Verify everything works

```bash
cd ~/trinaxai
.venv/bin/python test_system.py --verbose
```

You can also check manually:

```bash
curl http://localhost:11434/api/tags
curl http://localhost:3333/health
```

The PWA should open at:

```text
https://localhost:3334
```

## Daily use

1. Start TrinaxAI with `./startup_ai.sh` or leave autostart enabled.
2. Open `https://localhost:3334`.
3. Use Ollama mode for general chat.
4. Use RAG mode for questions about your indexed files.
5. Create collections to separate projects or topics.
6. Attach files temporarily if you don't want to index them.
7. Use phrases like `remember that...` to save explicit local memory.

## Update

```bash
cd ~/trinaxai
./update.sh
```

The updater asks whether to create a backup, pull latest code, update models, change autostart, restart services, and run the readiness audit. Python/npm dependencies and the PWA build still run automatically.

If you update manually:

```bash
git pull
source .venv/bin/activate
python -m pip install -r requirements.txt
cd chat-pwa
npm install
npm run build
cd ..
```

## Backups

Create a backup:

```bash
./backup.sh create
```

Manually back up the important files:

- `.env`
- `storage/`
- `local_sources/`

## Uninstall

```bash
./uninstall.sh
```

The uninstaller asks which runtime files to remove. RAG data and Ollama models are kept unless you choose to remove them.

To preselect removing Ollama models:

```bash
./uninstall.sh --remove-models
```

## Ports and firewall

| Port | Service | Purpose |
|---:|---|---|
| 11434 | Ollama | Local models |
| 3333 | RAG API | FastAPI backend |
| 3334 | PWA | Web interface |

If you use a phone/tablet, allow `3333` and `3334` only on your private network. Do not expose these ports to the internet.

Ollama has no built-in authentication. If `OLLAMA_HOST=0.0.0.0`, other devices on your LAN could use your models. For remote access, use a VPN such as Tailscale or WireGuard.

## Common issues

| Problem | Solution |
|---|---|
| `python3 -m venv` fails | Install `python3-venv`. |
| PWA does not open | Run `cd chat-pwa && npm run dev`. |
| API does not respond | Run `./startup_ai.sh` and check `logs/rag_api.log`. |
| Model not found | Run `ollama pull model-name`. |
| Phone cannot connect | Add your LAN IP to `TRINAXAI_CORS_ORIGINS` and check your firewall. |
| Untrusted certificate | Accept the warning for local use. |
| Slow responses | Use smaller models or a lower profile with `TRINAXAI_PROFILE=8gb ./install.sh`. |
