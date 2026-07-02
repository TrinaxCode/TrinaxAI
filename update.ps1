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
  [switch]$NoAudit
)

<# 
TrinaxAI - Windows updater
Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File .\update.ps1
#>

$ErrorActionPreference = "Stop"

function Write-Step($Text) { Write-Host "`n=== $Text ===`n" -ForegroundColor Blue }
function Write-Ok($Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn($Text) { Write-Host "  [!] $Text" -ForegroundColor Yellow }
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
    foreach ($Model in @("qwen2.5-coder:3b", "llama3.2:3b", "bge-m3", "qwen2.5vl:3b")) {
      Add-Model $List $Model
    }
  }
  return $List
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

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Repo
$PythonExe = Get-PythonExe

Write-Host ""
Write-Host "==========================================" -ForegroundColor Blue
Write-Host " TrinaxAI - Windows updater              " -ForegroundColor Blue
Write-Host "==========================================" -ForegroundColor Blue

$CreateBackup = -not $NoBackup
$PullCode = -not $NoPull
$PullModels = $Models -and -not $NoModels
$RunAudit = -not $NoAudit
$RestartAfter = $Restart -and -not $NoRestart
$AutostartAction = if ($EnableAutostart) { "enable-autostart" } elseif ($DisableAutostart) { "disable-autostart" } else { "" }

if (-not $NonInteractive) {
  $CreateBackup = Read-YesNo "Create a backup before updating?" $true
  $PullCode = Read-YesNo "Pull latest code from Git?" $true
  $PullModels = Read-YesNo "Download/update configured Ollama models too?" $false
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
  if ((Test-Path ".git") -and (Test-Cmd "git")) {
    git pull --ff-only
  } else {
    Write-Warn "Git repository not detected; pull skipped."
  }
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
