# 🚀 TrinaxAI — 100% Local AI Assistant

<p align="center">
  <img src="chat-pwa/public/logo-of-app.webp" alt="TrinaxAI Logo" width="180" />
</p>

<p align="center">
  <strong>Open-source, local-first AI assistant with RAG, vision, voice, CLI, and PWA.</strong><br>
  Runs entirely on your machine. No cloud. No subscriptions. No limits.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg" alt="AGPL-3.0-or-later"></a>
  <a href="#-quick-start"><img src="https://img.shields.io/badge/powered_by-Ollama-black.svg" alt="Ollama"></a>
  <a href="#-supported-platforms"><img src="https://img.shields.io/badge/platform-Linux|macOS|Windows-lightgrey.svg" alt="Platforms"></a>
  <a href="#-pwa-installation"><img src="https://img.shields.io/badge/PWA-ready-brightgreen.svg" alt="PWA"></a>
</p>

> **⭐ If TrinaxAI helps you, please star the repo — it helps others find it!**

---

## What is TrinaxAI?

TrinaxAI is a **local AI assistant** that combines a ChatGPT-like chat interface (PWA) with a developer CLI, RAG-powered code search, voice mode, and vision. Everything runs on your machine — your data never leaves your network.

- **Chat** with Ollama models via a beautiful PWA or terminal CLI
- **Index your projects** for semantic code search with citations
- **Voice conversations** with speech-to-text and text-to-speech
- **Vision** — analyze images and screenshots locally
- **Cross-platform** — Linux, macOS, Windows. One-command install.

---

## ✨ Features

- 🧠 **Dual AI Engines** — Ollama (fast, creative) + RAG (accurate, context-aware)
- 📇 **Custom RAG** — Indexes your project library. AI answers with real code context
- 🗂️ **Knowledge Collections** — Create separate RAG spaces and query one or many
- 🧭 **Local Memory** — "remember that..." facts persist across devices via shared state
- 🎤 **Voice Mode** — Speech recognition + text-to-speech. Natural conversations
- 📸 **Vision** — Analyze images with qwen2.5-vl
- 💻 **Developer CLI** — `trinaxai ask`, `trinaxai chat`, `trinaxai index`, `trinaxai doctor`
- 🌐 **Bilingual** — Spanish & English, auto-detected
- 🌓 **Dark/Light Mode** — Auto-detected from system preference
- 📱 **PWA** — Install as native app on iOS, Android, desktop
- 📤 **History** — Search chats, edit/resend, export to Markdown/PDF
- 🛡️ **100% Local** — No data leaves your network

---

## 📸 Screenshots

<!-- TODO: Add screenshots of the PWA chat, CLI demo, and mobile view -->
<p align="center">
  <em>Screenshots coming soon. For now: run <code>./install.sh && trinaxai chat</code> to see it live.</em>
</p>

---

## 🖥️ Supported Platforms

| OS | Installer | Service Manager |
|---|---|---|
| **Linux** (Ubuntu, Debian, Fedora, Arch) | `install.sh` | user systemd |
| **macOS** (Intel + Apple Silicon) | `install.sh` | launchctl |
| **Windows** (10/11, PowerShell) | `install.ps1` | subprocess supervisor |

Full guides: [Linux](docs/INSTALL_LINUX.md) · [macOS](docs/INSTALL_MACOS.md) · [Windows](docs/INSTALL_WINDOWS.md)
<br>Guías en español: [Linux](docs/INSTALL_LINUX.es.md) · [macOS](docs/INSTALL_MACOS.es.md) · [Windows](docs/INSTALL_WINDOWS.es.md)

---

## 🚀 Quick Start

### One-command install (Linux / macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash
```

> **Security note:** Review the script first with `curl -fsSL URL | less` or clone the repo and run locally.

### Windows

```powershell
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The Windows installer configures required dependencies automatically; Ollama is installed through `winget` or the official silent installer fallback.

### Manual install

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
./install.sh

# Or for more control:
./install.sh --non-interactive # Automatic install for CI/scripts
./install.sh --no-models       # Skip model downloads
./install.sh --profile ultra   # Force profile (8gb, 16gb, max, ultra)
```

### Options

| Flag | Description |
|------|-------------|
| `--interactive` | Guided install; asks optional choices (default) |
| `--non-interactive` | Automatic install for CI/scripts |
| `--no-models` | Skip downloading Ollama models |
| `--no-vision` | Skip vision model download |
| `--no-autostart` | Do not enable boot auto-start |
| `--no-start` | Do not start TrinaxAI after install |
| `--profile 8gb\|16gb\|max\|ultra` | Override auto-detected hardware profile |
| `--lan-system` | Enable LAN system-control endpoints (generate admin token) |

By default, **LAN system control is disabled** — no device on your network can call sensitive endpoints. Enable it explicitly with `--lan-system` or set `TRINAXAI_ALLOW_LAN_SYSTEM=1` and `TRINAXAI_ADMIN_TOKEN` in `.env`.

### Update and uninstall

```bash
./update.sh      # Guided update; asks backup, models, autostart, restart, audit
./uninstall.sh   # Guided uninstall; asks each removable item
```

On Windows, use PowerShell-native scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\update.ps1
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

Required dependencies still install/update automatically. Optional choices such as model downloads, boot auto-start, data removal, and restarts are prompted by default.

### Open the PWA

```
https://localhost:3334
```

From your phone (same WiFi): `https://[YOUR-LAN-IP]:3334`

---

## 💻 CLI

TrinaxAI includes a developer CLI for terminal-native workflows.

```bash
# Install the CLI (from the repo root)
pip install -e .

# Quick commands
trinaxai                  # Interactive REPL
trinaxai ask "..."        # One-shot question
trinaxai chat             # Interactive chat session
trinaxai index .          # Index the current directory
trinaxai browse           # Browse indexed collections
trinaxai doctor           # System health check
trinaxai start            # Start all services
trinaxai stop             # Stop all services
trinaxai watch            # Start file watcher for auto-reindex
trinaxai research "..."   # Multi-pass deep research on a question
trinaxai export           # Export a conversation
trinaxai memory           # Manage persistent memory entries
trinaxai collections      # List or manage RAG collections
trinaxai --engine rag     # Force RAG engine
trinaxai --engine ollama  # Force Ollama engine
```

The CLI auto-detects whether to use Ollama or RAG based on your query. It works with the same backend as the PWA — no separate configuration needed.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│              Your Device                 │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │ PWA (React)│  │ CLI (trinaxai)     │   │
│  │ :3334     │  │ pip install -e .    │   │
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

## 🔒 Security Model

TrinaxAI is **local-first by design**. Here's what that means in practice:

| Layer | Default | How to harden |
|-------|---------|---------------|
| **RAG API** | Binds to `0.0.0.0:3333` for LAN PWA/phone access | Set `TRINAXAI_HOST=127.0.0.1` for localhost-only |
| **System endpoints** | Require localhost or admin token | Set `TRINAXAI_ADMIN_TOKEN` and `TRINAXAI_ALLOW_LAN_SYSTEM=1` if exposing to LAN |
| **Ollama** | Binds to `127.0.0.1` by default | Firewall port 11434 if you expose it |
| **PWA** | Served over HTTPS with a generated local certificate | Trust the generated cert on each device, or use nginx/Caddy with Let's Encrypt for public-domain access |
| **File uploads** | Sanitized, sandboxed to `local_sources/collections/` | Adjust `TRINAXAI_UPLOAD_MAX_BYTES` |
| **CORS** | localhost + your LAN IP by default | Customize via `TRINAXAI_CORS_ORIGINS` |

**LAN system control is disabled by default.** Enable it explicitly during install (`--lan-system`) or set `TRINAXAI_ALLOW_LAN_SYSTEM=1` in `.env`. When enabled, a strong `TRINAXAI_ADMIN_TOKEN` is auto-generated.

Performance knobs for local hardware:

```bash
TRINAXAI_INDEX_BATCH_SIZE=100
TRINAXAI_RATE_LIMIT_PER_MINUTE=30
TRINAXAI_EMBED_WORKERS=2
TRINAXAI_EMBED_BATCH=8
TRINAXAI_EMBED_KEEP_ALIVE=15m
```

### Recommendations for LAN / remote access

- Use a **firewall** to restrict ports 3333, 3334, 11434 to trusted devices
- Use a **VPN** (Tailscale, WireGuard) for remote access — don't expose ports to the internet
- Set `TRINAXAI_ADMIN_TOKEN` to a strong random value
- Keep the PWA on **localhost or private WiFi** — not on public networks
- Audit your install with `trinaxai doctor`

See [SECURITY.md](SECURITY.md) for the full threat model and reporting process.

---

## 🧪 Development

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python rag_api.py

# PWA frontend
cd chat-pwa
npm install
npm run dev

# CLI (editable install)
pip install -e .
trinaxai doctor
```

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for full instructions.

---

## ✅ Testing & Audit

```bash
# Pre-release audit (checks i18n, hardcodes, required files, .gitignore)
python3 scripts/public_readiness.py

# Python checks
python3 -m py_compile rag_api.py config.py index.py trinaxai_cli.py
ruff check .

# PWA checks
cd chat-pwa
npx tsc --noEmit
npm run build
npm audit --audit-level=high

# System smoke test (requires running services)
trinaxai doctor
python3 test_system.py --verbose
```

---

## 📁 Project Structure

| Path | Purpose |
|------|---------|
| `rag_api.py` | FastAPI backend — chat, health, system control |
| `index.py` | Project indexer — AST chunking, incremental mode |
| `config.py` | Central configuration — models, profiles, chunking |
| `trinaxai_cli/` | Modular CLI package (`trinaxai ask`, `trinaxai chat`, …) |
| `trinaxai_cli.py` | Legacy standalone CLI (deprecated, kept for compat) |
| `query.py` | Backward-compatible wrapper for `trinaxai_cli.py` |
| `service_manager.py` | Cross-platform start/stop/status/watch supervisor |
| `startup_ai.sh` | Start all services |
| `shutdown_ai.sh` | Graceful shutdown |
| `backup.sh` / `update.sh` / `uninstall.sh` | Linux/macOS maintenance scripts |
| `update.ps1` / `uninstall.ps1` | Windows maintenance scripts |
| `install.sh` / `install.ps1` | One-command installers |
| `chat-pwa/` | React PWA frontend |
| `scripts/public_readiness.py` | Pre-release audit tool |
| `test_system.py` | System health test |

---

## 📚 FAQ

**Q: Does TrinaxAI send my data to the cloud?**  
A: No. Everything runs locally. The only network calls are to Ollama (localhost:11434), the RAG API (localhost:3333), and Google Fonts (in the PWA). No chat data, code, or documents leave your machine.

**Q: What models are recommended?**  
A: The installer auto-detects RAM. 8 GB uses `llama3.2:1b`, `qwen2.5-coder:1.5b`, and `nomic-embed-text`. 16 GB uses `llama3.2:3b`, `qwen2.5-coder:3b`, and `bge-m3`. Visit [canirun.ai](https://www.canirun.ai) to check what your hardware supports.

**Q: Can I use it from my phone?**  
A: Yes. Open `https://[YOUR-LAN-IP]:3334` from any device on the same WiFi. The PWA is installable on iOS and Android.

**Q: How secure is LAN access?**  
A: System endpoints are protected — disabled by default. Enable with `--lan-system` during install. See [SECURITY.md](SECURITY.md).

**Q: Does it work without GPU?**  
A: Yes. Ollama runs on CPU. Performance depends on RAM and model size. The `8gb` profile uses small models optimized for CPU inference.

**Q: Can I index my entire Documents folder?**  
A: Yes. The indexer supports 15+ languages with AST-aware chunking. It's incremental — re-indexing only touches changed files.

**Q: What license?**  
A: AGPL-3.0-or-later. Free for personal and commercial use. See [LICENSE](LICENSE) and [TRADEMARK.md](TRADEMARK.md).

---

## 🗺️ Roadmap

See [ROADMAP.md](ROADMAP.md) for the full plan. Highlights:

- ✅ **Done** — Chat, RAG, voice, vision, PWA, CLI, installers, watcher, research mode
- 🔜 **Near-term** — Visual project browser, conversation summarization, prompt templates
- 📅 **Planned** — Docker/Compose, MCP server, Obsidian integration, benchmark suite

---

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and setup instructions.

- 🐛 Report bugs · 💡 Suggest features · 📝 Improve docs · 🌍 Translate · 🔧 Submit PRs

---

## 📄 License

AGPL-3.0-or-later — see [LICENSE](LICENSE). See [TRADEMARK.md](TRADEMARK.md) for name/logo usage.

---

<p align="center">
  <strong>Built by <a href="https://github.com/TrinaxCode">TrinaxCode</a></strong><br>
  <sub>AI should be free, private, and local.</sub>
</p>
