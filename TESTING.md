# Installer Testing

[Español](TESTING.es.md)

These checks are deliberately split into Manager tests, script simulation, and real-machine tests. Dry-run never downloads the source package or Ollama, installs packages, starts services, changes PATH, edits launch agents, or removes files.

## Graphical Manager smoke test

Test the normal user journey first:

1. Download the Manager package for the target operating system from the [TrinaxAI 1.2.0 release](https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0).
   Use the `.exe` on Windows, `.dmg` on macOS, or `.deb` on Debian/Ubuntu. Portable ZIP/TAR.GZ fallbacks are published alongside them.
2. Open it and select **Install**. Confirm that no command needs to be copied or typed.
3. Reopen it and test **Update**, then **Uninstall**.
4. Confirm that Git is not installed or requested and that the detected profile is one of `8gb`, `16gb`, `32gb`, or `64gb`.

The command-line checks below validate the advanced fallback scripts; they are not the normal installation instructions.

## Local Dry-Run

From the repository root:

```bash
chmod +x test-installers.sh
./test-installers.sh
./install.sh --dry-run
./update.sh --dry-run
./uninstall.sh --dry-run
```

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -DryRun
.\update.ps1 -DryRun
.\uninstall.ps1 -DryRun
```

The output must contain the localized access-links label: `Links to enter` in English or `Enlaces de acceso` in Spanish. The Windows install simulation also prints the official Ollama fallback instructions.

## Advanced script test: macOS real machine

Use a normal user account with Homebrew available or allow the installer to offer Homebrew installation. Review the script before running a network installer.

```bash
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh -o /tmp/trinaxai-install.sh
bash /tmp/trinaxai-install.sh --dry-run
bash /tmp/trinaxai-install.sh

cd "$HOME/Library/Application Support/TrinaxAI"
./update.sh --dry-run
./update.sh
./uninstall.sh --dry-run
./uninstall.sh
```

For a destructive removal of runtime data, models, certificates, and Ollama, use `./uninstall.sh --purge` only after confirming the data is backed up.

Verify the real install with `ollama list`, `curl -kfsS https://127.0.0.1:3333/health`, the localhost link, and the LAN link from another device on the same network.

## Advanced script test: Windows real machine

Run PowerShell as the user who will run TrinaxAI. The installer may request Administrator permission for firewall rules.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$installer = Join-Path $env:TEMP "trinaxai-install.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.ps1" -OutFile $installer
Get-Content -Path $installer
& $installer
```

For a safe simulation from a downloaded script:

```powershell
irm https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.ps1 -OutFile "$env:TEMP\trinaxai-install.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\trinaxai-install.ps1" -DryRun
```

After installation, run from the installation directory:

```powershell
.\update.ps1 -DryRun
.\update.ps1
.\uninstall.ps1 -DryRun
.\uninstall.ps1
```

If automatic Ollama installation fails, the official `OllamaSetup.exe` is opened. Click `Install`, wait for completion, then press Enter in the installer window. Confirm with `Get-Command ollama` and `& (Get-Command ollama).Source list`.

## GitHub Actions

`.github/workflows/test-installers.yml` runs syntax and dry-run checks on `ubuntu-latest`, `macos-latest`, and `windows-latest`, and builds/packages the Windows Manager smoke artifact. It does not install Ollama or attempt to emulate another operating system. The release workflow builds all three native packages plus portable fallbacks on their native runners and verifies every published download URL.

## RAG quality evaluation

With the API running and the golden corpus indexed into `rag-eval`, run the
same reproducible evaluation used by the release checks:

```bash
make rag-eval RAG_API_URL=http://127.0.0.1:3333
```

The command writes `rag-eval-report.json` and fails when retrieval, grounding,
citations, or abstention fall below the configured thresholds. It intentionally
requires a live indexed API; fixture validation alone is not a model-quality
claim.

## Documentation checks

For documentation-only changes, run the smallest relevant checks plus the PWA
documentation test:

```bash
cd chat-pwa
npx vitest run src/components/Docs.test.tsx
npx tsc --noEmit
cd ..
git diff --check
```

Review local Markdown targets manually after moving a file. Keep English and
`.es.md` counterparts aligned, verify every command against the current source
rather than copying an old example, and confirm that the recovery guide still
matches the actions exposed by `api_errors.ts` and `MessageList.tsx`.
