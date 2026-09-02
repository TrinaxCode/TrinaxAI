<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · ✍️ Release Signing
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
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

The workflow first stages a draft and rejects missing or stale remote assets by
comparing the exact asset set and every detached signature. It publishes only
after that check, then repeats the exact-set and signature checks on the public
release. All source and installer assets are included in `SHA256SUMS`.

The readiness checker intentionally uses dependency-free, line-anchored checks
for critical commands instead of a full YAML parser; it cannot replace review
of YAML structure outside those commands.

## Trust anchor

The repository pins the release public key in
[`RELEASE_SIGNING_KEY.asc`](RELEASE_SIGNING_KEY.asc) and its fingerprint in
[`RELEASE_SIGNING_KEY.fingerprint`](RELEASE_SIGNING_KEY.fingerprint):

```text
CF927A2365A5C46438A790FCCCE8FD65623D065C
```

The GitHub Actions secret `RELEASE_SIGNING_KEY_FINGERPRINT` must match this
value. Compare the key fingerprint from the repository checkout before trusting
any release asset; never replace this anchor with a key downloaded from the
same release.

## Verify a download

The release workflow requires detached signatures. For end users, the
`SHA256SUMS` check in the installation guides is mandatory before execution.
That check protects integrity but does not authenticate the release.
Detached GPG verification is an optional additional check when the signing key
fingerprint was obtained and trusted independently. Without that independent
anchor, GPG cannot establish authenticity; never treat a key or fingerprint
downloaded from the same release as a trust anchor.

```bash
version=v1.2.1
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/${version}"
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/docs/RELEASE_SIGNING_KEY.asc -o TrinaxAI-release-signing-key.asc
trusted_fingerprint="CF927A2365A5C46438A790FCCCE8FD65623D065C"
actual_fingerprint="$(gpg --show-keys --with-colons TrinaxAI-release-signing-key.asc | awk -F: '$1 == "fpr" { print $10; exit }')"
test "${actual_fingerprint^^}" = "$trusted_fingerprint"
gpg --import TrinaxAI-release-signing-key.asc
curl -fLO "${base}/SHA256SUMS"
curl -fLO "${base}/SHA256SUMS.asc"
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum --check SHA256SUMS
```

After downloading the exact installer or archive and its `.asc` file, verify
that detached signature with the imported key before opening or executing it.
For example:

```bash
asset="TrinaxAI-${version#v}-installer.sh"
curl -fLO "${base}/${asset}" "${base}/${asset}.asc"
gpg --verify "${asset}.asc" "$asset"
```

The source updater validates HTTPS release metadata and the SHA-256 manifest,
and requires an operator-provided SHA-256 for every custom archive URL,
including `file://`. It does not execute a downloaded update until the release
archive checksum matches the signed manifest.
