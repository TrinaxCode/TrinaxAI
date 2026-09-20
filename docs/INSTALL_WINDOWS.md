<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🪟 Windows
</h1>

<p align="center"><sub><strong>English</strong> · <a href="INSTALL_WINDOWS.es.md">Español</a></sub></p>
<p align="center"><sub><a href="README.md">Documentation</a> · <a href="../README.md">Home</a> · <a href="TROUBLESHOOTING.md">Troubleshooting</a></sub></p>

This guide covers Windows requirements, npm installation, first run, service
operations, firewall behavior, and WSL boundaries.

## Support status

Windows is covered by release checks for backend, frontend, CLI, Python,
PowerShell, security, and the npm launcher. Setup uses a local process
supervisor and keeps the PWA and API on the host by default.

## Requirements

| Resource | Minimum | Recommended |
| --- | ---: | ---: |
| Windows | Windows 10 | Windows 11 |
| Node.js and npm | Node.js 22 with npm | Current Node.js LTS |
| RAM | 8 GB | 16 GB or more |
| Free disk | 5 GB | 10–25 GB |
| Shell | PowerShell 5.1+ | PowerShell 7 |

Use a normal PowerShell window for setup. Windows may ask for administrator
permission when it installs Python, Ollama, or system dependencies.

Check the tools:

~~~powershell
node --version
npm --version
~~~

## Install with npm

Use the same public path as Linux and macOS:

~~~powershell
npm install -g trinaxai@latest
trinaxai setup
~~~

The npm launcher downloads the matching release installer and verifies its
SHA-256 checksum. Setup prepares Python, Ollama, the PWA, certificates,
and the selected models.

Use options only when needed:

~~~powershell
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
trinaxai setup --install-dir D:\Apps\TrinaxAI
~~~

The npm launcher is the supported end-user entrypoint. Do not download or run
install.ps1 directly for a normal installation.

## First run

Check the services:

~~~powershell
trinaxai doctor
trinaxai status
~~~

Open https://localhost:3334. Approve the local certificate in the browser. Then
index a folder and ask a question:

~~~powershell
trinaxai index "$HOME\Documents"
trinaxai ask "Summarize my indexed files" --engine rag
~~~

## Windows service operations

Use the CLI from any PowerShell window:

~~~powershell
trinaxai start
trinaxai stop
trinaxai restart
trinaxai status
~~~

The managed installation uses a local process supervisor. Closing PowerShell
does not stop services that setup has started.

## Firewall and local network

Local access works through localhost. To pair another device, refresh the
address and create a one-time code:

~~~powershell
trinaxai network refresh
trinaxai pair start
~~~

Allow only the local or trusted network prompts that you understand. Never
forward ports 3333, 3334, or 11434 to the public Internet.

## Update, backup, and remove

Use the CLI:

~~~powershell
trinaxai update
trinaxai doctor --strict
trinaxai uninstall
~~~

The default uninstall preserves indexes and Ollama models. Read the
[CLI reference](CLI_REFERENCE.md) before using purge or remove-data options.

## WSL

WSL is not required for a Windows installation. If you choose WSL, follow the
Linux guide inside the distribution and keep its files, network, certificates,
and services separate from the Windows installation.

## Common issues

| Symptom | Action |
| --- | --- |
| npm or node is missing | Install an active Node.js LTS release and open a new PowerShell |
| A command is not found after npm install | Restart PowerShell so PATH changes take effect |
| The PWA certificate is rejected | Open the URL from trinaxai network and trust the local CA |
| Windows Firewall blocks a device | Allow only the private network rule you need |
| The service is offline | Run trinaxai status and trinaxai doctor --strict |

For the full decision table, see [Troubleshooting](TROUBLESHOOTING.md).
