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

if (-not $LanguageExplicit -and -not $NonInteractive -and -not $DryRun) {
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
    foreach ($Model in @("qwen3.5:2b", "qwen3.5:4b", "qwen3-embedding:0.6b")) {
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
  Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "update", "--root", $Repo)
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
if ((Test-Cmd "npm") -and (Test-Path "chat-pwa")) {
  Push-Location "chat-pwa"
  try {
    Invoke-NativeChecked "npm" @("ci") "npm ci"
    Invoke-NativeChecked "npm" @("run", "build") "npm run build"
  } finally {
    Pop-Location
  }
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
      if ($LASTEXITCODE -ne 0) { Write-Warn "Could not pull configured model $Model." }
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

Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "finish", "--root", $Repo)
$script:RollbackActive = $false
Write-Ok "TrinaxAI update finished"
Write-Info "Settings, indexes, models, and personal data were preserved."
