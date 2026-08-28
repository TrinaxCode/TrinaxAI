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
