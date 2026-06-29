# 🚀 TrinaxAI — 100% Local AI Assistant

<p align="center">
  <strong>Open-source, local-first AI assistant with RAG, vision, voice, and PWA.</strong><br>
  Runs entirely on your machine. No cloud. No subscriptions. No limits.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg" alt="AGPL-3.0-or-later"></a>
  <a href="#"><img src="https://img.shields.io/badge/powered_by-Ollama-black.svg" alt="Ollama"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Linux|macOS|Windows-lightgrey.svg" alt="Platforms"></a>
  <a href="#"><img src="https://img.shields.io/badge/PWA-ready-brightgreen.svg" alt="PWA"></a>
</p>

---

## 🖥️ Supported Platforms

| OS | Installer | Service Manager | Auto-Restart |
|---|---|---|---|
| **Linux** (Ubuntu, Debian, Fedora, Arch, etc.) | `install.sh` | user systemd via `service_manager.py` | supervisor keeps PWA online; AI follows the user's on/off choice |
| **macOS** (Intel + Apple Silicon) | `install.sh` | launchctl via `service_manager.py` | supervisor keeps PWA online; AI follows the user's on/off choice |
| **Windows** (10/11, PowerShell) | `install.ps1` | Windows Startup + subprocess supervisor | supervisor keeps PWA online; AI follows the user's on/off choice |
| **Docker** | (planned) | — | — |

- **Full setup guides:** [Linux](docs/INSTALL_LINUX.md) · [macOS](docs/INSTALL_MACOS.md) · [Windows](docs/INSTALL_WINDOWS.md)
- **Guias completas en espanol:** [README.es.md](README.es.md) · [Linux](docs/INSTALL_LINUX.md) · [macOS](docs/INSTALL_MACOS.md) · [Windows](docs/INSTALL_WINDOWS.md)
- **`setup_trinaxai.sh` is Linux-only legacy setup.** New installs should use `install.sh` / `install.ps1`; they configure `service_manager.py` so the PWA can stay available after reboot while the AI services only restart when the user left AI enabled.
- Native install is the recommended path for V1 because Ollama GPU, host file indexing, LAN HTTPS, and phone access are more predictable than in a container.

---

## ✨ Features

- 🧠 **Dual AI Engines** — Ollama (fast, creative) + RAG (accurate, context-aware)
- 📇 **Custom RAG** — Indexes your entire project library. AI answers with real code context
- 🗂️ **Knowledge Collections** — Create separate RAG spaces and query one or many at once
- 📎 **Temporary File Analysis** — Attach files for one chat turn without saving/indexing them; RAG indexing is explicit
- 🧭 **Local Memory** — Explicit "remember that..." facts persist across local devices through shared state
- 🎤 **Voice Mode** — Speech recognition + text-to-speech. Natural conversations
- 📸 **Vision** — Analyze images with qwen2.5-vl
- 🌐 **Multilingual** — Spanish & English, auto-detected
- 🌓 **Dark/Light Mode** — Auto-detected from system preference
- 📱 **PWA** — Install as native app on iOS, Android, desktop
- ⚡ **Auto-Routing** — Smart model selection based on your query
- 🔄 **Incremental Indexing** — AST-aware chunking, only changed files
- 📤 **History UX** — Search chats, edit/resend messages, export conversations to Markdown/PDF
- 📊 **Resource Monitor** — Basic local RAM telemetry in the PWA status panel
- 🛡️ **100% Local** — No data leaves your network
- 🧰 **Release Tooling** — `backup.sh`, `update.sh`, `uninstall.sh`, CI, DCO, and public readiness checks

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│              Your Device                 │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │ PWA (React)│  │ VSCode (Continue)  │   │
│  │ :3334     │  │ continue-config.yaml│   │
│  └─────┬─────┘  └──────────┬──────────┘   │
│        │                   │               │
│  ┌─────┴───────────────────┴──────────┐   │
│  │     RAG API (FastAPI) :3333        │   │
│  │  LlamaIndex • bge-m3 • BM25       │   │
│  └─────┬──────────────────────────────┘   │
│        │                                   │
│  ┌─────┴──────┐                            │
│  │  Ollama    │  qwen2.5 • llama3.2       │
│  │  :11434    │  bge-m3 • moondream       │
│  └────────────┘                            │
└──────────────────────────────────────────┘
```

---

## 🚀 Quick Start

For complete system-specific instructions, use:

| System | Complete guide |
|---|---|
| Linux | [docs/INSTALL_LINUX.md](docs/INSTALL_LINUX.md) |
| macOS | [docs/INSTALL_MACOS.md](docs/INSTALL_MACOS.md) |
| Windows | [docs/INSTALL_WINDOWS.md](docs/INSTALL_WINDOWS.md) |

### Prerequisites
- Python 3.10+, Node.js 18+, 8GB+ RAM (16GB recommended)
- Linux, macOS, or Windows

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB, 32GB+ for Ultra |
| Disk space | 5 GB | 10-25+ GB (models + index) |
| Python | 3.10 | 3.12+ |
| Node.js | 18 | 20+ |
| Ollama | Latest | Latest |
| GPU | Not required | NVIDIA CUDA / Apple Metal (auto-detected) |

> 💡 Check [canirun.ai](https://www.canirun.ai) to see which models your hardware can handle.

### 1. One-command install
```bash
# Linux
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash

# macOS
bash install.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer is automatic by default: it detects your OS/RAM, writes `.env`, installs dependencies where supported, prepares Python + PWA dependencies, pulls recommended Ollama models, enables boot startup, starts TrinaxAI, and configures LAN access for phones/tablets. Use `./install.sh --interactive` or `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Interactive` if you want manual prompts.

### 2. Manual setup
```bash
git clone https://github.com/TrinaxCode/trinaxai.git
cd trinaxai
./install.sh
```

### 3. Pull Models
```bash
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull bge-m3
# Vision model
ollama pull qwen2.5vl:3b
```

### 4. Index Your Projects
```bash
python index.py
```

You can also open the PWA, go to **Settings → Choose folder & index**, pick a folder from the file explorer, assign it to a collection, and TrinaxAI will copy it into `local_sources/collections/` before indexing it. The UI shows upload/index progress, ETA, skipped files, and a cancel button. Browsers do not expose the original absolute folder path for security.

### 5. Start Everything
```bash
./startup_ai.sh
```

### 6. Open the PWA
```
https://localhost:3334
```
From your phone: `https://[YOUR-LAN-IP]:3334`

### Maintenance

```bash
./backup.sh create        # backup .env, storage, and imported sources
./update.sh               # backup, pull latest code, update deps, rebuild PWA
./uninstall.sh            # remove local runtime files after typed confirmation
```

---

## ⚙️ Configuration

Most users should use `install.sh` / `install.ps1`; it writes `.env` automatically. Advanced users can override:

| Setting | Medium | High | Ultra |
|---------|:------:|:----:|:-----:|
| NUM_CTX | 4096 | 8192 | 16384 |
| RERANK_ENABLED | false | false | false |
| EMBED_WORKERS | 2 | 4 | 6 |
| KEEP_ALIVE | 0s | 30m | 60m |
| Deep model | 3B | 7B | 14B |

```bash
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_CORS_ORIGINS=https://localhost:3334,https://YOUR-LAN-IP:3334
TRINAXAI_PROFILE=ultra
TRINAXAI_ALLOW_LAN_SYSTEM=1
TRINAXAI_UPLOAD_MAX_BYTES=536870912
VITE_TRINAXAI_RAG_TARGET=https://localhost:3333
```

💡 Check **[canirun.ai](https://www.canirun.ai)** to see which models your hardware can run.

### Security Notes

- System actions and browser folder indexing allow localhost + private LAN IPs by default so phones work out of the box. Set `TRINAXAI_ALLOW_LAN_SYSTEM=0` to require localhost/token-only behavior.
- If you expose TrinaxAI beyond your trusted LAN, set `TRINAXAI_ADMIN_TOKEN` and put it behind a VPN/reverse proxy with authentication.
- Folder imports are copied into `local_sources/collections/`; original absolute paths are not stored.
- Upload limits are configurable with `TRINAXAI_MAX_FILE_BYTES`, `TRINAXAI_UPLOAD_MAX_FILES`, and `TRINAXAI_UPLOAD_MAX_BYTES`.
- The cross-platform supervisor keeps the PWA online after reboot. If the user stops AI, only the PWA restarts on the next boot; if AI was left enabled, Ollama + RAG restart too.

### Security Model

- **Local-first:** Ollama, RAG, collections, voice, vision, and shared state run on your machine or trusted LAN.
- **Protected actions:** system start/shutdown, browser folder indexing, app-state sync, and collection writes require localhost/trusted-LAN access or an admin token.
- **LAN-protected:** system actions, browser folder indexing, app-state sync, and collection writes accept localhost and trusted private LAN clients by default.
- **Token-protected option:** set `TRINAXAI_ADMIN_TOKEN` and `TRINAXAI_ALLOW_LAN_SYSTEM=0` when exposing TrinaxAI beyond your personal trusted LAN.
- **Recommended safe setup:** keep TrinaxAI on localhost/private WiFi, do not expose ports to the internet, and use a VPN for remote access.

## Knowledge Collections

- Collections live in `storage/collections.json`; indexed chunks carry `collection_id` and `collection_name` metadata.
- RAG chat can use one or several active collections as context. Files can also be uploaded directly from chat into the active collection.
- Chat file attachments are temporary by default. In RAG mode the UI asks whether to index them and which collection to use.
- Long-term memory is explicit: messages like "remember that my main project is X" are stored locally in `tc-user-memory` and injected into future prompts.
- Reset initial configuration clears local browser state and the host shared state (`storage/app_state.json`) when the backend is reachable.

## Comparison

| Project | Focus | TrinaxAI difference |
|---------|-------|---------------------|
| Open WebUI / Ollama WebUI | General Ollama chat UI | TrinaxAI is project/RAG-first, includes local indexing, citations, PWA phone access, and one-command local setup. |
| AnythingLLM | Knowledge-base assistant | TrinaxAI is designed as a developer/local-workstation assistant with code-aware chunking, Continue.dev config, Ollama routing, and no cloud dependency. |
| Continue.dev | IDE assistant | TrinaxAI complements it: use `continue-config.yaml` to connect Continue to the same local RAG and Ollama model fleet. |

> ⚠️ **Important — Ollama LAN exposure:** The setup scripts configure Ollama to listen on `0.0.0.0` (all network interfaces) so you can access TrinaxAI from your phone. This means **any device on your local network can use your AI models without authentication**. Ollama has no built-in auth. To mitigate this risk:
> - Use a firewall to restrict access to port 11434 (Ollama) to trusted devices only.
> - Consider running TrinaxAI behind a VPN like Tailscale or WireGuard for remote access.
> - If you only need local access, set `OLLAMA_HOST=127.0.0.1` in the systemd override or `.env` file.

> ⚠️ **Legacy sudoers caution:** `setup_trinaxai.sh` is Linux-only and can create `/etc/sudoers.d/trinaxai` for older systemd deployments. The default cross-platform installer uses `service_manager.py` instead. If you choose the legacy sudoers setup for production, move allowed scripts to a root-owned directory and update the sudoers rule accordingly.

---

## 📁 Project Structure

| File | Purpose |
|------|---------|
| `rag_api.py` | FastAPI backend — chat, health, system control |
| `index.py` | Project indexer — AST chunking, incremental mode |
| `trinaxai_cli.py` | TrinaxAI CLI local assistant (`ollama` / `rag` modes) |
| `query.py` | Backward-compatible wrapper for TrinaxAI CLI |
| `config.py` | All configuration — models, ctx, workers |
| `startup_ai.sh` | Start all services |
| `shutdown_ai.sh` | Graceful shutdown |
| `backup.sh` | Backup/restore local state |
| `update.sh` | Update code/dependencies and rebuild |
| `uninstall.sh` | Remove local runtime files |
| `service_manager.py` | Cross-platform start/stop/status/watch supervisor |
| `test_system.py` | Automated health check |
| `chat-pwa/` | React PWA frontend |

### What Should Not Be Published

The repo intentionally ignores local/runtime data:

- `.venv/`, `chat-pwa/node_modules/`, `chat-pwa/dist/`
- `storage/`, `storage.bak.nomic/`, `local_sources/`, `projects/`
- `logs/`, `backups/`
- `.env`, local certificates, generated service files

Run `python3 scripts/public_readiness.py` before publishing.

## Docker

Docker can help advanced users run a reproducible RAG API/PWA stack, but it is not the best default for TrinaxAI V1 because Ollama GPU acceleration, host file indexing, LAN HTTPS certificates, and phone access are more predictable with native installs. A future Docker Compose setup is useful for:

- demos and CI smoke tests,
- server/NAS deployments,
- users who already run Ollama outside the container,
- isolated testing without touching the host Python environment.

For V1, native install remains the recommended path.

---

## 📱 PWA Installation

**iOS (Safari):** Open URL → Share → "Add to Home Screen"  
**Android (Chrome):** Open URL → ⋮ → "Install app"  
**Desktop:** Install icon in address bar (Chrome/Edge)

---

## 🔧 Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "No index found" in PWA | Index not built yet | Run `python index.py` |
| Ollama won't start | Port 11434 occupied | Check with `lsof -i :11434` |
| HTTPS certificate warning | Self-signed cert | Accept the warning — local use only |
| CORS error from phone | `TRINAXAI_CORS_ORIGINS` not set | Add `https://YOUR-LAN-IP:3334` |
| "Model not found" | Model not pulled | Run `ollama pull <model>` |
| Out of memory | Too many models loaded | Reduce `OLLAMA_MAX_LOADED_MODELS` |
| "sudo not found" | macOS without sudo, or Windows | Use `python service_manager.py` for process management |
| Frontend not loading | Vite dev server not running | `cd chat-pwa && npm run dev` |
| Index stuck at 0% | Unreadable files in directory | Check permissions; the indexer skips unreadable files |

## 🧪 Testing

```bash
make audit
make build
python test_system.py --verbose
python trinaxai_cli.py --engine rag
```

For release preparation, see [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md).

### ✅ Verify

Before pushing changes or opening a PR, run these three commands. They are the same checks that `make audit` and the CI pipeline execute:

```bash
python3 scripts/public_readiness.py   # required files, hardcoded paths, i18n keys
python3 -m py_compile rag_api.py index.py config.py trinaxai_cli.py service_manager.py test_system.py scripts/public_readiness.py
cd chat-pwa && npx tsc --noEmit && npm run build
```

A clean run prints `Public readiness audit passed.` and exits with code `0`.

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome!

- 🐛 Report bugs · 💡 Suggest features · 📝 Improve docs · 🌍 Translate · 🔧 Submit PRs

---

## Uninstall

To completely remove TrinaxAI from your system:

```bash
./uninstall.sh
# Optional: ./uninstall.sh --remove-models
```

## License

AGPL-3.0-or-later — see [LICENSE](LICENSE). See [TRADEMARK.md](TRADEMARK.md) for project name/logo usage.

---

## ⭐ Support

If TrinaxAI helps you, please **star this repo** ⭐ — it helps others find the project!

[![Star History Chart](https://api.star-history.com/svg?repos=TrinaxCode/TrinaxAI&type=Date)](https://star-history.com/#TrinaxCode/TrinaxAI)

<p align="center">
  <strong>Built by <a href="https://github.com/TrinaxCode">TrinaxCode</a></strong><br>
  <sub>AI should be free, private, and local.</sub>
</p>
