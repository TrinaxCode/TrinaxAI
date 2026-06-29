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
- Affected components (RAG API, PWA frontend, shell scripts, etc.)
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
| **RAG API** (`rag_api.py`) | Medium | Binds to `0.0.0.0` by default when configured for LAN access. System endpoints require admin token. |
| **PWA Frontend** (`chat-pwa/`) | Low | Static React app. CSP headers are recommended for production deployments. |
| **Shell Scripts** | Low | `sudo` usage is documented. Scripts should be audited before production use. |
| **Ollama** | Medium | Ollama has no built-in authentication. When exposed on the LAN (`OLLAMA_HOST=0.0.0.0`), anyone on your network can use your models. |
| **Folder Uploads** | Low | Uploaded files are sanitized and sandboxed to `local_sources/collections/`. |

## Out of Scope

- Vulnerabilities in third-party dependencies (Ollama, LlamaIndex, Node.js modules) — report those upstream
- Social engineering attacks against users
- Physical access to the host machine
- Denial of service via resource exhaustion (inherent to running LLMs locally)

## Security Best Practices for Deployers

1. **Set `TRINAXAI_ADMIN_TOKEN`** if you expose TrinaxAI outside your personal trusted LAN.
2. **Restrict Ollama** to `127.0.0.1` if you only need local access, or use a firewall to limit access to port 11434.
3. **Audit the sudoers file** (`/etc/sudoers.d/trinaxai`) — the scripts it allows are user-writable by default. For production, move them to a root-owned directory.
4. **Run behind a reverse proxy** (nginx, Caddy) with TLS for production LAN deployments.
5. **Keep dependencies updated** — run `pip-audit` and `npm audit` regularly.
6. **Keep TrinaxAI on localhost or a trusted private LAN** unless you place it behind a VPN or authenticated reverse proxy.

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities. Contributors will be listed here (with permission).
