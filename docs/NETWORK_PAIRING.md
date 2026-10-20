<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🔗 Network Pairing
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.3.0"><img src="https://img.shields.io/badge/version-1.3.0-006bbd" alt="Stable release: 1.3.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="NETWORK_PAIRING.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

The PWA gateway is loopback-only by default. Run `trinaxai network refresh` to
enable intentional LAN access (`TRINAXAI_PWA_HOST=0.0.0.0`) and restart the
gateway; FastAPI and Ollama remain on loopback. A device on the same Wi-Fi must
trust the host certificate and either start a chat/web-only new-device session
or use a one-time pairing code before reading private data.

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

1. On the host, open **Settings > Advanced > Paired device**, choose the
   permissions the new device should have, and press **Generate pairing code**.
2. On the phone, choose **I already have TrinaxAI on another device**.
3. Enter the one-time code, name the device, and confirm.
4. Review, change or revoke it from the host settings, or run
   `trinaxai pair list`, `trinaxai pair set ID --scopes ...` and
   `trinaxai pair revoke ID`.

## Permissions Per Device

Each paired device holds its own permission set, chosen on the host when the
code is generated and editable later (**Permissions** next to the device, or
`trinaxai pair set`). The host asks for confirmation before it grants any
permission that lets a device change the computer.

| Permission | Allows the device to |
|---|---|
| `chat` | Talk to the local models. |
| `read_private` | Use indexed knowledge, memory, synced chats and statistics. |
| `web` | Search the web through the host. |
| `index` | Index and watch folders, create/clear/delete collections and sources. A watched folder must be inside the host's configured indexing roots. |
| `agent` | Use TrinaxAI Agent inside the allowed workspace roots, never in a folder that holds TrinaxAI's own files (install, `.env`, storage, credentials). Every dangerous action still needs confirmation from that device. |
| `modify` | Edit memory and web-search settings, and delete attachments. |

The default for a new code is `chat`, `read_private` and `web`. `index`,
`agent` and `modify` are off until you turn them on for a specific device; a
device paired before this feature existed keeps its previous behaviour until you
grant them explicitly. Changes apply on the device's next request.

Power and restart, model management, wiping data, opening host files, pairing
or revoking other devices, and the Agent's auto-approve (YOLO) mode can never
be granted. They only work from `https://localhost:3334`, and neither a device
nor an admin token sent over the network can change a device's permissions.

Choosing **Set up as a new device** creates a revocable `chat`/`web` cookie
without synchronized history or private reads. Pair it later from the host if
the device needs RAG, memory, or synchronized chats.

If installing a private CA on mobile is not acceptable, use a trusted VPN or a
reverse proxy with a public certificate. Do not disable TLS verification and do
not expose ports `3333` or `11434`.

For other service, model, indexing, or recovery failures, continue with the
[troubleshooting and recovery guide](TROUBLESHOOTING.md).
