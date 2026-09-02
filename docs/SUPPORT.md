<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 💬 Support
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="SUPPORT.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

TrinaxAI is a local-first open-source project. Community support happens in GitHub issues and discussions.

Start with the [troubleshooting and recovery guide](TROUBLESHOOTING.md). If the
PWA offers **Open indexing**, **Retry**, **Start AI**, or **Open settings**, use
that action before collecting logs.

## Before Opening an Issue

Run these from the repository root:

```bash
python3 test_system.py --verbose
python3 scripts/public_readiness.py
cd chat-pwa && npm run build
```

If services are not running, use `trinaxai doctor --strict --json` instead of
the system test. Include the failing command, a short description of the
expected behavior, and the relevant redacted output when you report a bug.
For API failures, include the request ID if one was returned. See the
[documentation index](README.md), [troubleshooting guide](TROUBLESHOOTING.md),
and [security policy](SECURITY.md) first.

## Useful Details

Please include:

- OS and version: Linux distro, macOS version, or Windows version.
- Python version.
- Node.js version.
- Ollama version.
- RAM and GPU, if relevant.
- TrinaxAI profile: `8gb`, `16gb`, `32gb`, or `64gb`.
- Whether you use localhost only or LAN/phone access.

## Security

Do not publish tokens, private documents, screenshots with secrets, or personal
files. For security reports, use [SECURITY.md](SECURITY.md) rather than a
public issue.
