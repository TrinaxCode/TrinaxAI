param(
  [switch]$Yes,
  [switch]$NonInteractive,
  [switch]$KeepServices,
  [switch]$KeepAutostart,
  [switch]$KeepVenv,
  [switch]$KeepFrontend,
  [switch]$KeepLogs,
  [switch]$KeepEnv,
  [switch]$RemoveData,
  [switch]$RemoveCerts,
  [switch]$RemoveModels,
  [switch]$RemoveOllama,
  [switch]$Purge,
  [switch]$KeepFirewall
)

<# 
TrinaxAI - Windows uninstaller
Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1 -Purge -Yes

Guided mode asks what to remove:
  - services, autostart, .venv, frontend build/deps, logs, .env
  - RAG index/memory/local_sources, HTTPS certs, firewall rules
  - Ollama models and the Ollama application itself
#>

$ErrorActionPreference = "Stop"

function Write-Step($Text) { Write-Host "`n=== $Text ===`n" -ForegroundColor Blue }
function Write-Ok($Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn($Text) { Write-Host "  [!] $Text" -ForegroundColor Yellow }
function Test-Cmd($Name) { return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }
function Read-YesNo($Prompt, [bool]$DefaultYes = $true) {
  if ($NonInteractive -or $Yes) { return $DefaultYes }
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
  if (-not $PythonExe) { return }
  if ($PythonExe -eq "py") {
    & py -3 @PythonArgs
  } else {
    & $PythonExe @PythonArgs
  }
}
function Invoke-ServiceManager($Action) {
  if ((Test-Path (Join-Path $Repo "service_manager.py")) -and $PythonExe) {
    Invoke-Python @((Join-Path $Repo "service_manager.py"), $Action, "--base-dir", $Repo)
  }
}
function Assert-InRepo($Path) {
  $Full = [IO.Path]::GetFullPath($Path)
  $Root = [IO.Path]::GetFullPath($Repo)
  if ($Full -eq $Root -or -not $Full.StartsWith($Root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove unsafe path: $Full"
  }
  return $Full
}
function Remove-InRepo([string[]]$RelativePaths) {
  foreach ($Rel in $RelativePaths) {
    $Target = Assert-InRepo (Join-Path $Repo $Rel)
    if (Test-Path -LiteralPath $Target) {
      Remove-Item -LiteralPath $Target -Recurse -Force
      Write-Ok "Removed $Rel"
    }
  }
}
function Remove-UserPath($PathToRemove) {
  if ([string]::IsNullOrWhiteSpace($PathToRemove)) { return }
  $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ([string]::IsNullOrWhiteSpace($UserPath)) { return }
  $Expected = [IO.Path]::GetFullPath($PathToRemove).TrimEnd('\')
  $Parts = $UserPath.Split(";") | Where-Object {
    -not [string]::IsNullOrWhiteSpace($_) -and
    ([IO.Path]::GetFullPath($_).TrimEnd('\') -ne $Expected)
  }
  [Environment]::SetEnvironmentVariable("Path", ($Parts -join ";"), "User")
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
function Remove-TrinaxAIFirewallRules {
  if ($KeepFirewall) { return }
  if (-not (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue)) { return }
  foreach ($Name in @("TrinaxAI RAG API", "TrinaxAI PWA")) {
    try {
      Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    } catch {
      Write-Warn "Could not remove firewall rule $Name"
    }
  }
}
function Remove-TrinaxAICertificates {
  foreach ($Store in @("Cert:\CurrentUser\My", "Cert:\CurrentUser\Root")) {
    try {
      Get-ChildItem $Store -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -eq "TrinaxAI Local HTTPS" -or $_.Subject -eq "CN=TrinaxAI Local HTTPS" } |
        Remove-Item -Force -ErrorAction SilentlyContinue
    } catch {
      Write-Warn "Could not remove TrinaxAI certificates from $Store"
    }
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
function Stop-OllamaProcesses {
  try {
    Get-CimInstance Win32_Process |
      Where-Object { $_.CommandLine -and ($_.CommandLine -like "*ollama*") } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  } catch {
    Write-Warn "Could not enumerate Ollama processes."
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
function Remove-OllamaModelsAndState {
  $Candidates = New-Object System.Collections.Generic.List[string]
  if ($env:OLLAMA_MODELS) { $Candidates.Add($env:OLLAMA_MODELS) | Out-Null }
  if ($env:USERPROFILE) { $Candidates.Add((Join-Path $env:USERPROFILE ".ollama\models")) | Out-Null }
  if ($HOME) { $Candidates.Add((Join-Path $HOME ".ollama\models")) | Out-Null }
  if ($env:LOCALAPPDATA) { $Candidates.Add((Join-Path $env:LOCALAPPDATA "Ollama\models")) | Out-Null }
  $Seen = @{}
  foreach ($Candidate in $Candidates) {
    if ([string]::IsNullOrWhiteSpace($Candidate)) { continue }
    $Full = [IO.Path]::GetFullPath($Candidate)
    if ($Seen.ContainsKey($Full)) { continue }
    $Seen[$Full] = $true
    Remove-KnownDirectory $Full "Ollama models: $Full"
  }
}
function Invoke-OllamaRegistryUninstall {
  $Roots = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
  )
  foreach ($Root in $Roots) {
    try {
      $Apps = Get-ItemProperty $Root -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -and $_.DisplayName -match "^Ollama" }
      foreach ($App in $Apps) {
        $Command = $App.QuietUninstallString
        if (-not $Command) { $Command = $App.UninstallString }
        if (-not $Command) { continue }
        Write-Host "  Running Ollama uninstaller..."
        Invoke-ExternalWithTimeout "cmd.exe" @("/d", "/s", "/c", $Command) 120 | Out-Null
      }
    } catch {
      Write-Warn "Could not use one Ollama uninstall registry entry."
    }
  }
}
function Remove-OllamaApp {
  Stop-OllamaProcesses
  if (Test-Cmd "winget") {
    Invoke-ExternalWithTimeout "winget" @("uninstall", "--id", "Ollama.Ollama", "--silent", "--accept-source-agreements") 120 | Out-Null
  }
  Invoke-OllamaRegistryUninstall
  Stop-OllamaProcesses
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Programs\Ollama") "Ollama app"
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Ollama") "Ollama local app data"
  Remove-KnownDirectory (Join-Path $env:APPDATA "Ollama") "Ollama roaming app data"
  Remove-KnownDirectory (Join-Path $env:ProgramFiles "Ollama") "Ollama Program Files app"
}

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Repo
$PythonExe = Get-PythonExe

Write-Host ""
Write-Host "+========================================+" -ForegroundColor Blue
Write-Host "|       TrinaxAI - Clean Uninstaller     |" -ForegroundColor Blue
Write-Host "+========================================+" -ForegroundColor Blue
Write-Host " Protected: source code, indexes, and Ollama models" -ForegroundColor Cyan

if (-not ($Yes -or $NonInteractive)) {
  $Confirm = Read-Host "Type UNINSTALL to continue"
  if ($Confirm -ne "UNINSTALL") {
    Write-Warn "Cancelled."
    exit 0
  }
} elseif (-not $Yes) {
  Write-Warn "Non-interactive uninstall requires -Yes."
  exit 1
}

$StopServices = -not $KeepServices
$DisableAutostart = -not $KeepAutostart
$RemoveVenv = -not $KeepVenv
$RemoveFrontend = -not $KeepFrontend
$RemoveLogs = -not $KeepLogs
$RemoveEnv = -not $KeepEnv
$RemoveRuntimeData = $RemoveData -or $Purge
$RemoveRuntimeCerts = $RemoveCerts -or $Purge
$RemoveOllamaModels = $RemoveModels -or $RemoveOllama -or $Purge
$RemoveOllamaApp = $RemoveOllama -or $Purge
$RemoveFirewallRules = -not $KeepFirewall

if (-not ($Yes -or $NonInteractive)) {
  $StopServices = Read-YesNo "Stop running TrinaxAI services now?" $true
  $DisableAutostart = Read-YesNo "Disable TrinaxAI auto-start on boot?" $true
  $RemoveVenv = Read-YesNo "Remove Python virtual environment (.venv)?" $true
  $RemoveFrontend = Read-YesNo "Remove frontend dependencies/build?" $true
  $RemoveLogs = Read-YesNo "Remove logs?" $true
  $RemoveEnv = Read-YesNo "Remove generated .env configuration and admin token?" $true
  $RemoveRuntimeData = Read-YesNo "Remove RAG index, memory, and local_sources data?" $false
  $RemoveRuntimeCerts = Read-YesNo "Remove generated local HTTPS cert files?" $false
  $RemoveOllamaModels = Read-YesNo "Remove known Ollama models used by TrinaxAI?" $false
  $RemoveOllamaApp = Read-YesNo "Remove Ollama application too?" $false
  if ($RemoveOllamaApp) { $RemoveOllamaModels = $true }
  $RemoveFirewallRules = Read-YesNo "Remove TrinaxAI Windows Firewall rules?" $true
}

if ($StopServices) {
  Write-Step "1/4 Services"
  Invoke-ServiceManager "stop-all"
}

Write-Step "Automatic updates"
if ((Test-Path (Join-Path $Repo "scripts\auto_update.py")) -and $PythonExe) {
  Invoke-Python @((Join-Path $Repo "scripts\auto_update.py"), "disable", "--base-dir", $Repo)
} elseif (Test-Cmd "schtasks") {
  & schtasks /Delete /F /TN "TrinaxAI Weekly Update" 2>$null
}
Write-Ok "Weekly update task removed"

if ($DisableAutostart) {
  Write-Step "2/4 Autostart"
  Invoke-ServiceManager "disable-autostart"
}

Write-Step "3/4 Runtime files"
$Targets = New-Object System.Collections.Generic.List[string]
if ($RemoveVenv) { $Targets.Add(".venv") | Out-Null }
if ($RemoveFrontend) {
  $Targets.Add("chat-pwa\node_modules") | Out-Null
  $Targets.Add("chat-pwa\dist") | Out-Null
}
if ($RemoveLogs) { $Targets.Add("logs") | Out-Null }
if ($RemoveEnv) { $Targets.Add(".env") | Out-Null }
if ($RemoveRuntimeData) {
  $Targets.Add("storage") | Out-Null
  $Targets.Add("local_sources") | Out-Null
}
if ($RemoveRuntimeCerts) { $Targets.Add("chat-pwa\certs") | Out-Null }
Remove-InRepo $Targets.ToArray()
if ($RemoveVenv) {
  Remove-UserPath (Join-Path $Repo ".venv\Scripts")
  Write-Ok "Removed TrinaxAI CLI directory from the user PATH"
}

if ($RemoveFirewallRules) {
  Remove-TrinaxAIFirewallRules
}
if ($RemoveRuntimeCerts) {
  Remove-TrinaxAICertificates
}

if ($RemoveOllamaModels) {
  Write-Step "4/4 Ollama models"
  $Ollama = Get-OllamaCommand
  if ($Ollama) {
    foreach ($Model in @("qwen3:4b-instruct-2507-q4_K_M", "qwen3:30b-a3b-instruct-2507-q4_K_M", "qwen2.5-coder:1.5b", "qwen2.5-coder:3b", "qwen2.5-coder:7b", "qwen3-coder:30b", "llama3.2:1b", "bge-m3", "qwen3-vl:2b", "qwen3-vl:4b", "qwen3-vl:8b", "qwen3-vl:32b", "qwen2.5-coder:14b", "llama3.2:3b", "nomic-embed-text", "moondream", "qwen2.5vl:3b", "qwen2.5vl:7b", "llava:7b")) {
      & $Ollama rm $Model 2>$null
    }
  } else {
    Write-Warn "Ollama not found; model removal skipped."
  }
  Remove-OllamaModelsAndState
}

if ($RemoveOllamaApp) {
  Write-Step "Ollama application"
  Remove-OllamaApp
}

Write-Ok "TrinaxAI uninstall finished"
