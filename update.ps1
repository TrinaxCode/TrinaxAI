param(
  [switch]$NonInteractive,
  [switch]$NoBackup,
  [switch]$NoPull,
  [switch]$Models,
  [switch]$NoModels,
  [switch]$Restart,
  [switch]$NoRestart,
  [switch]$EnableAutostart,
  [switch]$DisableAutostart,
  [switch]$RepairOllama,
  [switch]$RemoveModels,
  [switch]$RemoveOllama,
  [switch]$NoAudit,
  [switch]$Scheduled,
  [string]$RepoRoot = ""
)

<# 
TrinaxAI - Windows updater
Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File .\update.ps1

Guided mode asks what to update or repair, including Ollama reinstall/removal,
model removal/download, backup, Git pull, autostart, restart, and audit.
#>

$ErrorActionPreference = "Stop"

function Write-Step($Text) { Write-Host "`n  +-- $Text" -ForegroundColor Blue }
function Write-Ok($Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn($Text) { Write-Host "  [!] $Text" -ForegroundColor Yellow }
function Write-Info($Text) { Write-Host "  [>] $Text" -ForegroundColor Cyan }
function Test-Cmd($Name) { return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }
function Read-YesNo($Prompt, [bool]$DefaultYes = $true) {
  if ($NonInteractive) { return $DefaultYes }
  $Suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
  $Reply = Read-Host "$Prompt $Suffix"
  if ([string]::IsNullOrWhiteSpace($Reply)) { return $DefaultYes }
  return ($Reply -match "^[Yy]")
}
function Get-PythonExe {
  $Venv = Join-Path $Repo ".venv\Scripts\python.exe"
  if (Test-Path $Venv) { return $Venv }
  if (Test-Cmd "py") { return "py" }
  if (Test-Cmd "python") { return "python" }
  return $null
}
function Invoke-Python([string[]]$PythonArgs) {
  if ($PythonExe -eq "py") {
    & py -3 @PythonArgs
  } else {
    & $PythonExe @PythonArgs
  }
}
function Get-OllamaCommand {
  $Candidates = @(
    "ollama",
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
  )
  foreach ($Candidate in $Candidates) {
    if ($Candidate -and (Test-Cmd $Candidate)) { return $Candidate }
  }
  return $null
}
function Test-OllamaReady {
  try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null
    return $true
  } catch {
    return $false
  }
}
function Ensure-OllamaRunning {
  $Ollama = Get-OllamaCommand
  if (-not $Ollama) { return $null }
  if (Test-OllamaReady) { return $Ollama }
  Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden | Out-Null
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-OllamaReady) { return $Ollama }
  }
  return $null
}
function Stop-OllamaProcesses {
  try {
    Get-CimInstance Win32_Process |
      Where-Object { $_.CommandLine -and ($_.CommandLine -like "*ollama*") } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  } catch {
    Write-Warn "Could not enumerate Ollama processes."
  }
}
function Invoke-ExternalWithTimeout([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSec = 90) {
  try {
    $Proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru -WindowStyle Hidden
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
      Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
      Write-Warn "$FilePath timed out after ${TimeoutSec}s."
      return $false
    }
    return ($Proc.ExitCode -eq 0)
  } catch {
    Write-Warn "Could not run ${FilePath}: $($_.Exception.Message)"
    return $false
  }
}
function Install-OllamaOfficial {
  Write-Host "  Installing Ollama with: irm https://ollama.com/install.ps1 | iex"
  try {
    $PowerShellExe = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Source
    if (-not $PowerShellExe) { $PowerShellExe = "powershell.exe" }
    $Command = "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; irm https://ollama.com/install.ps1 | iex"
    & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -Command $Command
    if ($LASTEXITCODE -ne 0) { return $false }
    return [bool](Get-OllamaCommand)
  } catch {
    Write-Warn "Official Ollama install command failed: $($_.Exception.Message)"
    return $false
  }
}
function Remove-KnownDirectory([string]$Path, [string]$Label) {
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  try {
    $Full = [IO.Path]::GetFullPath($Path)
    if ($Full.Length -lt 10) { throw "Unsafe path: $Full" }
    if (Test-Path -LiteralPath $Full) {
      Remove-Item -LiteralPath $Full -Recurse -Force
      Write-Ok "Removed $Label"
    }
  } catch {
    Write-Warn "Could not remove ${Label}: $($_.Exception.Message)"
  }
}
function Remove-OllamaApp {
  Stop-OllamaProcesses
  if (Test-Cmd "winget") {
    Invoke-ExternalWithTimeout "winget" @("uninstall", "--id", "Ollama.Ollama", "--silent", "--accept-source-agreements") 120 | Out-Null
  }
  Stop-OllamaProcesses
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Programs\Ollama") "Ollama app"
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Ollama") "Ollama local app data"
  Remove-KnownDirectory (Join-Path $env:APPDATA "Ollama") "Ollama roaming app data"
  Remove-KnownDirectory (Join-Path $env:ProgramFiles "Ollama") "Ollama Program Files app"
}
function Read-EnvValue($Key) {
  $EnvPath = Join-Path $Repo ".env"
  if (-not (Test-Path $EnvPath)) { return "" }
  foreach ($Line in Get-Content -LiteralPath $EnvPath) {
    if ($Line -match "^\s*$([regex]::Escape($Key))=(.*)$") {
      return $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
  return ""
}
function Add-Model([System.Collections.Generic.List[string]]$List, $Model) {
  if (-not [string]::IsNullOrWhiteSpace($Model) -and -not $List.Contains($Model)) {
    $List.Add($Model) | Out-Null
  }
}
function Get-ConfiguredModels {
  $List = New-Object System.Collections.Generic.List[string]
  Add-Model $List (Read-EnvValue "TRINAXAI_MODEL_CODE")
  Add-Model $List (Read-EnvValue "TRINAXAI_MODEL_DEEP")
  Add-Model $List (Read-EnvValue "TRINAXAI_MODEL_GENERAL")
  Add-Model $List (Read-EnvValue "TRINAXAI_MODEL_FAST")
  Add-Model $List (Read-EnvValue "TRINAXAI_EMBED")
  Add-Model $List (Read-EnvValue "VITE_TRINAXAI_VISION_MODEL")
  if ($List.Count -eq 0) {
    foreach ($Model in @("qwen2.5-coder:3b", "qwen3:4b-instruct-2507-q4_K_M", "bge-m3", "qwen3-vl:4b")) {
      Add-Model $List $Model
    }
  }
  return $List
}
function Remove-ConfiguredModels {
  $Ollama = Get-OllamaCommand
  if ($Ollama) {
    foreach ($Model in Get-ConfiguredModels) {
      Write-Host "  Removing $Model..."
      & $Ollama rm $Model 2>$null
    }
  }
  Remove-KnownDirectory (Join-Path $env:USERPROFILE ".ollama\models") "Ollama models"
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Ollama\models") "Ollama local models"
}
function New-TrinaxAIBackup {
  $BackupDir = Join-Path $Repo "backups"
  New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
  $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $ZipPath = Join-Path $BackupDir "trinaxai-backup-$Stamp.zip"
  $Items = @(".env", "storage", "local_sources", "chat-pwa\certs", "logs") |
    Where-Object { Test-Path (Join-Path $Repo $_) } |
    ForEach-Object { Join-Path $Repo $_ }
  if ($Items.Count -eq 0) {
    Write-Warn "No runtime files found to back up."
    return
  }
  Compress-Archive -Path $Items -DestinationPath $ZipPath -Force
  Write-Ok "Backup created: $ZipPath"
}
function Invoke-ServiceManager($Action) {
  if (-not $PythonExe) { Write-Warn "Python not found; skipped service_manager $Action."; return }
  Invoke-Python @((Join-Path $Repo "service_manager.py"), $Action, "--base-dir", $Repo)
}

function Sync-TrinaxRepository {
  $Remote = "https://github.com/TrinaxCode/TrinaxAI.git"
  $Managed = Test-Path ".trinaxai-managed"
  if (-not (Test-Cmd "git")) { throw "Git is required to update TrinaxAI." }
  Write-Info "Fetching the latest TrinaxAI source from GitHub..."
  if (-not (Test-Path ".git")) {
    git init -q
    if ($Managed) { Add-Content -Encoding UTF8 ".git\info\exclude" ".trinaxai-managed" }
    git remote add origin $Remote
    git fetch --prune origin main
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch origin/main." }
    git reset --hard origin/main
    Write-Ok "Archive installation converted to an updateable Git repository"
    return
  }
  if ($Managed) {
    $Exclude = ".git\info\exclude"
    if (-not (Select-String -Path $Exclude -SimpleMatch ".trinaxai-managed" -Quiet -ErrorAction SilentlyContinue)) {
      Add-Content -Encoding UTF8 $Exclude ".trinaxai-managed"
    }
  }
  git remote get-url origin 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { git remote set-url origin $Remote }
  else { git remote add origin $Remote }
  $Dirty = -not [string]::IsNullOrWhiteSpace((git status --porcelain --untracked-files=normal | Out-String))
  if ($Dirty) {
    if ($Managed) {
      $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
      git stash push --include-untracked -m "TrinaxAI automatic pre-update $Stamp"
      Write-Warn "Local code changes were preserved in Git stash"
    } else {
      throw "Local developer changes detected; update stopped to protect them."
    }
  }
  git fetch --prune origin main
  if ($LASTEXITCODE -ne 0) { throw "Could not fetch origin/main." }
  git merge --ff-only origin/main
  if ($LASTEXITCODE -eq 0) {
    Write-Ok "Repository synchronized with origin/main"
  } elseif ($Managed) {
    git reset --hard origin/main
    Write-Ok "Managed installation synchronized with origin/main"
  } else {
    throw "The local branch diverged from origin/main; update stopped safely."
  }
}

$Repo = if ($RepoRoot) { [IO.Path]::GetFullPath($RepoRoot) } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location $Repo
$PythonExe = Get-PythonExe

Write-Host ""
Write-Host "+========================================+" -ForegroundColor Blue
Write-Host "|          TrinaxAI - Smart Update       |" -ForegroundColor Blue
Write-Host "+========================================+" -ForegroundColor Blue
if ($Scheduled) { Write-Info "Weekly automatic maintenance" }
else { Write-Info "Your data and settings stay untouched" }

$CreateBackup = -not $NoBackup
$PullCode = -not $NoPull
$PullModels = $Models -and -not $NoModels
$RunAudit = -not $NoAudit
$RestartAfter = $Restart -and -not $NoRestart
$AutostartAction = if ($EnableAutostart) { "enable-autostart" } elseif ($DisableAutostart) { "disable-autostart" } else { "" }
$RepairOllamaNow = $RepairOllama
$RemoveModelsFirst = $RemoveModels
$RemoveOllamaApp = $RemoveOllama
$InstallOllamaAfterRemove = $RemoveOllama

if ($Scheduled) {
  $NonInteractive = $true
  $CreateBackup = $false
  $PullCode = $true
  $PullModels = $false
  $RunAudit = $false
  $RestartAfter = $true
}

if (-not $NonInteractive) {
  $CreateBackup = Read-YesNo "Create a backup before updating?" $true
  $PullCode = Read-YesNo "Pull latest code from Git?" $true
  $RemoveOllamaApp = Read-YesNo "Remove Ollama application before continuing?" $false
  if ($RemoveOllamaApp) {
    $InstallOllamaAfterRemove = Read-YesNo "Install Ollama again with the official installer command after removal?" $true
  } else {
    $RepairOllamaNow = Read-YesNo "Repair/reinstall Ollama with the official installer command?" $false
  }
  $PullModels = Read-YesNo "Download/update configured Ollama models too?" $false
  $RemoveModelsFirst = Read-YesNo "Remove configured Ollama models before model update?" $false
  if (Read-YesNo "Change boot auto-start setting?" $false) {
    $AutostartAction = if (Read-YesNo "Start TrinaxAI automatically when Windows starts?" $true) { "enable-autostart" } else { "disable-autostart" }
  }
  $RestartAfter = Read-YesNo "Restart TrinaxAI after the update?" $true
  $RunAudit = Read-YesNo "Run public readiness audit after updating?" $true
}

if (-not $PythonExe) {
  Write-Warn "Python was not found. Run install.ps1 first."
  exit 1
}

if ($CreateBackup) {
  Write-Step "1/7 Backup"
  New-TrinaxAIBackup
}

if ($PullCode) {
  Write-Step "2/7 Git"
  Sync-TrinaxRepository
}

if ($RemoveOllamaApp) {
  Write-Step "Ollama application"
  Remove-OllamaApp
  if ($InstallOllamaAfterRemove) {
    if (Install-OllamaOfficial) { Write-Ok "Ollama installed" } else { Write-Warn "Ollama reinstall failed." }
  } else {
    $PullModels = $false
  }
} elseif ($RepairOllamaNow) {
  Write-Step "Ollama repair"
  if (Install-OllamaOfficial) { Write-Ok "Ollama installed" } else { Write-Warn "Ollama repair failed." }
}

Write-Step "3/7 Python dependencies"
Invoke-Python @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Python @("-m", "pip", "install", "-r", "requirements.txt")
Invoke-Python @("-m", "pip", "install", "-e", ".")
Write-Ok "Python dependencies updated"

Write-Step "4/7 PWA frontend"
if ((Test-Cmd "npm") -and (Test-Path "chat-pwa")) {
  Push-Location "chat-pwa"
  npm install
  npm run build
  Pop-Location
  Write-Ok "PWA rebuilt"
} else {
  Write-Warn "npm or chat-pwa not found; PWA build skipped."
}

if ($PullModels) {
  Write-Step "5/7 Ollama models"
  if ($RemoveModelsFirst) {
    Remove-ConfiguredModels
  }
  $Ollama = Ensure-OllamaRunning
  if ($Ollama) {
    foreach ($Model in Get-ConfiguredModels) {
      Write-Host "  Pulling $Model..."
      & $Ollama pull $Model
    }
    Write-Ok "Models updated"
  } else {
    Write-Warn "Ollama is not available; model update skipped."
  }
}

Write-Step "6/7 Autostart and audit"
if ($AutostartAction) {
  Invoke-ServiceManager $AutostartAction
}
if ($RunAudit -and (Test-Path "scripts\public_readiness.py")) {
  Invoke-Python @("scripts\public_readiness.py")
} elseif ($RunAudit) {
  Write-Warn "scripts\public_readiness.py not found; audit skipped."
}

Write-Step "7/7 Restart"
if ($RestartAfter) {
  Invoke-ServiceManager "stop-all"
  Invoke-ServiceManager "start"
  Write-Ok "TrinaxAI restarted"
} else {
  Write-Warn "Restart skipped. Run .\.venv\Scripts\trinaxai.exe start when ready."
}

Write-Ok "TrinaxAI update finished"
Write-Info "Settings, indexes, models, and personal data were preserved."
