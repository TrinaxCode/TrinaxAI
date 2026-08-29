<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · ✍️ Release Signing
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Latest release: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><strong>English</strong> · <a href="RELEASE_SIGNING.es.md">Español</a></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Website</a> · <a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="CHANGELOG.md">Changelog</a></sub></p>

The release workflow publishes source archives, shell and PowerShell installers,
and a Python wheel. Stable publication is fail-closed: every downloadable asset
must have a verified detached signature before upload.

## GitHub Actions secrets

Configure these repository or organization secrets before creating a stable tag:

| Secret | Used for |
| --- | --- |
| `RELEASE_SIGNING_KEY_BASE64` | Base64-encoded armored GPG private key for release assets |
| `RELEASE_SIGNING_KEY_PASSPHRASE` | Passphrase for the GPG release key |
| `RELEASE_SIGNING_KEY_FINGERPRINT` | Full, space-free fingerprint of the public release key; the workflow fails if the imported key differs |

The release job signs source archives, installers, the wheel, and `SHA256SUMS`
with GPG and verifies each signature before publication. Container images are
signed and verified with keyless Sigstore signing.

If any required signing secret is absent or invalid, the workflow fails before
publishing. Never print secrets or store certificates or private keys in the
repository.

After publishing, the workflow verifies every expected download URL and required
`.asc` asset; all source and installer assets are included in `SHA256SUMS`.

## Verify a download

Every stable release also publishes `TrinaxAI-release-signing-key.asc` and
`TrinaxAI-release-signing-key.fingerprint`. Compare that fingerprint with the
trusted value in the release announcement before importing the key. Do not run
an installer or script from a release that does not publish both files.

```bash
version=v1.2.0
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/${version}"
curl -fLO "${base}/TrinaxAI-release-signing-key.asc"
curl -fLO "${base}/TrinaxAI-release-signing-key.fingerprint"
gpg --show-keys --fingerprint TrinaxAI-release-signing-key.asc
gpg --import TrinaxAI-release-signing-key.asc
curl -fLO "${base}/SHA256SUMS"
curl -fLO "${base}/SHA256SUMS.asc"
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum --check SHA256SUMS
```

Verify the detached `.asc` for the exact installer or archive before opening or
executing it. The release workflow publishes the public key and fingerprint;
maintainers must publish the trusted fingerprint through an independent release
channel before calling a release signed.
