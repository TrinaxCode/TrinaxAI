<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🔗 Network Pairing
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="NETWORK_PAIRING.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

The PWA gateway is loopback-only by default. To enable intentional LAN access,
set `TRINAXAI_PWA_HOST=0.0.0.0` in `.env` and restart TrinaxAI; FastAPI and
Ollama remain on loopback. A device on the same Wi-Fi must trust the host
certificate and use a one-time pairing code before it can use chat or read
private data.

## Prepare The Host

Run this from the installed TrinaxAI directory:

```bash
trinaxai network refresh
trinaxai network
```

The command prints the current PWA URL and the public certificate that a phone
or tablet must trust. If `mkcert` is installed, use its `rootCA.pem` path. With
the OpenSSL fallback, use `chat-pwa/certs/trinaxai-local.crt`.

Never copy or expose either private key:

- `rootCA-key.pem` from the mkcert CA directory.
- `chat-pwa/certs/localhost-key.pem`.

Transfer only the public CA/certificate to devices you control, preferably with
a cable, AirDrop, or an encrypted local transfer. Do not publish it on the
Internet or attach it to a support issue.

## Trust On A Phone

The exact labels vary by OS version. The certificate must be installed as a
user-trusted CA/profile, not merely downloaded.

### Android

1. Transfer the public certificate to the phone.
2. Open **Settings > Security** (or **Security & privacy**) and choose **Install from device storage** or **Install a certificate**.
3. Select **CA certificate**, choose the transferred file, and confirm the lock-screen prompt.
4. Open the printed `https://HOST-LAN-IP:3334` address in Chrome.

### iPhone and iPad

1. Transfer the public certificate as a profile or certificate file.
2. Open **Settings > Profile Downloaded** and install it, or open the file and follow the profile prompt.
3. Go to **Settings > General > About > Certificate Trust Settings** and enable full trust for the installed root certificate.
4. Open the printed `https://HOST-LAN-IP:3334` address in Safari.

If the device still shows a certificate error, remove the old profile and
repeat the process after `trinaxai network refresh`. A certificate includes the
current LAN address; changing Wi-Fi can require a new certificate.

## Pair The Browser

1. On the host, open **Settings > Paired device > Generate pairing code**.
2. On the phone, choose **I already have TrinaxAI on another device**.
3. Enter the one-time code, name the device, and confirm.
4. Review or revoke it from the host settings, or run `trinaxai pair list` and
   `trinaxai pair revoke ID`.

Pairing grants only `chat`, `read_private`, and optionally `web`. Indexing,
configuration writes, the Agent, model management, lifecycle controls, factory
reset, and device administration remain host-only at `https://localhost:3334`.

If installing a private CA on mobile is not acceptable, use a trusted VPN or a
reverse proxy with a public certificate. Do not disable TLS verification and do
not expose ports `3333` or `11434`.

For other service, model, indexing, or recovery failures, continue with the
[troubleshooting and recovery guide](TROUBLESHOOTING.md).
