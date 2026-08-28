# Release Signing

[Versión en español](RELEASE_SIGNING.es.md)

The release workflow builds the Linux, Windows, and macOS Managers on native
runners before publishing the release. Stable publication is fail-closed: every
downloadable asset must have a verified detached signature before upload.

## GitHub Actions secrets

Configure all of these repository or organization secrets before creating a
stable tag:

| Secret | Used for |
| --- | --- |
| `WINDOWS_SIGNING_CERTIFICATE_BASE64` | Base64-encoded Authenticode `.pfx` certificate |
| `WINDOWS_SIGNING_CERTIFICATE_PASSWORD` | Password for the Windows certificate |
| `MACOS_SIGNING_CERTIFICATE_BASE64` | Base64-encoded Apple Developer `.p12` certificate |
| `MACOS_SIGNING_CERTIFICATE_PASSWORD` | Password for the Apple certificate |
| `MACOS_SIGNING_IDENTITY` | Exact `codesign` identity |
| `APPLE_ID` | Apple Developer account for notarization |
| `APPLE_TEAM_ID` | Apple Developer team identifier |
| `APPLE_APP_PASSWORD` | App-specific password for `notarytool` |
| `RELEASE_SIGNING_KEY_BASE64` | Base64-encoded armored GPG private key for release assets |
| `RELEASE_SIGNING_KEY_PASSPHRASE` | Passphrase for the GPG release key |
| `RELEASE_SIGNING_KEY_FINGERPRINT` | Full, space-free fingerprint of the public release key; the workflow fails if the imported key differs |

Windows signing uses SHA-256 Authenticode with a public timestamp service. macOS
signing uses a hardened runtime, then notarizes and staples the DMG. The release
job also signs source archives, installers, wheels, Manager packages and portable archives, and
`SHA256SUMS` with GPG and verifies each signature before publication. Container
images are signed and verified with keyless Sigstore signing.

If any required signing secret is absent or invalid, the workflow fails before
publishing. Never print secrets or store certificates or private keys in the
repository.

After publishing, the workflow verifies every expected download URL and required
`.asc` asset; all Manager packages and portable archives are included in `SHA256SUMS`.

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
