<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🐧 Linux
</h1>

<p align="center"><sub><strong>English</strong> · <a href="INSTALL_LINUX.es.md">Español</a></sub></p>
<p align="center"><sub><a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="TROUBLESHOOTING.md">Troubleshooting</a></sub></p>

This guide explains the Linux requirements, npm installation, first run, and
service operations. It covers Ubuntu, Debian, Fedora, Arch, openSUSE, and
similar distributions.

## Support status

Linux is the primary CI-tested platform. The release checks backend, frontend,
CLI, public readiness, security, and the npm launcher on Linux. Hardware
drivers, permissions, and model download speed depend on your machine.

## Requirements

| Resource | Minimum | Recommended |
| --- | ---: | ---: |
| Node.js and npm | Node.js 22 with npm | Current Node.js LTS |
| RAM | 8 GB | 16 GB or more |
| Free disk | 5 GB | 10–25 GB |
| Architecture | x86_64 or arm64 | A supported Ollama target |

You do not need Git for a normal installation. Install NVIDIA or AMD drivers
before downloading large models. TrinaxAI also works with CPU-only hardware.

Check the tools before setup:

~~~bash
node --version
npm --version
~~~

## Install with npm

Run the same public installation path used on every supported platform:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

The npm launcher downloads the matching release installer and verifies its
SHA-256 checksum. Setup then checks Python, Node.js, Ollama, storage,
models, certificates, and the PWA. Approve the package-manager prompt when
Linux asks for permission.

Use an option only when you need it:

~~~bash
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
~~~

The npm launcher is the supported end-user entrypoint. Do not run install.sh
from a source checkout for a normal installation; that path belongs to release
internals and development.

## First run

Check the services:

~~~bash
trinaxai doctor
trinaxai status
~~~

Open https://localhost:3334. The browser may ask you to trust the local
certificate. If you skipped models, run setup again without --no-models.

Index a folder and ask a cited question:

~~~bash
trinaxai index ~/Documents
trinaxai ask "Summarize my indexed files" --engine rag
~~~

## Linux service operations

The managed installation stores the application under
XDG_DATA_HOME/trinaxai, normally ~/.local/share/trinaxai. It also recognizes a
legacy ~/trinaxai installation. Use the CLI from any directory:

~~~bash
trinaxai start
trinaxai stop
trinaxai restart
trinaxai status
~~~

Setup can enable user-level systemd autostart. Keep host administration
localhost-only unless you understand the security model.

## Local network access

To pair a phone or browser on the same network, refresh the address and local
certificate:

~~~bash
trinaxai network refresh
trinaxai pair start
~~~

Follow [LAN pairing](NETWORK_PAIRING.md). Do not expose ports 3333, 3334, or
11434 directly to the Internet.

## Update, backup, and remove

Create a backup before upgrades or index changes:

~~~bash
trinaxai update
trinaxai doctor --strict
trinaxai uninstall
~~~

The default uninstall keeps indexes and Ollama models. Use the destructive
purge options only after reading the [CLI reference](CLI_REFERENCE.md).

## Docker and source development

Docker Compose and source checkouts are separate operator and developer paths.
They are not alternative end-user installers. Use the
[developer guide](DEVELOPER_GUIDE.md) for a checkout and the repository
compose documentation for a container deployment.

## Common issues

| Symptom | Action |
| --- | --- |
| npm or node is missing | Install an active Node.js LTS release, open a new terminal, and retry |
| Ollama is not ready | Run trinaxai doctor, then check the Ollama service |
| The PWA certificate is rejected | Open the URL printed by trinaxai network and trust the local CA |
| A model is too slow | Choose a smaller profile with trinaxai setup --profile 8gb |
| The service is offline | Run trinaxai status and trinaxai doctor --strict |

If the issue remains, follow [Troubleshooting](TROUBLESHOOTING.md) and include
redacted diagnostic output when requesting support.
