# Support

[Versión en español](SUPPORT.es.md)

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
