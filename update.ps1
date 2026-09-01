param(
  [switch]$Interactive,
  [switch]$NonInteractive,
  [switch]$NoBackup,
  [switch]$NoPull,
  [switch]$Models,
  [switch]$NoModels,
  [switch]$Restart,
  [switch]$NoRestart,
  [switch]$DryRun,
  [switch]$EnableAutostart,
  [switch]$DisableAutostart,
  [switch]$RepairOllama,
  [switch]$RemoveModels,
  [switch]$RemoveOllama,
  [switch]$NoAudit,
  [switch]$Scheduled,
  [ValidateSet("en", "es")]
  [string]$Language = "",
  [string]$RepoRoot = ""
)

<# 
TrinaxAI - Windows updater
Run in PowerShell:
  powershell -ExecutionPolicy Bypass -File .\update.ps1

Guided mode asks what to update or repair, including Ollama reinstall/removal,
model removal/download, backup, source download, autostart, restart, and audit.
#>

$ErrorActionPreference = "Stop"
$LanguageExplicit = -not [string]::IsNullOrWhiteSpace($Language) -or -not [string]::IsNullOrWhiteSpace($env:TRINAXAI_LANG)
if ([string]::IsNullOrWhiteSpace($Language)) { $Language = if ($env:TRINAXAI_LANG -match '^es') { 'es' } elseif ((Get-Culture).Name -match '^es') { 'es' } else { 'en' } }
function T($English, $Spanish) { if ($Language -eq 'es') { return $Spanish }; return $English }

$ReleaseVersion = if (-not [string]::IsNullOrWhiteSpace($env:TRINAXAI_RELEASE_VERSION)) { $env:TRINAXAI_RELEASE_VERSION } else { "" }
if ($ReleaseVersion -and $ReleaseVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Invalid TrinaxAI release version: $ReleaseVersion" }
$SourceUpdateUrl = if (-not [string]::IsNullOrWhiteSpace($env:TRINAXAI_UPDATE_SOURCE_URL)) { $env:TRINAXAI_UPDATE_SOURCE_URL } else { "" }
$SourceUpdateSha256 = if (-not [string]::IsNullOrWhiteSpace($env:TRINAXAI_UPDATE_SOURCE_SHA256)) { $env:TRINAXAI_UPDATE_SOURCE_SHA256 } else { $env:TRINAXAI_SOURCE_SHA256 }
if ($SourceUpdateSha256) { $SourceUpdateSha256 = $SourceUpdateSha256.Trim() }
if ($SourceUpdateSha256 -and $SourceUpdateSha256 -notmatch '^[0-9a-fA-F]{64}$') {
  throw "Source archive checksum must be a SHA-256 digest."
}
if ([string]::IsNullOrWhiteSpace($SourceUpdateUrl) -and $ReleaseVersion) {
  $SourceUpdateUrl = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$ReleaseVersion/TrinaxAI-$ReleaseVersion.tar.gz"
}
$IsReleaseSourceUrl = $SourceUpdateUrl -match '^https://github\.com/TrinaxCode/TrinaxAI/releases/download/v[0-9]+\.[0-9]+\.[0-9]+/TrinaxAI-[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz$'
if ($SourceUpdateUrl -and -not $IsReleaseSourceUrl -and [string]::IsNullOrWhiteSpace($SourceUpdateSha256)) {
  throw "TRINAXAI_UPDATE_SOURCE_URL requires a matching SHA-256 checksum."
}

if (-not $Interactive -and -not $NonInteractive -and -not $DryRun -and -not $Scheduled -and $env:TRINAXAI_INTERACTIVE -ne "0") {
  $Interactive = $true
}

if (-not $LanguageExplicit -and -not $NonInteractive -and -not $DryRun -and -not $Scheduled) {
  $Reply = Read-Host "Select language / Selecciona idioma [en/es, default: $Language]"
  if ($Reply -match '^es') { $Language = 'es' } elseif ($Reply -match '^en') { $Language = 'en' }
}

function Write-Step($Text) { Write-Host "`n  +-- $Text" -ForegroundColor Blue }
function Write-Ok($Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Warn($Text) { Write-Host "  [!] $Text" -ForegroundColor Yellow }
function Write-Info($Text) { Write-Host "  [>] $Text" -ForegroundColor Cyan }
function Test-Cmd($Name) { return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue) }
function Update-ProcessPath {
  $MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $ExtraPaths = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama"),
    (Join-Path $env:ProgramFiles "Ollama")
  ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
  $env:Path = (@($MachinePath, $UserPath) + $ExtraPaths) -join ";"
}
function Invoke-NativeChecked([string]$FilePath, [string[]]$Arguments, [string]$Label) {
  & $FilePath @Arguments
  $ExitCode = $LASTEXITCODE
  if ($ExitCode -ne 0) {
    throw "$Label failed with exit code $ExitCode."
  }
}
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
  $ExitCode = $LASTEXITCODE
  if ($ExitCode -ne 0) {
    throw "Python command failed with exit code ${ExitCode}: $PythonExe $($PythonArgs -join ' ')"
  }
}
function Get-OllamaCommand {
  Update-ProcessPath
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
function Test-OllamaModel([string]$OllamaExe, [string]$Model) {
  try {
    $Rows = @(& $OllamaExe list 2>$null)
    if ($LASTEXITCODE -ne 0) { return $false }
    $Pattern = "^\s*$([regex]::Escape($Model))(\s|$)"
    return [bool]($Rows | Where-Object { $_ -match $Pattern })
  } catch {
    return $false
  }
}
function Invoke-LocalWebRequest([string]$Uri, [string]$Method = "GET", [string]$Body = "") {
  $Params = @{
    Uri = $Uri
    Method = $Method
    UseBasicParsing = $true
    TimeoutSec = 5
    ErrorAction = "Stop"
  }
  if ($Body) {
    $Params.Body = $Body
    $Params.ContentType = "application/json"
  }
  $Command = Get-Command Invoke-WebRequest
  if ($Command.Parameters.ContainsKey("SkipCertificateCheck")) {
    $Params.SkipCertificateCheck = $true
    return Invoke-WebRequest @Params
  }
  $OriginalCallback = [Net.ServicePointManager]::ServerCertificateValidationCallback
  try {
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    return Invoke-WebRequest @Params
  } finally {
    [Net.ServicePointManager]::ServerCertificateValidationCallback = $OriginalCallback
  }
}
function Wait-LocalUrl([int]$Port, [string]$Path = "/") {
  foreach ($Scheme in @("https", "http")) {
    $Uri = "${Scheme}://127.0.0.1:${Port}${Path}"
    for ($i = 0; $i -lt 20; $i++) {
      try {
        Invoke-LocalWebRequest $Uri | Out-Null
        return "${Scheme}://127.0.0.1:${Port}"
      } catch {
        Start-Sleep -Seconds 1
      }
    }
  }
  return ""
}
function Assert-RuntimeReady {
  $RagPortText = if ($env:TRINAXAI_PORT) { $env:TRINAXAI_PORT } else { Read-EnvValue "TRINAXAI_PORT" }
  $PwaPortText = if ($env:TRINAXAI_PWA_PORT) { $env:TRINAXAI_PWA_PORT } else { Read-EnvValue "TRINAXAI_PWA_PORT" }
  $RagPort = if ($RagPortText) { [int]$RagPortText } else { 3333 }
  $PwaPort = if ($PwaPortText) { [int]$PwaPortText } else { 3334 }
  $RagBase = Wait-LocalUrl $RagPort "/health"
  if (-not $RagBase) { throw "TrinaxAI backend is not ready on port $RagPort." }
  $PwaBase = Wait-LocalUrl $PwaPort
  if (-not $PwaBase) { throw "TrinaxAI PWA is not ready on port $PwaPort." }
  $Body = @{ messages = @(@{ role = "user"; content = "Reply with the single word OK." }); stream = $false; mode = "model"; think = $false } | ConvertTo-Json -Compress
  try {
    $Response = Invoke-LocalWebRequest "$RagBase/v1/chat/completions" "POST" $Body
    $Payload = $Response.Content | ConvertFrom-Json
    $Content = $Payload.choices[0].message.content
    if ([string]::IsNullOrWhiteSpace([string]$Content)) { throw "empty response" }
  } catch {
    throw "TrinaxAI smoke inference failed: $($_.Exception.Message)"
  }
  Write-Ok "Backend, PWA, and smoke inference are ready"
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
    if (-not (Invoke-ExternalWithTimeout $PowerShellExe @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command) 90)) {
      return $false
    }
    Update-ProcessPath
    return [bool](Get-OllamaCommand)
  } catch {
    Write-Warn "Official Ollama install command failed: $($_.Exception.Message)"
    return $false
  }
}
function Remove-KnownDirectory([string]$Path, [string]$Label) {
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  try {
    if ($Path -notmatch '^(?:[A-Za-z]:[\\/]|\\\\)') { throw "Unsafe path: $Path" }
    $Full = [IO.Path]::GetFullPath($Path)
    if ($Full -eq [IO.Path]::GetPathRoot($Full)) { throw "Unsafe path: $Full" }
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
    if (-not (Invoke-ExternalWithTimeout "winget" @("uninstall", "--id", "Ollama.Ollama", "--silent", "--accept-source-agreements") 120)) {
      Write-Warn "winget could not remove the Ollama package; continuing with known application paths."
    }
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
  if ($List.Count -eq 0) {
    foreach ($Model in @("qwen3.5:2b", "qwen3.5:4b", "qwen3-embedding:0.6b", "qwen3-embedding:4b")) {
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
      if ($LASTEXITCODE -ne 0) { Write-Warn "Could not remove configured model $Model." }
    }
  }
}
function New-TrinaxAIBackup {
  $BackupDir = Join-Path $Repo "backups"
  New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
  if (Test-Cmd "icacls") {
    & icacls $BackupDir /inheritance:r /grant:r "${env:USERNAME}:(OI)(CI)F" | Out-Null
  }
  $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $ZipPath = Join-Path $BackupDir "trinaxai-backup-$Stamp.zip"
  $Items = @(".env", "storage", "local_sources", "chat-pwa\certs", "logs") |
    Where-Object { Test-Path (Join-Path $Repo $_) } |
    ForEach-Object { Join-Path $Repo $_ }
  if ($Items.Count -eq 0) {
    Write-Warn "No runtime files found to back up."
    return
  }

  if (-not $PythonExe) { throw "Python is required to pause services before backup." }
  $Status = Get-TrinaxAIServiceStatus
  $ApiWasRunning = Test-TrinaxAIRagApiRunning $Status
  try {
    if ($ApiWasRunning) {
      Invoke-ServiceManager "stop-ai"
      if (Test-TrinaxAIRagApiRunning (Get-TrinaxAIServiceStatus)) {
        throw "The TrinaxAI RAG API is still running; backup was not created."
      }
    }
    Compress-Archive -Path $Items -DestinationPath $ZipPath -Force
    if (Test-Cmd "icacls") {
      & icacls $ZipPath /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
    }
    Write-Ok "Backup created: $ZipPath"
  } finally {
    if ($ApiWasRunning) {
      Invoke-ServiceManager "start-ai"
      if (-not (Test-TrinaxAIRagApiRunning (Get-TrinaxAIServiceStatus))) {
        throw "The TrinaxAI RAG API could not be restored after backup."
      }
    }
  }
}
function Invoke-ServiceManager($Action) {
  if (-not $PythonExe) { Write-Warn "Python not found; skipped service_manager $Action."; return }
  Invoke-Python @((Join-Path $Repo "service_manager.py"), $Action, "--base-dir", $Repo)
}
function Get-TrinaxAIServiceStatus {
  $Output = @(Invoke-Python @((Join-Path $Repo "service_manager.py"), "status", "--json", "--base-dir", $Repo) 2>$null)
  if ($Output.Count -eq 0) { throw "The service manager returned no status." }
  try {
    return (($Output -join [Environment]::NewLine) | ConvertFrom-Json)
  } catch {
    throw "The service manager returned invalid status JSON: $($_.Exception.Message)"
  }
}
function Test-TrinaxAIRagApiRunning($Status) {
  $Api = @($Status | Where-Object { $_.name -eq "rag_api" } | Select-Object -First 1)
  return $Api.Count -eq 1 -and [bool]$Api[0].running
}

function Sync-TrinaxRepository {
  if (-not (Test-Path -LiteralPath (Join-Path $Repo ".trinaxai-managed") -PathType Leaf)) {
    throw "This is not a managed TrinaxAI installation; source update stopped safely."
  }
  if (-not (Test-Path -LiteralPath (Join-Path $Repo "scripts\source_update.py") -PathType Leaf)) {
    throw "The safe source updater is missing; source update stopped safely."
  }
  Write-Info "Downloading the latest TrinaxAI source package from GitHub..."
  $SourceArgs = @((Join-Path $Repo "scripts\source_update.py"), "update", "--root", $Repo)
  if ($SourceUpdateUrl) { $SourceArgs += @("--url", $SourceUpdateUrl) }
  if ($SourceUpdateSha256) { $SourceArgs += @("--sha256", $SourceUpdateSha256) }
  Invoke-Python $SourceArgs
  $script:RollbackActive = $true
  Write-Ok "Source package updated"
}

function Restore-FailedUpdate {
  if (-not $script:RollbackActive) { return }
  Write-Warn "Update failed; restoring the previously working source tree."
  try {
    Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "rollback", "--root", $Repo)
  } catch {
    Write-Warn "Automatic source rollback failed: $($_.Exception.Message)"
  }
}

$Repo = if ($RepoRoot) { [IO.Path]::GetFullPath($RepoRoot) } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location $Repo

if ($DryRun) {
  Write-Host (T "DRY-RUN: nothing will be downloaded, installed, or changed." "SIMULACIÓN: no se descargará, instalará ni modificará nada.") -ForegroundColor Yellow
  Write-Step (T "Source Code" "Código fuente")
  Write-Info (T "Would download the latest source package from GitHub" "Se descargaría el paquete fuente más reciente desde GitHub")
  Write-Step (T "Backup" "Copia de seguridad")
  Write-Info (T "Would create a backup of runtime configuration and data" "Se crearía una copia de la configuración y los datos de ejecución")
  Write-Step (T "Python Dependencies" "Dependencias de Python")
  Write-Info (T "Would refresh pip, requirements, and the editable CLI" "Se actualizarían pip, requirements y la CLI editable")
  Write-Step (T "Web App" "Aplicación web")
  Write-Info (T "Would run npm ci and npm run build" "Se ejecutarían npm ci y npm run build")
  Write-Step (T "Ollama Models" "Modelos de Ollama")
  Write-Info (T "Would check Ollama and pull configured models if requested" "Se comprobaría Ollama y se descargarían los modelos configurados si se solicita")
  Write-Step (T "Autostart and Audit" "Inicio automático y auditoría")
  Write-Info (T "Would change autostart and run readiness checks" "Se cambiaría el inicio automático y se ejecutarían comprobaciones de preparación")
  Write-Step (T "Restart" "Reinicio")
  Write-Info (T "Would restart TrinaxAI if requested" "Se reiniciaría TrinaxAI si se solicita")
  Write-Host ""
  Write-Host (T "Links to enter" "Enlaces de acceso") -ForegroundColor Cyan
  Write-Host "  Localhost:       https://localhost:3334"
  Write-Host "  LAN:             https://[YOUR-LAN-IP]:3334"
  Write-Host (T "  RAG health:      https://localhost:3333/health" "  Salud de RAG:    https://localhost:3333/health")
  Write-Ok (T "Dry-run finished; no changes were made" "Simulación terminada; no se hicieron cambios")
  exit 0
}

$PythonExe = Get-PythonExe
$script:RollbackActive = $false
trap {
  Restore-FailedUpdate
  exit 1
}

Write-Host ""
Write-Host "+========================================+" -ForegroundColor Blue
Write-Host "|          TrinaxAI - Smart Update       |" -ForegroundColor Blue
Write-Host "+========================================+" -ForegroundColor Blue
if ($Scheduled) { Write-Info "Weekly update check (no remote code execution)" }
else { Write-Info "Your data and settings stay untouched" }

$CreateBackup = -not $NoBackup
$PullCode = -not $NoPull
$PullModels = $Models -and -not $NoModels
$RunAudit = -not $NoAudit
$RestartAfter = $Restart -and -not $NoRestart
if (-not $RestartAfter -and $env:TRINAXAI_UPDATE_RESTART -eq "1") { $RestartAfter = $true }
$AutostartAction = if ($EnableAutostart) { "enable-autostart" } elseif ($DisableAutostart) { "disable-autostart" } else { "" }
$RepairOllamaNow = $RepairOllama
$RemoveModelsFirst = $RemoveModels
$RemoveOllamaApp = $RemoveOllama
$InstallOllamaAfterRemove = $RemoveOllama

if ($Scheduled) {
  $NonInteractive = $true
  $CreateBackup = $false
  $PullCode = $false
  $PullModels = $false
  $RunAudit = $false
  $RestartAfter = $false
}

if (-not $NonInteractive -and ($Interactive -or $env:TRINAXAI_INTERACTIVE -eq "1")) {
  $CreateBackup = Read-YesNo (T "Create a backup before updating?" "¿Crear un backup antes de actualizar?") $true
  $PullCode = Read-YesNo (T "Download the latest TrinaxAI version?" "¿Descargar la versión más reciente de TrinaxAI?") $true
  $RemoveOllamaApp = Read-YesNo (T "Remove Ollama application before continuing?" "¿Eliminar Ollama antes de continuar?") $false
  if ($RemoveOllamaApp) {
    $InstallOllamaAfterRemove = Read-YesNo (T "Install Ollama again with the official installer command after removal?" "¿Instalar Ollama de nuevo con el instalador oficial?") $true
  } else {
    $RepairOllamaNow = Read-YesNo (T "Repair/reinstall Ollama with the official installer command?" "¿Reparar/reinstalar Ollama con el instalador oficial?") $false
  }
  $PullModels = Read-YesNo (T "Download/update configured Ollama models too?" "¿Descargar/actualizar también los modelos Ollama configurados?") $false
  $RemoveModelsFirst = Read-YesNo (T "Remove configured Ollama models before model update?" "¿Eliminar los modelos Ollama antes de actualizarlos?") $false
  if (Read-YesNo (T "Change boot auto-start setting?" "¿Cambiar el arranque automático?") $false) {
    $AutostartAction = if (Read-YesNo (T "Start TrinaxAI automatically when Windows starts?" "¿Iniciar TrinaxAI automáticamente al iniciar Windows?") $true) { "enable-autostart" } else { "disable-autostart" }
  }
  $RestartAfter = Read-YesNo (T "Restart TrinaxAI after the update?" "¿Reiniciar TrinaxAI después de actualizar?") $true
  $RunAudit = Read-YesNo (T "Run public readiness audit after updating?" "¿Ejecutar readiness audit después de actualizar?") $true
}

if (-not $PythonExe) {
  Write-Warn "Python was not found. Run install.ps1 first."
  exit 1
}

if ($Scheduled) {
  Invoke-Python @("scripts\auto_update.py", "run", "--base-dir", $Repo)
  exit 0
}

if ($CreateBackup) {
  Write-Step "1/7 Backup"
  New-TrinaxAIBackup
}

if ($PullCode) {
  Write-Step "2/7 Source"
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
$RequirementsFile = if (Test-Path "requirements.lock") { "requirements.lock" } else { "requirements.txt" }
if ($RequirementsFile -eq "requirements.lock") {
  Invoke-Python @("-m", "pip", "install", "--require-hashes", "-r", $RequirementsFile)
} else {
  Invoke-Python @("-m", "pip", "install", "-r", $RequirementsFile)
}
Invoke-Python @("-m", "pip", "install", "-e", ".")
Write-Ok "Python dependencies updated"
if (Test-Path "scripts\generate_continue_config.py") {
  Invoke-Python @((Join-Path $Repo "scripts\generate_continue_config.py"), "--root", $Repo, "--install-user-config")
  Write-Ok "Continue configuration regenerated"
}

Write-Step "4/7 PWA frontend"
if (-not (Test-Path "chat-pwa\package.json") -or -not (Test-Path "chat-pwa\package-lock.json")) {
  throw "chat-pwa/package.json and package-lock.json are required for the PWA."
}
if (-not (Test-Cmd "npm")) { throw "npm is required to build the PWA." }
Push-Location "chat-pwa"
try {
  Invoke-NativeChecked "npm" @("ci") "npm ci"
  Invoke-NativeChecked "npm" @("run", "build") "npm run build"
} finally {
  Pop-Location
}
if (-not (Test-Path "chat-pwa\dist\index.html")) { throw "PWA build completed without chat-pwa/dist/index.html." }
Write-Ok "PWA rebuilt"

Write-Step "5/7 Ollama models"
$ConfiguredModels = @(Get-ConfiguredModels)
if ($RemoveModelsFirst -and $PullModels) {
  Remove-ConfiguredModels
}
$Ollama = Ensure-OllamaRunning
if (-not $Ollama) { throw "Ollama API is not ready." }
if ($PullModels) {
  foreach ($Model in $ConfiguredModels) {
    Write-Host "  Pulling $Model..."
    Invoke-NativeChecked $Ollama @("pull", $Model) "ollama pull $Model"
  }
} else {
  Write-Warn "Model downloads skipped; installed models will still be verified."
}
foreach ($Model in $ConfiguredModels) {
  if (-not (Test-OllamaModel $Ollama $Model)) { throw "Required Ollama model is not ready: $Model" }
}
Write-Ok "Models ready"

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
  Write-Warn "Restart skipped; checking the already-running TrinaxAI services."
}
Assert-RuntimeReady

Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "finish", "--root", $Repo)
$script:RollbackActive = $false
Write-Ok "TrinaxAI update finished"
Write-Info "Settings, indexes, models, and personal data were preserved."
