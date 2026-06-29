param(
  [switch]$Interactive,
  [switch]$NonInteractive,
  [switch]$NoModels,
  [switch]$NoVision,
  [switch]$NoAutostart,
  [switch]$NoStart,
  [switch]$LanSystem,
  [ValidateSet("8gb", "16gb", "max", "ultra")]
  [string]$Profile = ""
)

<# 
TrinaxAI - Windows one-command installer
Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File .\install.ps1
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -Interactive
#>

$ErrorActionPreference = "Stop"

function Write-Step($Text) { Write-Host "`n=== $Text ===`n" -ForegroundColor Blue }
function Write-Ok($Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn($Text) { Write-Host "  [!] $Text" -ForegroundColor Yellow }
function Test-Cmd($Name) { return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }
function Normalize-Profile($Value, $Fallback) {
  $Text = ""
  if ($null -ne $Value) { $Text = [string]$Value }
  switch ($Text.ToLowerInvariant()) {
    "8gb" { return "8gb" }
    "low" { return "8gb" }
    "lite" { return "8gb" }
    "16gb" { return "16gb" }
    "medium" { return "16gb" }
    "normal" { return "16gb" }
    "max" { return "max" }
    "high" { return "max" }
    "ultra" { return "ultra" }
    default { return $Fallback }
  }
}
function Install-WingetPackage($Id, $Name) {
  if (-not (Test-Cmd winget)) { return }
  if (Test-Cmd $Name) { return }
  Write-Host "  Installing $Id with winget..."
  winget install --id $Id --silent --accept-package-agreements --accept-source-agreements
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
  if (-not (Test-Cmd ollama)) { return $false }
  if (Test-OllamaReady) { return $true }
  Write-Host "  Starting Ollama..."
  try {
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden | Out-Null
  } catch {
    return $false
  }
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    if (Test-OllamaReady) { return $true }
  }
  return $false
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Blue
Write-Host " TrinaxAI - Local AI Assistant for Windows " -ForegroundColor Blue
Write-Host "==========================================" -ForegroundColor Blue
Write-Host " Privacy: 100% local. Nothing leaves your machine." -ForegroundColor Cyan

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Repo

$RamGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$AutoProfile = if ($RamGb -ge 32) { "ultra" } elseif ($RamGb -ge 20) { "max" } elseif ($RamGb -le 8) { "8gb" } else { "16gb" }
if (-not $Profile) { $Profile = if ($env:TRINAXAI_PROFILE) { $env:TRINAXAI_PROFILE } else { $AutoProfile } }
$Profile = Normalize-Profile $Profile $AutoProfile

Write-Step "1/6 Hardware profile"
Write-Host "  Detected RAM: $RamGb GB" -ForegroundColor Cyan
Write-Host "  Recommended profile: $AutoProfile" -ForegroundColor Green
Write-Host ""
$Mode = ""
if ($Interactive) { $Mode = Read-Host "Setup mode: Normal recommended or Advanced manual? [N/a]" }
if ($Interactive -and $Mode -match "^[Aa]") {
  Write-Host "  1) medium  Balanced default (about 16GB RAM)"
  Write-Host "  2) high    Stronger CPU / more RAM"
  Write-Host "  3) ultra   32GB+ RAM + powerful GPU"
  Write-Host "  4) low     Low memory (about 8GB RAM)"
  $Choice = Read-Host "Choose profile [default: $Profile]"
  switch ($Choice) {
    "1" { $Profile = "16gb" }
    "medium" { $Profile = "16gb" }
    "2" { $Profile = "max" }
    "high" { $Profile = "max" }
    "3" { $Profile = "ultra" }
    "4" { $Profile = "8gb" }
    "low" { $Profile = "8gb" }
  }
} else {
  Write-Ok "Automatic setup selected: profile=$Profile"
}

$LanIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -match "^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[0-1]))" } |
  Select-Object -First 1 -ExpandProperty IPAddress)

$EnableLanSystem = if ($env:TRINAXAI_ALLOW_LAN_SYSTEM) {
  [int]$env:TRINAXAI_ALLOW_LAN_SYSTEM
} elseif ($LanSystem) {
  1
} else {
  0
}
$AdminToken = $env:TRINAXAI_ADMIN_TOKEN

if ($EnableLanSystem -ne 1) {
  Write-Host ""
  Write-Host "Security option: LAN system control" -ForegroundColor Yellow
  Write-Host "This allows devices on your local network to call sensitive system endpoints"
  Write-Host "(shutdown, startup, reload, indexing, file watchers, collection management)."
  Write-Host "Only enable this if you trust your local network and use a strong admin token."
  if ($Interactive) {
    $Reply = Read-Host "Enable LAN system control? [y/N]"
  } else {
    Write-Host "  Default: disabled. Use -LanSystem to enable non-interactively, or answer below." -ForegroundColor Cyan
    $Reply = Read-Host "Enable LAN system control? [y/N]"
  }
  if ($Reply -match "^[Yy]") { $EnableLanSystem = 1 } else { $EnableLanSystem = 0 }
}

if ($EnableLanSystem -eq 1 -and [string]::IsNullOrWhiteSpace($AdminToken)) {
  $TokenBytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($TokenBytes)
  $AdminToken = [BitConverter]::ToString($TokenBytes) -replace '-','' | ForEach-Object { $_.ToLower() }
  if ([string]::IsNullOrWhiteSpace($AdminToken)) {
    Write-Host "Could not generate admin token. Ensure .NET cryptography is available." -ForegroundColor Red
    exit 1
  }
  Write-Ok "Admin token generated and saved to .env"
}

$Cors = "https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334,https://localhost:3335,http://localhost:3335,https://127.0.0.1:3335,http://127.0.0.1:3335"
if ($LanIp) { $Cors += ",https://$($LanIp):3334,http://$($LanIp):3334,https://$($LanIp):3335,http://$($LanIp):3335" }

$EnvLines = @(
  "# TrinaxAI generated configuration",
  "TRINAXAI_PROFILE=$Profile",
  "TRINAXAI_HOST=0.0.0.0",
  "TRINAXAI_PORT=3333",
  "OLLAMA_BASE_URL=http://localhost:11434",
  "TRINAXAI_MODEL_GENERAL=llama3.2:3b",
  "TRINAXAI_MODEL_CODE=qwen2.5-coder:3b",
  "TRINAXAI_MODEL_DEEP=qwen2.5-coder:3b",
  "TRINAXAI_MODEL_FAST=llama3.2:3b",
  "TRINAXAI_AUTO_ROUTE=1",
  "TRINAXAI_EMBED_PRESET=balanced",
  "TRINAXAI_EMBED=bge-m3",
  "TRINAXAI_EMBED_DIMS=1024",
  "TRINAXAI_RERANK=0",
  "TRINAXAI_ALLOW_LAN_SYSTEM=$EnableLanSystem",
  "TRINAXAI_ADMIN_TOKEN=$AdminToken",
  "TRINAXAI_CORS_ORIGINS=$Cors",
  "TRINAXAI_INDEX_DIR=$($env:USERPROFILE)\Documents"
)
if ($Profile -eq "ultra") {
  $EnvLines += @(
    "TRINAXAI_NUM_CTX=16384",
    "TRINAXAI_EMBED_WORKERS=6",
    "TRINAXAI_MODEL_DEEP=qwen2.5-coder:14b",
    "VITE_TRINAXAI_VISION_QUALITY_MODEL=qwen2.5vl:7b"
  )
} elseif ($Profile -eq "max") {
  $EnvLines += @(
    "TRINAXAI_NUM_CTX=8192",
    "TRINAXAI_EMBED_WORKERS=4",
    "TRINAXAI_MODEL_DEEP=qwen2.5-coder:7b"
  )
}
$EnvLines | Set-Content -Encoding UTF8 ".env"
Write-Ok ".env written with profile=$Profile"

Write-Step "2/6 Dependencies"
if (Test-Cmd winget) {
  Install-WingetPackage "Python.Python.3.12" "python"
  Install-WingetPackage "Git.Git" "git"
  Install-WingetPackage "OpenJS.NodeJS.LTS" "node"
  Install-WingetPackage "Ollama.Ollama" "ollama"
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
if (-not (Test-Cmd python)) {
  Write-Warn "Python was not found. Install Python 3.10+ from https://python.org and re-run this script."
  exit 1
} else {
  Write-Ok "Python found"
}

$FreeGb = [math]::Round((Get-PSDrive -Name ((Get-Location).Path.Substring(0,1))).Free / 1GB)
if ($FreeGb -lt 12) {
  Write-Warn "Only $FreeGb GB free on this drive. Model downloads may fail."
}
if (-not (Test-Cmd node)) {
  Write-Warn "Node.js was not found. Install Node.js 18+ from https://nodejs.org and re-run this script."
  exit 1
} else {
  Write-Ok "Node.js found"
}
if (-not (Test-Cmd ollama)) {
  Write-Warn "Ollama was not found. Download it from https://ollama.com/download/windows, start Ollama, then re-run this script."
  exit 1
} else {
  Write-Ok "Ollama found"
}

Write-Step "3/6 Python environment"
if (Test-Cmd python) {
  if (-not (Test-Path ".venv")) { python -m venv .venv }
  & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
  & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
  & ".\.venv\Scripts\python.exe" -m pip install -e .
  Write-Ok "Python packages installed"
  Write-Ok "TrinaxAI CLI installed: .\.venv\Scripts\trinaxai.exe"
  Write-Warn "If 'trinaxai' is not available globally, run it from this shell after activating .\.venv\Scripts\Activate.ps1 or add .\.venv\Scripts to PATH."
}

Write-Step "4/6 PWA frontend"
if ((Test-Cmd npm) -and (Test-Path "chat-pwa")) {
  Push-Location "chat-pwa"
  npm install
  npm run build
  Pop-Location
  Write-Ok "PWA ready"
}

Write-Step "5/6 AI models"
$Models = @("qwen2.5-coder:3b", "llama3.2:3b", "bge-m3")
$VisionModel = "qwen2.5vl:3b"
if (($Profile -eq "max") -or ($Profile -eq "ultra")) {
  $Models += "qwen2.5-coder:7b"
  $VisionModel = "qwen2.5vl:7b"
}
if ($Profile -eq "ultra") { $Models += "qwen2.5-coder:14b" }
if ($Interactive) {
  $SkipModels = Read-Host "Download default models now? [Y/n]"
  if ($SkipModels -match "^[Nn]") { $NoModels = $true }
  if (-not $NoModels) {
    $SkipVision = Read-Host "Download vision model ($VisionModel)? [Y/n]"
    if ($SkipVision -match "^[Nn]") { $NoVision = $true }
  }
}
if (-not $NoModels -and (Ensure-OllamaRunning)) {
  foreach ($Model in $Models) {
    Write-Host "  Pulling $Model..."
    ollama pull $Model
  }
  if (-not $NoVision) {
    Write-Host "  Pulling $VisionModel..."
    ollama pull $VisionModel
  }
  Write-Ok "Models ready"
} elseif ($NoModels) {
  Write-Warn "Model download skipped by flag."
} else {
  Write-Warn "Ollama did not start; skipping model downloads. TrinaxAI is installed, but models must be pulled later."
}

Write-Step "6/6 Start"
if (-not $NoStart) {
  & ".\.venv\Scripts\python.exe" "service_manager.py" "start" "--base-dir" $Repo
  Write-Ok "TrinaxAI started"
}
if ($Interactive) {
  $AutoStart = Read-Host "Start TrinaxAI automatically when Windows starts? [Y/n]"
  if ($AutoStart -match "^[Nn]") { $NoAutostart = $true }
}
if (-not $NoAutostart) {
  & ".\.venv\Scripts\python.exe" "service_manager.py" "enable-autostart" "--base-dir" $Repo
  Write-Ok "Auto-start enabled"
}
Write-Host "Then open:" -ForegroundColor Cyan
Write-Host "  https://localhost:3334"
Write-Host "CLI:" -ForegroundColor Cyan
Write-Host "  trinaxai"
if ($LanIp) { Write-Host "  https://$($LanIp):3334" }
Write-Host ""
if ($EnableLanSystem -eq 1) {
  Write-Host "  LAN system control: enabled" -ForegroundColor Yellow
  Write-Host "  Admin token: saved in .env (TRINAXAI_ADMIN_TOKEN)" -ForegroundColor Yellow
} else {
  Write-Host "  LAN system control: disabled by default" -ForegroundColor Yellow
  Write-Host "  To enable later: set TRINAXAI_ALLOW_LAN_SYSTEM=1 and TRINAXAI_ADMIN_TOKEN in .env" -ForegroundColor Yellow
}
Write-Host ""
Write-Ok "TrinaxAI setup finished"
