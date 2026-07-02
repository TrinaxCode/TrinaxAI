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
function Update-ProcessPath {
  $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $ExtraPaths = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\Scripts"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\Scripts"),
    (Join-Path $env:ProgramFiles "Python312"),
    (Join-Path $env:ProgramFiles "Python312\Scripts"),
    (Join-Path $env:ProgramFiles "Python311"),
    (Join-Path $env:ProgramFiles "Python311\Scripts")
  ) | Where-Object { $_ -and (Test-Path $_) }
  $env:Path = (@($MachinePath, $UserPath) + $ExtraPaths) -join ";"
}
function Test-PythonCandidate($Exe, [string[]]$PythonArgs = @()) {
  try {
    $InvocationArgs = @($PythonArgs) + @("-c", "import sys; print(sys.executable)")
    $Output = & $Exe @InvocationArgs 2>$null
    return ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($Output | Select-Object -First 1)))
  } catch {
    return $false
  }
}
function Get-PythonCommand {
  $LocalPython312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
  $LocalPython311 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
  $ProgramPython312 = Join-Path $env:ProgramFiles "Python312\python.exe"
  $ProgramPython311 = Join-Path $env:ProgramFiles "Python311\python.exe"
  $Candidates = @(
    @{ Exe = "py"; Args = @("-3.12") },
    @{ Exe = "py"; Args = @("-3.11") },
    @{ Exe = "py"; Args = @("-3") },
    @{ Exe = $LocalPython312; Args = @() },
    @{ Exe = $LocalPython311; Args = @() },
    @{ Exe = $ProgramPython312; Args = @() },
    @{ Exe = $ProgramPython311; Args = @() },
    @{ Exe = "python"; Args = @() },
    @{ Exe = "python3"; Args = @() }
  )
  foreach ($Candidate in $Candidates) {
    if ((Test-Cmd $Candidate.Exe) -and (Test-PythonCandidate -Exe $Candidate.Exe -PythonArgs $Candidate.Args)) {
      return $Candidate
    }
  }
  return $null
}
function Invoke-Python($PythonCommand, [string[]]$PythonArgs) {
  $Exe = $PythonCommand.Exe
  $InvocationArgs = @($PythonCommand.Args) + @($PythonArgs)
  & $Exe @InvocationArgs
}
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
function Read-ModelValue($Label, $Default) {
  $Value = Read-Host "$Label [$Default]"
  if ([string]::IsNullOrWhiteSpace($Value)) { return $Default }
  return $Value.Trim()
}
function Install-WingetPackage($Id, $Name) {
  if (-not (Test-Cmd winget)) { return $false }
  if (Test-Cmd $Name) { return $true }
  Write-Host "  Installing $Id with winget..."
  winget install --id $Id --silent --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) {
    Write-Warn "winget could not install $Id automatically."
    return $false
  }
  Update-ProcessPath
  return $true
}
function Require-Command($Command, $WingetId, $InstallName, $ManualUrl) {
  if (Test-Cmd $Command) {
    Write-Ok "$InstallName found"
    return
  }
  if (Install-WingetPackage $WingetId $Command) {
    if (Test-Cmd $Command) {
      Write-Ok "$InstallName installed"
      return
    }
  }
  Write-Warn "$InstallName was not found and could not be installed automatically."
  Write-Warn "Install it manually from $ManualUrl, reopen PowerShell, and re-run install.ps1."
  exit 1
}
function Add-UserPath($PathToAdd) {
  if ([string]::IsNullOrWhiteSpace($PathToAdd) -or -not (Test-Path $PathToAdd)) { return }
  $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $Parts = @()
  if (-not [string]::IsNullOrWhiteSpace($UserPath)) {
    $Parts = $UserPath.Split(";") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  }
  if ($Parts -notcontains $PathToAdd) {
    $Next = (@($Parts) + $PathToAdd) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $Next, "User")
  }
  if (($env:Path.Split(";") | Where-Object { $_ -eq $PathToAdd }).Count -eq 0) {
    $env:Path = "$env:Path;$PathToAdd"
  }
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
function Ensure-TrinaxAICertificate($Repo, $LanIp) {
  $CertDir = Join-Path $Repo "chat-pwa\certs"
  New-Item -ItemType Directory -Force -Path $CertDir | Out-Null
  $PfxPath = Join-Path $CertDir "trinaxai-local.pfx"
  $Passphrase = "trinaxai-local"
  if (Test-Path $PfxPath) {
    Write-Ok "HTTPS certificate found"
    return
  }
  Write-Host "  Creating trusted HTTPS certificate for TrinaxAI..."
  try {
    Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.FriendlyName -eq "TrinaxAI Local HTTPS" } | Remove-Item -ErrorAction SilentlyContinue
    Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.FriendlyName -eq "TrinaxAI Local HTTPS" } | Remove-Item -ErrorAction SilentlyContinue
    $San = "2.5.29.17={text}DNS=localhost&DNS=$env:COMPUTERNAME&IPAddress=127.0.0.1&IPAddress=::1"
    if ($LanIp) { $San = "$San&IPAddress=$LanIp" }
    $Cert = New-SelfSignedCertificate `
      -Subject "CN=TrinaxAI Local HTTPS" `
      -FriendlyName "TrinaxAI Local HTTPS" `
      -CertStoreLocation "Cert:\CurrentUser\My" `
      -KeyAlgorithm RSA `
      -KeyLength 2048 `
      -HashAlgorithm SHA256 `
      -KeyExportPolicy Exportable `
      -NotAfter (Get-Date).AddYears(5) `
      -TextExtension @($San)
    $RootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
    $RootStore.Open("ReadWrite")
    $RootStore.Add($Cert)
    $RootStore.Close()
    $SecurePass = ConvertTo-SecureString -String $Passphrase -Force -AsPlainText
    Export-PfxCertificate -Cert $Cert -FilePath $PfxPath -Password $SecurePass | Out-Null
    Write-Ok "Trusted HTTPS certificate installed"
  } catch {
    Write-Warn "Could not create a trusted HTTPS certificate automatically: $($_.Exception.Message)"
    Write-Warn "TrinaxAI will still run, but your browser may show 'Not secure' until you trust a local certificate."
  }
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

$ModelGeneral = "llama3.2:3b"
$ModelCode = "qwen2.5-coder:3b"
$ModelDeep = "qwen2.5-coder:3b"
$ModelFast = "llama3.2:3b"
$EmbedPreset = "balanced"
$EmbedModel = "bge-m3"
$EmbedDims = "1024"
$EmbedBatch = "8"
$EmbedKeepAlive = "15m"
$VisionModel = "qwen2.5vl:3b"
$VisionQualityModel = "qwen2.5vl:7b"
if ($Profile -eq "8gb") {
  $EmbedBatch = "2"
  $EmbedKeepAlive = "10m"
} elseif ($Profile -eq "max") {
  $ModelDeep = "qwen2.5-coder:7b"
  $VisionModel = "qwen2.5vl:7b"
  $EmbedKeepAlive = "30m"
} elseif ($Profile -eq "ultra") {
  $ModelDeep = "qwen2.5-coder:14b"
  $VisionModel = "qwen2.5vl:7b"
  $EmbedBatch = "16"
  $EmbedKeepAlive = "30m"
}

Write-Host ""
Write-Host "Model roles TrinaxAI needs:" -ForegroundColor Cyan
Write-Host "  General chat: conversation and everyday questions"
Write-Host "  Code/deep: code, reasoning, refactors, project analysis"
Write-Host "  Embeddings: RAG indexing and semantic search"
Write-Host "  Vision: image and screenshot analysis"
if (-not $NonInteractive) {
  $ModelMode = Read-Host "Use recommended Ollama models, or configure your own? [R/o]"
  if ($ModelMode -match "^[Oo]") {
    $ModelGeneral = Read-ModelValue "General chat model" $ModelGeneral
    $ModelCode = Read-ModelValue "Code model" $ModelCode
    $ModelDeep = Read-ModelValue "Deep analysis model" $ModelDeep
    $ModelFast = Read-ModelValue "Fast model" $ModelFast
    $EmbedModel = Read-ModelValue "Embedding model for RAG" $EmbedModel
    $VisionModel = Read-ModelValue "Vision/image model" $VisionModel
    $VisionQualityModel = Read-ModelValue "High-quality vision model" $VisionQualityModel
  }
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
  "TRINAXAI_HEALTH_URL=http://localhost:3333",
  "TRINAXAI_FRONTEND_URL=https://localhost:3334",
  "TRINAXAI_FRONTEND_MODE=preview",
  "TRINAXAI_CERT_PASSPHRASE=trinaxai-local",
  "TRINAXAI_RAG_TARGET=http://127.0.0.1:3333",
  "VITE_TRINAXAI_RAG_TARGET=http://127.0.0.1:3333",
  "OLLAMA_BASE_URL=http://localhost:11434",
  "TRINAXAI_MODEL_GENERAL=$ModelGeneral",
  "TRINAXAI_MODEL_CODE=$ModelCode",
  "TRINAXAI_MODEL_DEEP=$ModelDeep",
  "TRINAXAI_MODEL_FAST=$ModelFast",
  "TRINAXAI_AUTO_ROUTE=1",
  "TRINAXAI_EMBED_PRESET=$EmbedPreset",
  "TRINAXAI_EMBED=$EmbedModel",
  "TRINAXAI_EMBED_DIMS=$EmbedDims",
  "TRINAXAI_EMBED_BATCH=$EmbedBatch",
  "TRINAXAI_EMBED_KEEP_ALIVE=$EmbedKeepAlive",
  "VITE_TRINAXAI_VISION_MODEL=$VisionModel",
  "VITE_TRINAXAI_VISION_QUALITY_MODEL=$VisionQualityModel",
  "TRINAXAI_RERANK=0",
  "TRINAXAI_ALLOW_LAN_SYSTEM=$EnableLanSystem",
  "TRINAXAI_ADMIN_TOKEN=$AdminToken",
  "TRINAXAI_CORS_ORIGINS=$Cors",
  "TRINAXAI_INDEX_DIR=$($env:USERPROFILE)\Documents"
)
if ($Profile -eq "ultra") {
  $EnvLines += @(
    "TRINAXAI_NUM_CTX=16384",
    "TRINAXAI_EMBED_WORKERS=6"
  )
} elseif ($Profile -eq "max") {
  $EnvLines += @(
    "TRINAXAI_NUM_CTX=8192",
    "TRINAXAI_EMBED_WORKERS=4"
  )
}
$EnvLines | Set-Content -Encoding UTF8 ".env"
Write-Ok ".env written with profile=$Profile"

Write-Step "2/6 Dependencies"
Update-ProcessPath
if (Test-Cmd winget) {
  $PythonCommand = Get-PythonCommand
  if ($null -eq $PythonCommand) {
    Write-Host "  Installing Python.Python.3.12 with winget..."
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
      Write-Warn "winget could not install Python automatically."
      Write-Warn "Install Python 3.12 from https://python.org, reopen PowerShell, and re-run install.ps1."
      exit 1
    }
    Update-ProcessPath
    $PythonCommand = Get-PythonCommand
  }
} else {
  Write-Warn "winget was not found. Automatic dependency installation is not available on this Windows image."
  $PythonCommand = Get-PythonCommand
}
if ($null -eq $PythonCommand) {
  Write-Warn "Python 3.10+ was not found or only the Microsoft Store alias is available."
  Write-Warn "Install Python from winget/python.org, reopen PowerShell, and re-run this script."
  Write-Warn "Recommended command:"
  Write-Warn "  winget install --id Python.Python.3.12 --source winget"
  exit 1
} else {
  $PythonExe = Invoke-Python -PythonCommand $PythonCommand -PythonArgs @("-c", "import sys; print(sys.executable)")
  Write-Ok "Python found: $($PythonExe | Select-Object -First 1)"
}
Require-Command "git" "Git.Git" "Git" "https://git-scm.com/download/win"
Require-Command "node" "OpenJS.NodeJS.LTS" "Node.js" "https://nodejs.org"
Require-Command "ollama" "Ollama.Ollama" "Ollama" "https://ollama.com/download/windows"

Ensure-TrinaxAICertificate -Repo $Repo -LanIp $LanIp

$FreeGb = [math]::Round((Get-PSDrive -Name ((Get-Location).Path.Substring(0,1))).Free / 1GB)
if ($FreeGb -lt 12) {
  Write-Warn "Only $FreeGb GB free on this drive. Model downloads may fail."
}

Write-Step "3/6 Python environment"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  if (Test-Path ".venv") {
    Write-Warn "Existing .venv is incomplete. Recreating it."
    Remove-Item -Recurse -Force ".venv"
  }
  Invoke-Python -PythonCommand $PythonCommand -PythonArgs @("-m", "venv", ".venv")
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Warn "Could not create .venv\Scripts\python.exe. Reopen PowerShell after Python installation and re-run install.ps1."
  exit 1
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" -m pip install -e .
$VenvScripts = Join-Path $Repo ".venv\Scripts"
Add-UserPath $VenvScripts
Write-Ok "Python packages installed"
Write-Ok "TrinaxAI CLI installed: .\.venv\Scripts\trinaxai.exe"
Write-Ok "CLI path configured for this user: $VenvScripts"

Write-Step "4/6 PWA frontend"
if ((Test-Cmd npm) -and (Test-Path "chat-pwa")) {
  Push-Location "chat-pwa"
  npm install
  npm run build
  Pop-Location
  Write-Ok "PWA ready"
}

Write-Step "5/6 AI models"
$Models = @($ModelCode, $ModelDeep, $ModelGeneral, $ModelFast, $EmbedModel) |
  Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
  Select-Object -Unique
Write-Host "  General chat: $ModelGeneral"
Write-Host "  Code:         $ModelCode"
Write-Host "  Deep:         $ModelDeep"
Write-Host "  Embeddings:   $EmbedModel"
Write-Host "  Vision:       $VisionModel"
if (-not $NonInteractive) {
  $SkipModels = Read-Host "Download these Ollama models now? Choose N if you already have your own. [Y/n]"
  if ($SkipModels -match "^[Nn]") {
    $NoModels = $true
    Write-Warn "Model download skipped. The configured model names were still saved to .env."
  }
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
