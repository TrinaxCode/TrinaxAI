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
  [switch]$KeepFirewall
)

<# 
TrinaxAI - Windows uninstaller
Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
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

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Repo
$PythonExe = Get-PythonExe

Write-Host ""
Write-Host "==========================================" -ForegroundColor Blue
Write-Host " TrinaxAI - Windows uninstaller          " -ForegroundColor Blue
Write-Host "==========================================" -ForegroundColor Blue
Write-Host "Repository/source code will stay in place." -ForegroundColor Cyan

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
$RemoveRuntimeData = $RemoveData
$RemoveRuntimeCerts = $RemoveCerts
$RemoveOllamaModels = $RemoveModels
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
  $RemoveFirewallRules = Read-YesNo "Remove TrinaxAI Windows Firewall rules?" $true
}

if ($StopServices) {
  Write-Step "1/4 Services"
  Invoke-ServiceManager "stop-all"
}

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

if ($RemoveFirewallRules) {
  Remove-TrinaxAIFirewallRules
}

if ($RemoveOllamaModels) {
  Write-Step "4/4 Ollama models"
  $Ollama = Get-OllamaCommand
  if ($Ollama) {
    foreach ($Model in @("llama3.2:1b", "llama3.2:3b", "qwen2.5-coder:1.5b", "qwen2.5-coder:3b", "qwen2.5-coder:7b", "qwen2.5-coder:14b", "nomic-embed-text", "bge-m3", "moondream", "qwen2.5vl:3b", "qwen2.5vl:7b")) {
      & $Ollama rm $Model 2>$null
    }
  } else {
    Write-Warn "Ollama not found; model removal skipped."
  }
}

Write-Ok "TrinaxAI uninstall finished"
