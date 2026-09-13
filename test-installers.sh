#!/usr/bin/env bash
# Static and dry-run checks for the TrinaxAI lifecycle scripts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/trinaxai-installer-tests.XXXXXX")"
trap 'rm -rf -- "$TMP_DIR"' EXIT

fail() { printf '[FAIL] %s\n' "$1" >&2; exit 1; }
ok() { printf '[OK] %s\n' "$1"; }

while IFS= read -r -d '' script; do
  bash -n "$script" || fail "bash -n failed: ${script#$ROOT/}"
done < <(find "$ROOT" -type f -name '*.sh' -print0)
ok "All shell scripts pass bash -n"

for script in install.ps1 update.ps1 uninstall.ps1; do
  bom=$(od -An -tx1 -N3 "$ROOT/$script" | tr -d '[:space:]')
  [ "$bom" = "efbbbf" ] || fail "$script must be UTF-8 with BOM for Windows PowerShell 5.1"
done
ok "PowerShell scripts are UTF-8 BOM compatible with Windows PowerShell 5.1"

if grep -Fq 'npm run build >/dev/null 2>&1' "$ROOT/install.sh"; then
  fail "macOS frontend build output must not be hidden"
fi
ok "macOS frontend failures remain visible"

for script in install.sh update.sh; do
  grep -Fq 'TRINAXAI_NPM_CACHE' "$ROOT/$script" || fail "npm cache override is missing: $script"
  grep -Fq -- '--cache "$cache_dir"' "$ROOT/$script" || fail "dedicated npm cache is not used: $script"
  grep -Fq 'trinaxai-npm-cache.XXXXXX' "$ROOT/$script" || fail "temporary npm cache fallback is missing: $script"
done
ok "PWA installs isolate npm cache permissions and have a clean-cache fallback"

for script in install.sh update.sh uninstall.sh; do
  grep -Fq 'pause_on_macos_failure' "$ROOT/$script" || fail "macOS failure pause is missing: $script"
done
ok "macOS lifecycle failures remain visible"

if grep -R -Fq 'Invoke-RestMethod -Uri "$base/SHA256SUMS"' \
  "$ROOT"/*.md "$ROOT"/docs/*.md 2>/dev/null; then
  fail "PowerShell checksum examples must read SHA256SUMS line by line"
fi
ok "PowerShell release checksum examples parse manifest lines"

if grep --line-number --fixed-strings 'realpath -m' \
  "$ROOT/install.sh" "$ROOT/update.sh" "$ROOT/uninstall.sh" \
  "$ROOT/install.ps1" "$ROOT/update.ps1" "$ROOT/uninstall.ps1"; then
  fail "GNU-only realpath -m usage found"
fi
ok "No realpath -m usage found"

for script in install.sh update.sh install.ps1 update.ps1; do
  grep -Fq -- '--require-hashes' "$ROOT/$script" || fail "locked dependency hashes are not enforced: $script"
done
ok "Locked dependency installs enforce hashes"

if grep -Ein 'command -v git|git (clone|fetch|merge|pull)|Require-Command "git"' \
  "$ROOT/install.sh" "$ROOT/update.sh" "$ROOT/uninstall.sh" \
  "$ROOT/install.ps1" "$ROOT/update.ps1" "$ROOT/uninstall.ps1"; then
  fail "Git dependency found in lifecycle scripts"
fi
ok "Lifecycle scripts do not require Git"

grep -Fq 'releases/download/v${release_version}' "$ROOT/install.sh" || fail "installer does not pin a versioned source archive"
grep -Fq 'releases/download/v${RELEASE_VERSION}' "$ROOT/update.sh" || fail "updater does not pin a versioned source archive"
if grep -Fq 'archive/refs/heads/main' "$ROOT/install.sh" "$ROOT/install.ps1"; then
  fail "installer can download an unpinned main archive"
fi
grep -Fq 'SHA-256 verification' "$ROOT/install.sh" || fail "installer source checksum verification is missing"
grep -Fq 'sha256sum' "$ROOT/install.sh" || fail "installer SHA-256 digest calculation is missing"
grep -Fq 'Get-FileHash -Algorithm SHA256' "$ROOT/install.ps1" || fail "PowerShell installer checksum verification is missing"
grep -Fq 'assert_runtime_ready' "$ROOT/install.sh" || fail "installer readiness gate is missing"
grep -Fq 'assert_runtime_ready' "$ROOT/update.sh" || fail "updater readiness gate is missing"
grep -Fq 'Assert-RuntimeReady' "$ROOT/install.ps1" || fail "PowerShell installer readiness gate is missing"
grep -Fq 'Assert-RuntimeReady' "$ROOT/update.ps1" || fail "PowerShell updater readiness gate is missing"
grep -Fq 'Installation prepared; TrinaxAI is not running.' "$ROOT/install.sh" || fail "installer no-start status is misleading"
grep -Fq 'if [ "$START_NOW" = "1" ]; then' "$ROOT/install.sh" || fail "installer live URLs are not conditional on startup"
grep -Fq 'configured_models()' "$ROOT/install.sh" || fail "installer does not read persisted model configuration"
grep -Fq 'for model in "${MODELS[@]}"; do' "$ROOT/install.sh" || fail "installer model checks do not use persisted models"
grep -Fq 'Model downloads deferred; run the installer again when you are ready.' "$ROOT/install.sh" || fail "POSIX no-model mode is not deferred"
grep -Fq 'if [ "$INSTALL_MODELS" = "1" ]; then' "$ROOT/install.sh" || fail "POSIX installer model verification is not conditional"
grep -Fq 'Model downloads skipped; model preparation is deferred.' "$ROOT/install.ps1" || fail "PowerShell no-model mode is not deferred"
grep -Fq 'if (-not $NoModels)' "$ROOT/install.ps1" || fail "PowerShell installer model verification is not conditional"
grep -Fq 'runtime readiness check deferred' "$ROOT/update.sh" || fail "POSIX updater no-restart readiness is not deferred"
grep -Fq 'runtime readiness check deferred' "$ROOT/update.ps1" || fail "PowerShell updater no-restart readiness is not deferred"
grep -Fq -- '--no-recovery' "$ROOT/uninstall.sh" || fail "uninstaller can leave the recovery server running"
posix_autostart_guard_line="$(grep -nF 'if [ "$START_NOW" = "1" ] && [ "$ENABLE_AUTOSTART" = "1" ]; then' "$ROOT/install.sh" | tail -n 1 | cut -d: -f1)"
[ -n "$posix_autostart_guard_line" ] || fail "installer autostart is not gated on startup"
posix_autostart_block="$(sed -n "${posix_autostart_guard_line},$((posix_autostart_guard_line + 3))p" "$ROOT/install.sh")"
grep -Fq 'python service_manager.py enable-autostart' <<< "$posix_autostart_block" || fail "installer autostart command is outside the no-start guard"
posix_autostart_test_block="$TMP_DIR/posix-autostart-block.sh"
sed -n "${posix_autostart_guard_line},$((posix_autostart_guard_line + 8))p" "$ROOT/install.sh" > "$posix_autostart_test_block"
if (
  START_NOW=0 ENABLE_AUTOSTART=1
  python() { touch "$TMP_DIR/posix-autostart-called"; }
  print_info() { :; }
  print_ok() { :; }
  print_warn() { :; }
  SCRIPT_DIR="$TMP_DIR"
  source "$posix_autostart_test_block"
  [ ! -e "$TMP_DIR/posix-autostart-called" ]
); then
  ok "POSIX --no-start skips autostart execution"
else
  fail "POSIX --no-start invoked autostart"
fi
configured_models_test="$TMP_DIR/configured-models.sh"
awk '/^env_file_value\(\) \{/{capture=1} /^ollama_model_installed\(\) \{/{exit} capture' "$ROOT/install.sh" > "$configured_models_test"
printf '%s\n' \
  'TRINAXAI_MODEL_CODE=custom-code' \
  'TRINAXAI_MODEL_DEEP=custom-deep' \
  'TRINAXAI_MODEL_GENERAL=custom-general' \
  'TRINAXAI_MODEL_FAST=custom-fast' \
  'TRINAXAI_EMBED=custom-embed' > "$TMP_DIR/.env"
configured_models_output="$(cd "$TMP_DIR" && bash -c 'source "$1"; configured_models; printf "%s\\n" "${MODELS[@]}"' _ "$configured_models_test")"
expected_models=$'custom-code\ncustom-deep\ncustom-general\ncustom-fast\ncustom-embed'
[ "$configured_models_output" = "$expected_models" ] || fail "POSIX installer ignored persisted model configuration"
ok "POSIX installer reads persisted model configuration"
grep -Fq 'Installation prepared; TrinaxAI is not running.' "$ROOT/install.ps1" || fail "PowerShell installer no-start status is misleading"
grep -Fq 'function Get-ConfiguredModels' "$ROOT/install.ps1" || fail "PowerShell installer does not read persisted model configuration"
grep -Fq '$Models = @(Get-ConfiguredModels)' "$ROOT/install.ps1" || fail "PowerShell installer model checks do not use persisted models"
ps_autostart_guard_line="$(grep -nF 'if (-not $NoStart -and -not $NoAutostart) {' "$ROOT/install.ps1" | tail -n 1 | cut -d: -f1)"
[ -n "$ps_autostart_guard_line" ] || fail "PowerShell installer autostart is not gated on startup"
ps_autostart_block="$(sed -n "${ps_autostart_guard_line},$((ps_autostart_guard_line + 3))p" "$ROOT/install.ps1")"
grep -Fq '"enable-autostart"' <<< "$ps_autostart_block" || fail "PowerShell installer autostart command is outside the no-start guard"
grep -Fq 'smoke_inference' "$ROOT/install.sh" || fail "installer smoke inference is missing"
grep -Fq 'smoke' "$ROOT/update.sh" || fail "updater smoke inference is missing"
grep -Fq 'detect_hardware' "$ROOT/install.sh" || fail "installer hardware detection is not canonical"
grep -Fq 'model_recommendations' "$ROOT/install.sh" || fail "installer model recommendations are not canonical"
grep -Fq 'select_profile' "$ROOT/install.sh" || fail "installer profile selection is not canonical"
grep -Fq 'detect_hardware' "$ROOT/install.ps1" || fail "PowerShell installer hardware detection is not canonical"
grep -Fq 'model_recommendations' "$ROOT/install.ps1" || fail "PowerShell installer model recommendations are not canonical"
grep -Fq 'select_profile' "$ROOT/install.ps1" || fail "PowerShell installer profile selection is not canonical"
grep -Fq 'INTERACTIVE="${TRINAXAI_INTERACTIVE:-1}"' "$ROOT/update.sh" || fail "shell updater is not guided by default"
grep -Fq '$Interactive = $true' "$ROOT/update.ps1" || fail "PowerShell updater is not guided by default"
grep -Fq 'qwen3-embedding:4b' "$ROOT/uninstall.sh" || fail "shell purge misses the current large embedding model"
grep -Fq 'qwen3-embedding:4b' "$ROOT/uninstall.ps1" || fail "PowerShell purge misses the current large embedding model"
ok "Release pinning, checksums, canonical profiles, readiness gates, and embedding purge checks found"

grep -Fq 'python3 -m pip --version' "$ROOT/install.sh" || fail "installer does not check pip availability"
grep -Fq 'python3 -m venv --help' "$ROOT/install.sh" || fail "installer does not check venv availability"
grep -Fq 'process.versions.node.split(".")[0]) >= 22' "$ROOT/install.sh" || fail "installer does not refresh an old Node.js runtime"
grep -Fq 'https://nodejs.org/dist/index.json' "$ROOT/install.sh" || fail "installer has no verified Node.js fallback"
grep -Fq 'SHASUMS256.txt' "$ROOT/install.sh" || fail "installer does not verify the Node.js archive manifest"
if (cd "$ROOT" && TRINAXAI_HOME=relative bash install.sh --dry-run >"$TMP_DIR/relative-install.out" 2>&1); then
  fail "installer accepted a relative installation directory"
fi
grep -Fq 'absolute path' "$TMP_DIR/relative-install.out" || fail "relative installation path error is unclear"
ok "Linux dependency and installation-path guards found"

if (cd "$ROOT" && TRINAXAI_UPDATE_SOURCE_URL='https://github.com/TrinaxCode/TrinaxAI/archive/refs/heads/main.tar.gz' bash update.sh --dry-run >/dev/null 2>&1); then
  fail "updater accepted an unchecksummed main archive"
fi
ok "Unchecksummed main archive is rejected before update"

for script in install.sh update.sh uninstall.sh; do
  output="$TMP_DIR/${script}.out"
  if ! (cd "$ROOT" && bash -u "$script" --dry-run >"$output" 2>&1); then
    cat "$output" >&2
    fail "dry-run failed: $script"
  fi
  grep -Fq 'Links to enter' "$output" || fail "missing Links to enter: $script"
  if grep -Eiq 'unbound variable|unbound variable' "$output"; then
    fail "unbound variable reported: $script"
  fi
ok "dry-run passed: $script"
done

if command -v python3 >/dev/null 2>&1; then
  generated="$TMP_DIR/continue-config.yaml"
  python3 "$ROOT/scripts/generate_continue_config.py" --root "$ROOT" --output "$generated" --profile 8gb >/dev/null
  grep -Fq '# Generated automatically for TrinaxAI profile 8gb.' "$generated" || fail "Continue profile marker missing"
  grep -Fq 'model: qwen3-embedding:0.6b' "$generated" || fail "Continue embedding profile missing"
  ok "Continue config generation passed"
fi

install_ps1="$ROOT/install.ps1"

if command -v pwsh >/dev/null 2>&1; then
  for script in install.ps1 update.ps1 uninstall.ps1; do
    output="$TMP_DIR/${script}.out"
    pwsh -NoProfile -ExecutionPolicy Bypass -File "$ROOT/$script" -DryRun >"$output" 2>&1 || {
      cat "$output" >&2
      fail "PowerShell dry-run failed: $script"
    }
    grep -Fq 'Links to enter' "$output" || fail "missing PowerShell links: $script"
    ok "PowerShell dry-run passed: $script"
  done
else
  printf '[INFO] pwsh not installed; PowerShell execution checks skipped\n'
fi

printf 'Installer dry-run checks passed.\n'
