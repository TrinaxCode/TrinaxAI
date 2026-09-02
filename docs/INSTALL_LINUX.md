<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🐧 Linux Installation
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="INSTALL_LINUX.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

Guide to install, configure, start, and get TrinaxAI running on Linux. Applies to Ubuntu, Debian, Fedora, Arch, openSUSE, and similar distributions.

## Support status

Linux is the primary CI-tested platform. Current CI validates backend tests, frontend tests/build, CLI smoke tests, public-readiness checks, and shell syntax on Ubuntu. Full end-to-end installer validation across every listed distribution is still pending.

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
| Node.js | 22 | 24 LTS |
| Git | Not required | Development only |
| Ollama | Yes | Latest version |

If you use NVIDIA, install the drivers before downloading large models. TrinaxAI also works CPU-only, but responses will be slower.

## Recommended release-pinned install

> Release status: `v1.2.1` is Production/Stable. Its signed archives, installers, wheel, checksums, and signatures are published on GitHub. The installer never falls back to `main`.

```bash
set -e; version="1.2.1"; base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"; installer="$(mktemp)"; trap 'rm -f "$installer"' EXIT; curl -fsSL "$base/TrinaxAI-${version}-installer.sh" -o "$installer"; expected="$(curl -fsSL "$base/SHA256SUMS" | awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }')"; actual="$( (shasum -a 256 "$installer" 2>/dev/null || sha256sum "$installer") | awk '{print $1}' )"; test "$expected" = "$actual"; bash "$installer"
```

The installer downloads the source archive directly from GitHub. It does not need Git, detects your hardware, installs the required dependencies, configures Ollama, builds the PWA, verifies a smoke inference, and starts TrinaxAI. Approve the password prompt when your distribution asks to install system packages. For manual checksum or GPG review, see [Release signing](RELEASE_SIGNING.md).

## Installer options

The release-pinned command above is the normal path. For a local checkout:

```bash
cd /path/to/TrinaxAI
./install.sh
```

The installer uses `$XDG_DATA_HOME/trinaxai` (normally `~/.local/share/trinaxai`) for a new installation, while continuing to recognize an existing legacy `~/trinaxai` install. It detects RAM, creates `.env`, installs required dependencies, and prepares the PWA automatically. Optional choices such as model downloads, autostart, and starting services are prompted by default. Host administration remains localhost-only.

Use `./install.sh --no-start` to leave TrinaxAI stopped; boot autostart is skipped too and can be enabled later after starting TrinaxAI.

Choose a different application directory when needed:

Set `TRINAXAI_HOME` or pass `--install-dir PATH` when you need a custom location.

After installation, lifecycle operations do not require changing directories:

```bash
trinaxai doctor
trinaxai update
trinaxai uninstall
```

Use `trinaxai update -y` or `trinaxai uninstall -y` for safe non-interactive defaults. Personal indexes and Ollama models are preserved unless you explicitly request their removal.

Running from a local checkout is an operator/development mode and is intentionally not blocked; review and protect that checkout separately from the verified release-download flow.

The profile is chosen automatically. In interactive mode, choose `Normal` unless you know you want a specific profile:

- `8gb`: low-memory machines.
- `16gb`: balanced profile.
- `32gb`: more RAM or a capable GPU.
- `64gb`: abundant memory or a powerful GPU.

## Manual install

Use these steps if you prefer to review each part.

### 1. Install system dependencies

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv curl unzip nodejs npm
```

Fedora:

```bash
sudo dnf install -y python3 python3-pip curl unzip nodejs npm
```

Arch:

```bash
sudo pacman -Sy --needed python python-pip curl unzip nodejs npm
```

openSUSE:

```bash
sudo zypper install python3 python3-pip curl unzip nodejs npm
```

### 2. Download the release archive

```bash
set -eu
version="1.2.1"
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
mkdir -p ~/trinaxai
archive="$(mktemp)"
manifest="$(mktemp)"
trap 'rm -f "$archive" "$manifest"' EXIT
curl --fail --location --output "$archive" "${base}/TrinaxAI-${version}.tar.gz"
curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
expected="$(awk -v asset="TrinaxAI-${version}.tar.gz" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$archive" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$archive" | awk '{print $1}')"; else echo "A SHA-256 tool (sha256sum or shasum) is required." >&2; exit 2; fi
if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Source archive SHA-256 verification failed." >&2; exit 1; fi
tar -xzf "$archive" --strip-components=1 -C ~/trinaxai
cd ~/trinaxai
```

### 3. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements.lock
```

### 4. Install the PWA

```bash
cd chat-pwa
npm ci
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

Recommended starting values (leave the profile automatic unless you need an explicit override):

```bash
# Leave unset for CPU/RAM/GPU detection.
#TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=./local_sources
# Deprecated compatibility value; host administration is always localhost-only.
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
VITE_TRINAXAI_RAG_TARGET=http://localhost:3333
```

If you change networks or want to connect a phone on the same Wi-Fi, let TrinaxAI renew its local address and HTTPS certificate:

```bash
trinaxai network refresh
```

Open the IP URL it prints. The `.local` URL is an alternative when mDNS works on the router. A cached PWA at an old IP is an offline shell, not a second running installation.

## Download models

Recommended `16gb` profile:

```bash
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
```

For `8gb`, `32gb`, and `64gb`, use the exact current fleet in the
[Models & profiles table](../README.md#models-and-hardware-profiles). The installer pulls
the text/RAG set automatically. Vision models download on first image analysis;
manual pulls are only needed for custom setups.

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

### Advanced option with system-wide systemd

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

## Optional Docker backend

This first stage containerizes only the RAG API. The PWA, security gateway, and
Ollama continue to run on the host.

Requirements: Docker Compose and Ollama installed on the host.

```bash
cd ~/trinaxai
cp .env.example .env
mkdir -p projects storage local_sources
```

In `.env`, change the API target to HTTP because the container does not
terminate TLS:

```dotenv
TRINAXAI_RAG_TARGET=http://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=http://127.0.0.1:3333
```

Then start only the host PWA gateway and the Docker API:

```bash
export TRINAXAI_DOCKER_UID="$(id -u)"
export TRINAXAI_DOCKER_GID="$(id -g)"
export TRINAXAI_DOCKER_IMAGE=ghcr.io/trinaxcode/trinaxai:1.2.1
docker compose pull
docker compose up --no-build -d
.venv/bin/python service_manager.py start-frontend --base-dir "$PWD"
```

The registry also publishes `1.2`, `1`, and `latest` tags. Pin `1.2.1` for a
reproducible deployment. To build the current checkout instead, omit
`TRINAXAI_DOCKER_IMAGE` and run `docker compose up --build -d`.

The API is published only on `127.0.0.1:3333`, so the native PWA can keep
using its gateway on `3334`. Indexes, sources, and secrets remain in
`storage/` and `local_sources/` through persistent mounts.

By default, the container looks for Ollama at
`http://host.docker.internal:11434`. On Linux, Ollama must accept connections
from Docker's network; configure its bind deliberately and restrict access
with the firewall. Compose uses the private `172.31.0.0/24` subnet to transport
the HMAC identity; if it is already in use, set `TRINAXAI_DOCKER_NETWORK_CIDR`
to another free private subnet. To use another Ollama address:

```bash
TRINAXAI_DOCKER_OLLAMA_URL=http://host.docker.internal:11434 \
  docker compose up --no-build -d
```

The container indexes `./projects` read-only. To use another host directory,
set `TRINAXAI_DOCKER_INDEX_DIR` before starting:

```bash
TRINAXAI_DOCKER_INDEX_DIR=/path/to/documents docker compose up --no-build -d
```

Check status and stop it with:

```bash
curl http://127.0.0.1:3333/health
docker compose ps
docker compose down
```

This profile does not containerize the PWA or Ollama yet, and port `3333` must
not be exposed outside the host. Do not use `startup_ai.sh` or `start-ai` while
this Compose profile is active; they would try to start another API on the
same port.

The `.env` file is optional for Compose. Without it, the safe defaults in
`compose.yaml` are used; add `.env` only when you need application overrides.

## Update

```bash
cd ~/trinaxai
./update.sh
```

The updater asks whether to create a backup, pull latest code, update models, change autostart, restart services, and run the readiness audit. Python/npm dependencies and the PWA build still run automatically.

The installer also enables a persistent user timer that checks GitHub weekly
and records whether an update is available in `logs/auto-update.log`. It is
check-only: it does not download/execute an updater or modify services. Review
the tagged release and run the local guided updater manually. Disable the check
with `python scripts/auto_update.py disable`.

If you update manually:

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

Create a backup:

```bash
./backup.sh create
```

The archive is created through a temporary file, published with mode `0600`,
and contains `.env` plus private chats, attachments, sources and indexes. Encrypt
copies moved off-host. Restore validates paths and entry types, extracts to
staging, and rolls back a failed replacement; still test restoration before an
upgrade.

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

If you use a phone/tablet, allow only the PWA gateway on `3334` on your private
network. Keep FastAPI `3333` and Ollama `11434` bound to loopback; do not expose
them to the LAN or internet.

Ollama has no built-in authentication. If `OLLAMA_HOST=0.0.0.0`, other devices on your LAN could use your models. For remote access, use a VPN such as Tailscale or WireGuard.

## Common issues

| Problem | Solution |
|---|---|
| `python3 -m venv` fails | Install `python3-venv`. |
| PWA does not open | Run `cd chat-pwa && npm run dev`. |
| API does not respond | Run `./startup_ai.sh` and check `logs/rag_api.log`. |
| Model not found | Run `ollama pull model-name`. |
| Phone cannot connect | Run `trinaxai network refresh`, open the reported `https://HOST-LAN-IP:3334` URL, and allow only the gateway on the private-network firewall. |
| Untrusted certificate | Install/trust the public CA from `trinaxai network` on the device; do not bypass TLS on a LAN. See [LAN pairing and HTTPS trust](NETWORK_PAIRING.md). |
| Slow responses | Use smaller models or a lower profile with `TRINAXAI_PROFILE=8gb ./install.sh`. |
