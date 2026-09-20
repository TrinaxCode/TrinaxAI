<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🍎 macOS
</h1>

<p align="center"><sub><strong>English</strong> · <a href="INSTALL_MACOS.es.md">Español</a></sub></p>
<p align="center"><sub><a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="TROUBLESHOOTING.md">Troubleshooting</a></sub></p>

This guide covers the macOS requirements, npm installation, first run, local
networking, and service operations on Intel and Apple Silicon.

## Support status

macOS is covered by the release checks for backend, frontend, CLI, Python,
security, and the npm launcher. Apple Silicon uses unified memory when setup
chooses a model profile.

## Requirements

| Resource | Minimum | Recommended |
| --- | ---: | ---: |
| Node.js and npm | Node.js 22 with npm | Current Node.js LTS |
| RAM | 8 GB | 16 GB or more |
| Free disk | 5 GB | 10–25 GB |
| CPU | Intel or Apple Silicon | Apple Silicon for local models |

Keep macOS updated and allow Terminal to access folders you plan to index.
Check the tools before setup:

~~~bash
node --version
npm --version
~~~

## Install with npm

Use the same public path as Linux and Windows:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

The npm launcher downloads the matching release installer and verifies its
SHA-256 checksum. Setup prepares Python, Node.js, Ollama, the PWA, local
certificates, and the selected models.

Use options only when needed:

~~~bash
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
~~~

The npm launcher is the supported end-user entrypoint. The shell installer is
release implementation code; do not run it directly for a normal installation.

## First run

Run the health check:

~~~bash
trinaxai doctor
trinaxai status
~~~

Open https://localhost:3334. Approve the local certificate in the browser when
macOS asks for trust. Then index a folder:

~~~bash
trinaxai index ~/Documents
trinaxai ask "Summarize my indexed files" --engine rag
~~~

## macOS service operations

Use the CLI from any directory:

~~~bash
trinaxai start
trinaxai stop
trinaxai restart
trinaxai status
~~~

The managed installation uses a user-level launchd lifecycle. Do not delete the
application directory while services are running. Stop TrinaxAI first.

## Local network access

Refresh the local address and certificate before pairing another device:

~~~bash
trinaxai network refresh
trinaxai pair start
~~~

Follow [LAN pairing](NETWORK_PAIRING.md). Keep local service ports private and
use a VPN for networks you do not control.

## Update, backup, and remove

Use the CLI for maintenance:

~~~bash
trinaxai update
trinaxai doctor --strict
trinaxai uninstall
~~~

The default uninstall keeps indexes and Ollama models. Read the
[CLI reference](CLI_REFERENCE.md) before using purge options.

## Common issues

| Symptom | Action |
| --- | --- |
| npm or node is missing | Install an active Node.js LTS release and open a new terminal |
| macOS blocks a local action | Review System Settings, Privacy & Security, then retry setup |
| The PWA certificate is rejected | Open the URL from trinaxai network and trust the local CA |
| A model uses too much memory | Re-run setup with a smaller profile |
| The service is offline | Run trinaxai status and trinaxai doctor --strict |

For a full decision table, see [Troubleshooting](TROUBLESHOOTING.md).
