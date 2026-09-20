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
if ($ReleaseVersion -and $ReleaseVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw (T "Invalid TrinaxAI release version: $ReleaseVersion" "Versión de lanzamiento de TrinaxAI no válida: $ReleaseVersion") }
$SourceUpdateUrl = if (-not [string]::IsNullOrWhiteSpace($env:TRINAXAI_UPDATE_SOURCE_URL)) { $env:TRINAXAI_UPDATE_SOURCE_URL } else { "" }
$SourceUpdateSha256 = if (-not [string]::IsNullOrWhiteSpace($env:TRINAXAI_UPDATE_SOURCE_SHA256)) { $env:TRINAXAI_UPDATE_SOURCE_SHA256 } else { $env:TRINAXAI_SOURCE_SHA256 }
if ($SourceUpdateSha256) { $SourceUpdateSha256 = $SourceUpdateSha256.Trim() }
if ($SourceUpdateSha256 -and $SourceUpdateSha256 -notmatch '^[0-9a-fA-F]{64}$') {
  throw (T "Source archive checksum must be a SHA-256 digest." "La suma de comprobación del archivo fuente debe ser un resumen SHA-256.")
}
if ([string]::IsNullOrWhiteSpace($SourceUpdateUrl) -and $ReleaseVersion) {
  $SourceUpdateUrl = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$ReleaseVersion/TrinaxAI-$ReleaseVersion.tar.gz"
}
$IsReleaseSourceUrl = $SourceUpdateUrl -match '^https://github\.com/TrinaxCode/TrinaxAI/releases/download/v[0-9]+\.[0-9]+\.[0-9]+/TrinaxAI-[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz$'
if ($SourceUpdateUrl -and -not $IsReleaseSourceUrl -and [string]::IsNullOrWhiteSpace($SourceUpdateSha256)) {
  throw (T "TRINAXAI_UPDATE_SOURCE_URL requires a matching SHA-256 checksum." "TRINAXAI_UPDATE_SOURCE_URL requiere una suma de comprobación SHA-256 coincidente.")
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
  $Seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  $Paths = [Collections.Generic.List[string]]::new()
  foreach ($PathList in (@($env:Path, $MachinePath, $UserPath) + $ExtraPaths)) {
    foreach ($Entry in @([string]$PathList -split ";")) {
      $Entry = $Entry.Trim()
      if ($Entry -and $Seen.Add($Entry)) { $Paths.Add($Entry) }
    }
  }
  $env:Path = $Paths -join ";"
}
function Invoke-NativeChecked([string]$FilePath, [string[]]$Arguments, [string]$Label) {
  & $FilePath @Arguments
  $ExitCode = $LASTEXITCODE
  if ($ExitCode -ne 0) {
    throw (T "$Label failed with exit code $ExitCode." "$Label falló con el código de salida $ExitCode.")
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
    throw (T "Python command failed with exit code ${ExitCode}: $PythonExe $($PythonArgs -join ' ')" "El comando de Python falló con el código de salida ${ExitCode}: $PythonExe $($PythonArgs -join ' ')")
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
  if (-not $RagBase) { throw (T "TrinaxAI backend is not ready on port $RagPort." "El backend de TrinaxAI no está listo en el puerto $RagPort.") }
  $PwaBase = Wait-LocalUrl $PwaPort
  if (-not $PwaBase) { throw (T "TrinaxAI PWA is not ready on port $PwaPort." "La PWA de TrinaxAI no está lista en el puerto $PwaPort.") }
  $Body = @{ messages = @(@{ role = "user"; content = "Reply with the single word OK." }); stream = $false; mode = "model"; think = $false } | ConvertTo-Json -Compress
  try {
    $Response = Invoke-LocalWebRequest "$RagBase/v1/chat/completions" "POST" $Body
    $Payload = $Response.Content | ConvertFrom-Json
    $Content = $Payload.choices[0].message.content
    if ([string]::IsNullOrWhiteSpace([string]$Content)) { throw (T "empty response" "respuesta vacía") }
  } catch {
    throw ((T "TrinaxAI smoke inference failed" "La inferencia de prueba de TrinaxAI falló") + ": $($_.Exception.Message)")
  }
  Write-Ok (T "Backend, PWA, and smoke inference are ready" "El backend, la PWA y la inferencia de prueba están listos")
}
function Stop-OllamaProcesses {
  try {
    Get-CimInstance Win32_Process |
      Where-Object { $_.CommandLine -and ($_.CommandLine -like "*ollama*") } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  } catch {
    Write-Warn (T "Could not enumerate Ollama processes." "No se pudieron enumerar los procesos de Ollama.")
  }
}
function Invoke-ExternalWithTimeout([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSec = 90) {
  try {
    $Proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments -PassThru -WindowStyle Hidden
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
      Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
      Write-Warn (T "$FilePath timed out after ${TimeoutSec}s." "$FilePath agotó el tiempo de espera después de ${TimeoutSec}s.")
      return $false
    }
    return ($Proc.ExitCode -eq 0)
  } catch {
    Write-Warn ((T "Could not run ${FilePath}" "No se pudo ejecutar ${FilePath}") + ": $($_.Exception.Message)")
    return $false
  }
}
function Install-OllamaOfficial {
  Write-Host (T "  Installing Ollama with: irm https://ollama.com/install.ps1 | iex" "  Instalando Ollama con: irm https://ollama.com/install.ps1 | iex")
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
    Write-Warn ((T "Official Ollama install command failed" "El comando oficial de instalación de Ollama falló") + ": $($_.Exception.Message)")
    return $false
  }
}
function Remove-KnownDirectory([string]$Path, [string]$Label) {
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  try {
    if ($Path -notmatch '^(?:[A-Za-z]:[\\/]|\\\\)') { throw (T "Unsafe path: $Path" "Ruta insegura: $Path") }
    $Full = [IO.Path]::GetFullPath($Path)
    if ($Full -eq [IO.Path]::GetPathRoot($Full)) { throw (T "Unsafe path: $Full" "Ruta insegura: $Full") }
    if (Test-Path -LiteralPath $Full) {
      Remove-Item -LiteralPath $Full -Recurse -Force
      Write-Ok (T "Removed $Label" "$Label eliminado")
    }
  } catch {
    Write-Warn ((T "Could not remove ${Label}" "No se pudo eliminar ${Label}") + ": $($_.Exception.Message)")
  }
}
function Remove-OllamaApp {
  Stop-OllamaProcesses
  if (Test-Cmd "winget") {
    if (-not (Invoke-ExternalWithTimeout "winget" @("uninstall", "--id", "Ollama.Ollama", "--silent", "--accept-source-agreements") 120)) {
      Write-Warn (T "winget could not remove the Ollama package; continuing with known application paths." "winget no pudo eliminar el paquete de Ollama; se continuará con las rutas conocidas de la aplicación.")
    }
  }
  Stop-OllamaProcesses
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Programs\Ollama") (T "Ollama app" "aplicación de Ollama")
  Remove-KnownDirectory (Join-Path $env:LOCALAPPDATA "Ollama") (T "Ollama local app data" "datos locales de la aplicación Ollama")
  Remove-KnownDirectory (Join-Path $env:APPDATA "Ollama") (T "Ollama roaming app data" "datos móviles de la aplicación Ollama")
  Remove-KnownDirectory (Join-Path $env:ProgramFiles "Ollama") (T "Ollama Program Files app" "aplicación Ollama de Archivos de programa")
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
      Write-Host (T "  Removing $Model..." "  Eliminando $Model...")
      & $Ollama rm $Model 2>$null
      if ($LASTEXITCODE -ne 0) { Write-Warn (T "Could not remove configured model $Model." "No se pudo eliminar el modelo configurado $Model.") }
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
    Write-Warn (T "No runtime files found to back up." "No se encontraron archivos de ejecución para respaldar.")
    return
  }

  if (-not $PythonExe) { throw (T "Python is required to pause services before backup." "Se requiere Python para pausar los servicios antes del respaldo.") }
  $Status = Get-TrinaxAIServiceStatus
  $ApiWasRunning = Test-TrinaxAIRagApiRunning $Status
  try {
    if ($ApiWasRunning) {
      Invoke-ServiceManager "stop-ai"
      if (Test-TrinaxAIRagApiRunning (Get-TrinaxAIServiceStatus)) {
        throw (T "The TrinaxAI RAG API is still running; backup was not created." "La API RAG de TrinaxAI sigue en ejecución; no se creó el respaldo.")
      }
    }
    Compress-Archive -Path $Items -DestinationPath $ZipPath -Force
    if (Test-Cmd "icacls") {
      & icacls $ZipPath /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
    }
    Write-Ok (T "Backup created: $ZipPath" "Respaldo creado: $ZipPath")
  } finally {
    if ($ApiWasRunning) {
      Invoke-ServiceManager "start-ai"
      if (-not (Test-TrinaxAIRagApiRunning (Get-TrinaxAIServiceStatus))) {
        throw (T "The TrinaxAI RAG API could not be restored after backup." "No se pudo restaurar la API RAG de TrinaxAI después del respaldo.")
      }
    }
  }
}
function Invoke-ServiceManager($Action) {
  if (-not $PythonExe) { Write-Warn (T "Python not found; skipped service_manager $Action." "No se encontró Python; se omitió service_manager $Action."); return }
  Invoke-Python @((Join-Path $Repo "service_manager.py"), $Action, "--base-dir", $Repo)
}
function Get-TrinaxAIServiceStatus {
  $Output = @(Invoke-Python @((Join-Path $Repo "service_manager.py"), "status", "--json", "--base-dir", $Repo) 2>$null)
  if ($Output.Count -eq 0) { throw (T "The service manager returned no status." "El gestor de servicios no devolvió ningún estado.") }
  try {
    return (($Output -join [Environment]::NewLine) | ConvertFrom-Json)
  } catch {
    throw ((T "The service manager returned invalid status JSON" "El gestor de servicios devolvió un JSON de estado no válido") + ": $($_.Exception.Message)")
  }
}
function Test-TrinaxAIRagApiRunning($Status) {
  $Api = @($Status | Where-Object { $_.name -eq "rag_api" } | Select-Object -First 1)
  return $Api.Count -eq 1 -and [bool]$Api[0].running
}

function Sync-TrinaxRepository {
  if (-not (Test-Path -LiteralPath (Join-Path $Repo ".trinaxai-managed") -PathType Leaf)) {
    throw (T "This is not a managed TrinaxAI installation; source update stopped safely." "Esta no es una instalación administrada de TrinaxAI; la actualización del código fuente se detuvo de forma segura.")
  }
  if (-not (Test-Path -LiteralPath (Join-Path $Repo "scripts\source_update.py") -PathType Leaf)) {
    throw (T "The safe source updater is missing; source update stopped safely." "Falta el actualizador seguro del código fuente; la actualización se detuvo de forma segura.")
  }
  Write-Info (T "Downloading the latest TrinaxAI source package from GitHub..." "Descargando el paquete fuente más reciente de TrinaxAI desde GitHub...")
  $SourceArgs = @((Join-Path $Repo "scripts\source_update.py"), "update", "--root", $Repo)
  if ($SourceUpdateUrl) { $SourceArgs += @("--url", $SourceUpdateUrl) }
  if ($SourceUpdateSha256) { $SourceArgs += @("--sha256", $SourceUpdateSha256) }
  Invoke-Python $SourceArgs
  $script:RollbackActive = $true
  Write-Ok (T "Source package updated" "Paquete fuente actualizado")
}

function Restore-FailedUpdate {
  if (-not $script:RollbackActive) { return }
  Write-Warn (T "Update failed; restoring the previously working source tree." "La actualización falló; se restaurará el árbol de código fuente que funcionaba anteriormente.")
  try {
    Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "rollback", "--root", $Repo)
  } catch {
    Write-Warn ((T "Automatic source rollback failed" "Falló la reversión automática del código fuente") + ": $($_.Exception.Message)")
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
  Write-Host (T "  Localhost:       https://localhost:3334" "  Localhost:       https://localhost:3334")
  Write-Host (T "  LAN:             https://[YOUR-LAN-IP]:3334" "  LAN / Red local: https://[TU-IP-LAN]:3334")
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
Write-Host (T "|          TrinaxAI - Smart Update       |" "|       TrinaxAI - Actualización inteligente |") -ForegroundColor Blue
Write-Host "+========================================+" -ForegroundColor Blue
if ($Scheduled) { Write-Info (T "Weekly update check (no remote code execution)" "Comprobación semanal de actualización (sin ejecución de código remoto)") }
else { Write-Info (T "Your data and settings stay untouched" "Tus datos y configuraciones no se modificarán") }

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
  Write-Warn (T "Python was not found. Run install.ps1 first." "No se encontró Python. Ejecuta primero install.ps1.")
  exit 1
}

if ($Scheduled) {
  Invoke-Python @("scripts\auto_update.py", "run", "--base-dir", $Repo)
  exit 0
}

if ($CreateBackup) {
  Write-Step (T "1/7 Backup" "1/7 Respaldo")
  New-TrinaxAIBackup
}

if ($PullCode) {
  Write-Step (T "2/7 Source" "2/7 Código fuente")
  Sync-TrinaxRepository
}

if ($RemoveOllamaApp) {
  Write-Step (T "Ollama application" "Aplicación Ollama")
  Remove-OllamaApp
  if ($InstallOllamaAfterRemove) {
    if (Install-OllamaOfficial) { Write-Ok (T "Ollama installed" "Ollama instalado") } else { Write-Warn (T "Ollama reinstall failed." "Falló la reinstalación de Ollama.") }
  } else {
    $PullModels = $false
  }
} elseif ($RepairOllamaNow) {
  Write-Step (T "Ollama repair" "Reparación de Ollama")
  if (Install-OllamaOfficial) { Write-Ok (T "Ollama installed" "Ollama instalado") } else { Write-Warn (T "Ollama repair failed." "Falló la reparación de Ollama.") }
}

Write-Step (T "3/7 Python dependencies" "3/7 Dependencias de Python")
Invoke-Python @("-m", "pip", "install", "--upgrade", "pip")
$RequirementsFile = if (Test-Path "requirements.lock") { "requirements.lock" } else { "requirements.txt" }
if ($RequirementsFile -eq "requirements.lock") {
  Invoke-Python @("-m", "pip", "install", "--require-hashes", "-r", $RequirementsFile)
} else {
  Invoke-Python @("-m", "pip", "install", "-r", $RequirementsFile)
}
Invoke-Python @("-m", "pip", "install", "-e", ".")
Write-Ok (T "Python dependencies updated" "Dependencias de Python actualizadas")
if (Test-Path "scripts\generate_continue_config.py") {
  Invoke-Python @((Join-Path $Repo "scripts\generate_continue_config.py"), "--root", $Repo, "--install-user-config")
  Write-Ok (T "Continue configuration regenerated" "Configuración de Continue regenerada")
}

Write-Step (T "4/7 PWA frontend" "4/7 Frontend PWA")
if (-not (Test-Path "chat-pwa\package.json") -or -not (Test-Path "chat-pwa\package-lock.json")) {
  throw (T "chat-pwa/package.json and package-lock.json are required for the PWA." "La PWA requiere chat-pwa/package.json y package-lock.json.")
}
if (-not (Test-Cmd "npm")) { throw (T "npm is required to build the PWA." "Se requiere npm para compilar la PWA.") }
Push-Location "chat-pwa"
try {
  Invoke-NativeChecked "npm" @("ci") (T "npm ci" "npm ci")
  Invoke-NativeChecked "npm" @("run", "build") (T "npm run build" "npm run build")
} finally {
  Pop-Location
}
if (-not (Test-Path "chat-pwa\dist\index.html")) { throw (T "PWA build completed without chat-pwa/dist/index.html." "La compilación de la PWA terminó sin chat-pwa/dist/index.html.") }
Write-Ok (T "PWA rebuilt" "PWA recompilada")

Write-Step (T "5/7 Ollama models" "5/7 Modelos de Ollama")
$ConfiguredModels = @(Get-ConfiguredModels)
if ($RemoveModelsFirst -and $PullModels) {
  Remove-ConfiguredModels
}
$Ollama = $null
if ($PullModels) {
  $Ollama = Ensure-OllamaRunning
  if (-not $Ollama) { throw (T "Ollama API is not ready." "La API de Ollama no está lista.") }
}
if ($PullModels) {
  foreach ($Model in $ConfiguredModels) {
    Write-Host (T "  Pulling $Model..." "  Descargando $Model...")
    Invoke-NativeChecked $Ollama @("pull", $Model) (T "ollama pull $Model" "ollama pull $Model")
  }
} else {
  Write-Warn (T "Model downloads skipped; model preparation is deferred." "Se omitieron las descargas de modelos; la preparación de modelos queda pendiente.")
}
if ($PullModels) {
  foreach ($Model in $ConfiguredModels) {
    if (-not (Test-OllamaModel $Ollama $Model)) { throw (T "Required Ollama model is not ready: $Model" "El modelo de Ollama requerido no está listo: $Model") }
  }
  Write-Ok (T "Models ready" "Modelos listos")
}

Write-Step (T "6/7 Autostart and audit" "6/7 Inicio automático y auditoría")
if ($AutostartAction) {
  Invoke-ServiceManager $AutostartAction
}
if ($RunAudit -and (Test-Path "scripts\public_readiness.py")) {
  Invoke-Python @("scripts\public_readiness.py")
} elseif ($RunAudit) {
  Write-Warn (T "scripts\public_readiness.py not found; audit skipped." "No se encontró scripts\public_readiness.py; se omitió la auditoría.")
}

Write-Step (T "7/7 Restart" "7/7 Reinicio")
if ($RestartAfter) {
  Invoke-ServiceManager "stop-all"
  Invoke-ServiceManager "start"
  Write-Ok (T "TrinaxAI restarted" "TrinaxAI reiniciado")
} else {
  Write-Warn (T "Restart skipped; runtime readiness check deferred." "Se omitió el reinicio; la comprobación de preparación queda pendiente.")
  $RestartAfter = $false
}
if ($RestartAfter) { Assert-RuntimeReady }

Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "finish", "--root", $Repo)
$script:RollbackActive = $false
Write-Ok (T "TrinaxAI update finished" "Actualización de TrinaxAI terminada")
Write-Info (T "Settings, indexes, models, and personal data were preserved." "Se conservaron las configuraciones, los índices, los modelos y los datos personales.")
