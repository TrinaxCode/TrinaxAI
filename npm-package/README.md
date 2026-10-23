# TrinaxAI

**English** · [Español](https://github.com/TrinaxCode/TrinaxAI/blob/main/npm-package/README.es.md)

Install TrinaxAI on Linux, macOS, or Windows with npm:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

The package is a verified launcher. It does not bundle the backend or the PWA.
The setup command downloads the matching official release installer from GitHub,
verifies its SHA-256 checksum, and runs the platform setup.

## What setup does

Setup is guided and available in English and Spanish:

1. A welcome, then the language question (skip it with `--language en|es`).
2. Preflight checks: free disk space and a connection to GitHub. If a proxy
   blocks the direct download, the launcher retries through `curl`.
3. All optional questions up front: model downloads, start now, start with your
   computer, and a weekly update check that only checks and never installs
   without you.
4. An installation plan to confirm. Nothing changes before you accept it.
5. The installation itself, which runs without further attention.

If TrinaxAI is already installed, `trinaxai setup` offers to repair or
reinstall it (your data and settings are kept), update it, uninstall it, or
cancel. Running `trinaxai` alone before installing offers to set it up.

## First run

Check the installation and open the local app:

~~~bash
trinaxai doctor
trinaxai status
~~~

Open https://localhost:3334. The first visit may ask you to trust the local
HTTPS certificate.

## Setup options

Pass options after setup when you need to change the default flow:

~~~bash
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
trinaxai setup --language es
trinaxai setup --dry-run
trinaxai setup --yes
~~~

`--yes` (alias `--non-interactive`) accepts the recommended answers and asks
nothing, for scripts and CI.

Run `trinaxai setup --help` for the complete option list.

## After setup

The launcher forwards commands to the installed TrinaxAI CLI:

~~~bash
trinaxai chat
trinaxai ask "Summarize my indexed files" --engine rag
trinaxai index ./documents
trinaxai doctor --strict
trinaxai update
trinaxai update --dry-run
trinaxai uninstall
trinaxai uninstall --dry-run
~~~

`trinaxai uninstall` asks what to remove and keeps your data, indexes, and
models by default. After it finishes, `npm uninstall -g trinaxai` removes the
launcher itself.

Use `trinaxai --help` for the complete command list and the
[CLI reference](https://github.com/TrinaxCode/TrinaxAI/blob/main/docs/CLI_REFERENCE.md)
for detailed usage.

## Requirements

The launcher runs on Node.js 18 or newer. Use Node.js 22 or newer for the full
setup, which checks and prepares the remaining local runtime, including Python,
Ollama, the PWA, certificates, and model profiles. The package supports Linux,
macOS, and Windows.

## Security

Downloads use HTTPS and the launcher verifies the release checksum before
executing the platform installer. Do not replace the release URL or pipe an
unverified script into a shell.

## Links

- [TrinaxAI repository](https://github.com/TrinaxCode/TrinaxAI)
- [Documentation](https://github.com/TrinaxCode/TrinaxAI/tree/main/docs)
- [Issue tracker](https://github.com/TrinaxCode/TrinaxAI/issues)
- [Website](https://www.trinaxai.app/)
