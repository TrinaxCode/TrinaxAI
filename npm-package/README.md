# TrinaxAI npm CLI

The npm package is a small verified launcher for the official TrinaxAI release.
It does not bundle the backend or the PWA.

```bash
npm install --global trinaxai@latest
trinaxai setup
```

`setup` downloads the platform installer and `SHA256SUMS` from the matching
GitHub release, verifies the installer, and then delegates to the existing
Linux/macOS or Windows installer. After setup, commands such as `trinaxai
doctor`, `trinaxai update`, and `trinaxai uninstall` are forwarded to the
installed CLI.
