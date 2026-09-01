<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🛡️ Security
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="SECURITY.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| Latest  | :white_check_mark: |
| < Latest| :x:                |

Only the latest commit on `main` receives security patches.

## Reporting a Vulnerability

**Do not open a public issue.** Instead, email:

> **trinaxcode@gmail.com**

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

TrinaxAI is **local-first**: inference and persisted application data use the
configured host by default. Installation/model downloads, explicit web research,
external assets, and operator-configured remote endpoints are network activity.
The primary attack surface is:

| Component | Risk | Notes |
|-----------|------|-------|
| **RAG API** (`app/`) | Medium | Managed launch is loopback-only. The local gateway signs the original peer with a short-lived HMAC assertion; ordinary forwarding headers are ignored. Private state, sources, memory, attachments, agent and administration require authorization. |
| **PWA gateway** (`chat-pwa/vite.config.ts`) | Medium | LAN-facing HTTPS boundary. It validates paired-device/admin credentials, strips client-supplied identity headers, signs the peer for FastAPI, applies security headers, and exposes only an allowlisted Ollama facade. Vite remains a project gateway, not a generic reverse proxy. |
| **Agent** (`trinaxai_cli/agent/`) | High | File tools resolve symlinks inside registered workspace roots. Linux shell commands use networkless bubblewrap; command execution fails closed when supported isolation is unavailable. Dangerous tools require approval; HTTP auto-approval is disabled and cannot be enabled remotely. |
| **CLI** (`trinaxai_cli/`) | Limited | Local terminal tool with verified TLS by default. `--insecure`, `--yolo`, and unsandboxed command execution are explicit high-risk opt-ins. |
| **Lifecycle/backups** | Medium | Privileged lifecycle calls use an exact, root-owned wrapper rather than repository-editable scripts. Backups use private modes, validate archive entry types/paths, restore through staging, and roll back failed replacement. Backups contain sensitive data and should still be encrypted at rest. |
| **Ollama** | High if exposed | Ollama has no built-in authentication. Managed launch binds it to `127.0.0.1`; never expose port 11434 or a generic Ollama proxy. |
| **Uploads/web fetch** | Medium | Imports use managed roots, sanitized paths, quotas, and protected endpoints. Web page reads are bounded, resolve/connect to validated public IPs, reject private/link-local destinations and revalidate redirects. Parsers still process untrusted formats, so keep limits conservative. |

## Out of Scope

- Vulnerabilities in third-party dependencies (Ollama, LlamaIndex, Node.js modules) — report those upstream
- Social engineering attacks against users
- Physical access to the host machine
- Denial of service via resource exhaustion (inherent to running LLMs locally)

## Threat Model

TrinaxAI's threat model assumes:

1. **Trusted local machine** — the host is not compromised
2. **Untrusted LAN by default** — possession of the same WiFi is not identity; protected remote requests require a scoped paired-device token or the administrator credential
3. **Untrusted internet** — TrinaxAI should never be exposed directly to the internet without a VPN or authenticated reverse proxy

### Attack vectors considered

- **LAN attacker** (same WiFi, no credential): The gateway preserves the signed
  original IP, so a proxied client cannot inherit loopback privilege. App state,
  attachments, sources, memory, index/system routes and the agent return `403`.
  Only explicitly public health/resource routes remain available without a
  credential.
- **Stolen device token:** A device token is a bearer capability limited to its
  recorded scopes. A new PWA claim keeps it only in an `HttpOnly; SameSite=Strict`
  cookie scoped to `/api/rag`; the browser never receives a new bearer in JSON or
  persists it in browser storage. FastAPI stores only a keyed hash, and
  host/admin operators can revoke it immediately. Legacy CLI bearers remain
  header-only and are never copied into a response cookie. Pair only devices you control and revoke a lost device
  with `trinaxai pair revoke`; the CLI remains header-based.
- **Forged proxy identity:** Client-supplied TrinaxAI/forwarding headers are stripped
  by the gateway. FastAPI accepts a fresh, single-use HMAC signature only from
  loopback or an explicitly configured private runtime peer; network membership
  alone grants no privilege without the secret in `storage/.proxy_secret`.
- **Prompt injection in indexed/web content:** Retrieved material is delimited and
  labelled untrusted. It cannot authorize a tool. Keep dangerous-action approval on;
  HTTP yolo is off and restricted to real loopback even when explicitly enabled.
- **Remote attacker** (internet): Should be impossible if ports are not forwarded. Use a VPN for remote access.
- **Malicious tarball** (`backup.sh restore`): Only the expected `.env`, `storage/`
  and `local_sources/` trees are accepted; absolute/traversal paths, links and
  device entries are rejected before staged replacement.

## Security Best Practices for Deployers

1. **Keep FastAPI and Ollama on loopback.** Leave `TRINAXAI_UNSAFE_BIND_BACKEND=0`; publish only the authenticated PWA gateway.
2. **Pair devices with least privilege.** `trinaxai pair start` grants
   `chat,read_private` by default and may add only `web`. Review
   `trinaxai pair list` and revoke devices that are lost or no longer used.
3. **Administer only from `https://localhost:3334`.** Indexing, Agent, model and
   device management, lifecycle actions, and factory reset require verified
   loopback even when an admin credential or retired device scope is supplied.
4. **Keep credential secrets private.** Never share `storage/.proxy_secret` or
   `storage/.device_secret`; preserve mode `0600` on those files and on
   `storage/device_pairing.json`.
5. **Use a firewall** to restrict the PWA port to intended devices and block direct ports 3333/11434.
6. **Use a VPN** (Tailscale, WireGuard) for remote access — never forward ports directly to the internet.
7. **Keep dependencies reproducible and audited** — install `requirements.lock`, run `pip-audit --require-hashes -r requirements.lock` and `npm audit`, and do not downgrade the NLTK `>=3.10.0` floor.
8. **Keep shell isolation fail-closed.** Install bubblewrap on Linux; do not enable `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS` on a remotely reachable service.
9. **Encrypt backups** when they leave the host; the archive includes `.env`, chats, attachments, sources and indexes even though its filesystem mode is private.
10. **Audit your install** with `trinaxai doctor --strict --json` and `python3 scripts/public_readiness.py`.

## Repository Security

- CI runs tests/build/typecheck/lint, hashed-lock `pip-audit`, Bandit, `npm audit`,
  gitleaks, CodeQL and public-readiness checks. It produces a CycloneDX Python SBOM.
- Dependabot monitors Python and npm dependencies weekly
- No secrets, tokens, or credentials are committed (enforced by `.gitignore`)
- Tagged releases build a deterministic archive, SHA-256 sums and GitHub/Sigstore
  provenance. The scheduled updater only checks availability; installation changes
  remain a reviewed manual operation.

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities. Contributors will be listed here (with permission).
