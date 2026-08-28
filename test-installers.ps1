[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Assert-Contains([string]$Text, [string]$Needle, [string]$Message) {
  if ($Text.IndexOf($Needle, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw $Message
  }
}
function Assert-NotMatches([string]$Text, [string]$Pattern, [string]$Message) {
  if ($Text -match $Pattern) { throw $Message }
}
function Invoke-PowerShellDryRun([string]$Script, [string[]]$Arguments = @()) {
  if (-not $PowerShellEngine) { return "" }
  $Output = & $PowerShellEngine.Source -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root $Script) @Arguments 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) { throw "PowerShell dry-run failed: $Script`n$Output" }
  Assert-Contains $Output "Links to enter" "Missing links output: $Script"
  return $Output
}

$PowerShellEngine = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $PowerShellEngine) { $PowerShellEngine = Get-Command powershell.exe -ErrorAction SilentlyContinue }

$Install = Get-Content -Raw (Join-Path $Root "install.ps1")
$Update = Get-Content -Raw (Join-Path $Root "update.ps1")
$Uninstall = Get-Content -Raw (Join-Path $Root "uninstall.ps1")
$Lifecycle = @($Install, $Update, $Uninstall) -join "`n"

Assert-Contains $Install "Se ha abierto el instalador oficial de Ollama." "Missing Ollama fallback message"
Assert-Contains $Install "Get-ValidatedRemoteArchiveUrl" "Missing remote archive URL validation"
Assert-Contains $Install "Test-ZipArchiveEntries" "Missing archive entry validation"
Assert-Contains $Install "Expand-Archive -LiteralPath" "Expand-Archive must use a literal validated path"
Assert-Contains $Install "Merge-EnvFileDefaults" "Installer can overwrite existing configuration"
Assert-Contains $Install "ReparsePoint" "Installer must reject a symbolic-link .env"
Assert-Contains $Install "-TimeoutSec 120" "Remote download timeout is missing"
Assert-NotMatches $Install '\$EnvLines\s*\|\s*Set-Content' "Installer must merge existing configuration"
Assert-Contains $Install 'Install-RemoteRepository -Target $Repo' "Missing checked remote repository install"
Assert-Contains $Install "Invoke-NativeChecked" "Installer hides native command failures"
Write-Host "[OK] Install remote archive, path, and error checks found"

Assert-Contains $Update "Sync-TrinaxRepository" "Missing source synchronization"
Assert-Contains $Update "scripts\source_update.py" "Missing archive updater"
Assert-Contains $Update "Restore-FailedUpdate" "Missing update rollback"
Assert-Contains $Update '"rollback", "--root", $Repo' "Missing source rollback command"
Assert-Contains $Update "Get-ConfiguredModels" "Updater does not read configured models"
$ConfiguredRemovalStart = $Update.IndexOf("function Remove-ConfiguredModels", [StringComparison]::Ordinal)
$ConfiguredRemovalEnd = $Update.IndexOf("function New-TrinaxAIBackup", [StringComparison]::Ordinal)
if ($ConfiguredRemovalStart -lt 0 -or $ConfiguredRemovalEnd -le $ConfiguredRemovalStart) { throw "Cannot isolate updater model removal" }
$ConfiguredRemoval = $Update.Substring($ConfiguredRemovalStart, $ConfiguredRemovalEnd - $ConfiguredRemovalStart)
Assert-NotMatches $ConfiguredRemoval "Remove-KnownDirectory" "Configured model removal must not delete model directories"
Assert-Contains $Update "Invoke-NativeChecked" "Updater hides native command failures"
$FinishAt = $Update.IndexOf('"finish", "--root", $Repo', [StringComparison]::Ordinal)
$RollbackOffAt = $Update.LastIndexOf('$script:RollbackActive = $false', [StringComparison]::Ordinal)
if ($FinishAt -lt 0 -or $RollbackOffAt -lt 0 -or $FinishAt -gt $RollbackOffAt) {
  throw "Updater disables rollback before finalizing the update"
}
Write-Host "[OK] Update rollback, configured models, and error checks found"

Assert-Contains $Uninstall "Get-ConfiguredModels" "Uninstaller does not read configured models"
Assert-Contains $Uninstall 'if ($RemoveOllamaApp) { Remove-OllamaModelsAndState }' "Full Ollama state removal is not gated"
Assert-Contains $Uninstall "Assert-InRepo" "Missing in-repository deletion guard"
Assert-Contains $Uninstall "Dry-run" "Missing uninstaller dry-run"
$ModelRemovalStart = $Uninstall.IndexOf('if ($RemoveOllamaModels)', [StringComparison]::Ordinal)
$ModelRemovalEnd = $Uninstall.IndexOf('if ($RemoveOllamaApp)', $ModelRemovalStart, [StringComparison]::Ordinal)
if ($ModelRemovalStart -lt 0 -or $ModelRemovalEnd -le $ModelRemovalStart) { throw "Cannot isolate uninstaller model removal" }
$ModelRemoval = $Uninstall.Substring($ModelRemovalStart, $ModelRemovalEnd - $ModelRemovalStart)
Assert-NotMatches $ModelRemoval "Remove-KnownDirectory" "Configured model removal must not delete model directories"
Write-Host "[OK] Uninstall safety and model preservation checks found"

Assert-NotMatches $Lifecycle 'Require-Command\s+"git"|git\s+(clone|fetch|merge|pull)' "Git dependency found in lifecycle scripts"
Write-Host "[OK] Lifecycle scripts do not require Git"

if ($PowerShellEngine) {
  foreach ($Script in @("install.ps1", "update.ps1", "uninstall.ps1")) {
    Invoke-PowerShellDryRun $Script @("-DryRun", "-NonInteractive") | Out-Null
    Write-Host "[OK] PowerShell dry-run passed: $Script"
  }

  $SpacePath = Join-Path $env:TEMP ("trinaxai installer test " + [guid]::NewGuid().ToString("N"))
  $InstallOutput = Invoke-PowerShellDryRun "install.ps1" @("-DryRun", "-NonInteractive", "-InstallDir", $SpacePath)
  Assert-Contains $InstallOutput $SpacePath "Install dry-run lost a path containing spaces"
  if (Test-Path -LiteralPath $SpacePath) { throw "Install dry-run changed the path containing spaces" }
  Write-Host "[OK] PowerShell dry-run preserves paths with spaces"
} else {
  Write-Host "[INFO] pwsh/powershell.exe not installed; PowerShell execution checks skipped"
}

$Bash = Get-Command bash -ErrorAction SilentlyContinue
if ($Bash) {
  & $Bash.Source (Join-Path $Root "test-installers.sh")
  if ($LASTEXITCODE -ne 0) { throw "Shell installer checks failed" }
} else {
  Write-Warning "bash not found; shell checks skipped"
}
