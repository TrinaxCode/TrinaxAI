# TrinaxAI

Install TrinaxAI on Linux, macOS, or Windows with npm:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

The package is a verified launcher. It does not bundle the backend or the PWA.
The setup command downloads the matching official release installer from GitHub,
verifies its SHA-256 checksum, and runs the platform setup.

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
trinaxai setup --dry-run
~~~

Run `trinaxai setup --help` for the complete option list.

## After setup

The launcher forwards commands to the installed TrinaxAI CLI:

~~~bash
trinaxai chat
trinaxai ask "Summarize my indexed files" --engine rag
trinaxai index ./documents
trinaxai doctor --strict
trinaxai update
trinaxai uninstall
~~~

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
