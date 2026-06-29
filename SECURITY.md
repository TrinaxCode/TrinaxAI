# Security Policy — TrinaxAI

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| Latest  | :white_check_mark: |
| < Latest| :x:                |

Only the latest commit on `main` receives security patches.

## Reporting a Vulnerability

**Do not open a public issue.** Instead, email:

> **security@trinaxcode.com**

We aim to respond within **72 hours** and publish a fix within **7 days** of confirmation.

### What to include

- A clear description of the vulnerability
- Steps to reproduce (proof-of-concept code helps)
- Affected components (RAG API, PWA frontend, shell scripts, CLI, installer)
- Whether you believe it's exploitable remotely or only locally
- Any suggested mitigations

### Process

1. You report privately via email.
2. We acknowledge within 72 hours and begin triage.
3. We develop and test a fix.
4. We publish a GitHub Security Advisory (GHSA) and patch release.
5. You receive credit in the advisory (unless you prefer anonymity).

## Scope

TrinaxAI is a **local-first** application — it runs entirely on your machine. The primary attack surface is:

| Component | Risk | Notes |
|-----------|------|-------|
| **RAG API** (`rag_api.py`) | Medium | Binds to `0.0.0.0` by default when configured for LAN access. System endpoints are protected — disabled by default, require admin token or localhost when enabled. |
| **PWA Frontend** (`chat-pwa/`) | Low | Static React app. Served over self-signed HTTPS. CSP headers recommended for production. |
| **CLI** (`trinaxai_cli/`) | Low | Local terminal tool. No network listeners. |
| **Shell Scripts** (`install.sh`, `backup.sh`, `uninstall.sh`) | Low | `sudo` usage is confined to service management. Backup extraction validates tarball contents before unpacking. Uninstall requires typed confirmation before destructive actions. |
| **Ollama** | Medium | Ollama has no built-in authentication. The installer binds it to `127.0.0.1` by default. If exposed on the LAN (`OLLAMA_HOST=0.0.0.0`), anyone on your network can use your models. |
| **Folder Uploads** | Low | Uploaded files are sanitized (`_safe_rel_path`, `_collection_slug`) and sandboxed to `local_sources/collections/`. Path traversal is blocked. |

## Out of Scope

- Vulnerabilities in third-party dependencies (Ollama, LlamaIndex, Node.js modules) — report those upstream
- Social engineering attacks against users
- Physical access to the host machine
- Denial of service via resource exhaustion (inherent to running LLMs locally)

## Threat Model

TrinaxAI's threat model assumes:

1. **Trusted local machine** — the host is not compromised
2. **Trusted LAN (if enabled)** — devices on the same WiFi are trusted when `TRINAXAI_ALLOW_LAN_SYSTEM=1`
3. **Untrusted internet** — TrinaxAI should never be exposed directly to the internet without a VPN or authenticated reverse proxy

### Attack vectors considered

- **LAN attacker** (same WiFi, no auth): By default, system endpoints are disabled. An attacker can only access read-only endpoints (`/health`, `/resources`, `/app-state`, `/collections`). Chat is rate-limited.
- **LAN attacker + misconfiguration** (`ALLOW_LAN_SYSTEM=1`, no token): Full system control (shutdown, startup, indexing, file uploads). **This is why it's disabled by default.**
- **Remote attacker** (internet): Should be impossible if ports are not forwarded. Use a VPN for remote access.
- **Malicious tarball** (`backup.sh restore`): Tarball contents are validated before extraction — absolute paths and `..` entries are rejected.

## Security Best Practices for Deployers

1. **Keep LAN system control disabled** unless you understand the risks and run on a trusted network.
2. **Set `TRINAXAI_ADMIN_TOKEN`** to a strong random value if you enable LAN system control. The installer generates one automatically with `--lan-system`.
3. **Bind Ollama to `127.0.0.1`** if you only need local access. The installer does this by default.
4. **Use a firewall** to restrict ports 3333, 3334, 11434 to trusted devices only.
5. **Use a VPN** (Tailscale, WireGuard) for remote access — never forward ports directly to the internet.
6. **Keep dependencies updated** — run `pip install --upgrade -r requirements.txt` and `npm audit` regularly.
7. **Audit your install** with `trinaxai doctor` and `python3 scripts/public_readiness.py`.

## Repository Security

- CI runs `ruff check`, `py_compile`, `npx tsc --noEmit`, `npm audit`, and `scripts/public_readiness.py`
- Dependabot monitors Python and npm dependencies weekly
- No secrets, tokens, or credentials are committed (enforced by `.gitignore`)

Recommended additions for production repos:
- `gitleaks` for secret scanning
- `semgrep` for SAST
- `CodeQL` for deep code analysis
- `trivy` for vulnerability scanning

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities. Contributors will be listed here (with permission).
