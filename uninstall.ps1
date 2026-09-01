param(
  [switch]$Yes,
  [switch]$Interactive,
  [switch]$NonInteractive,
  [switch]$KeepServices,
  [switch]$KeepAutostart,
  [switch]$KeepVenv,
  [switch]$KeepFrontend,
  [switch]$KeepLogs,
  [switch]$KeepEnv,
  [switch]$RemoveEnv,
  [switch]$RemoveData,
  [switch]$RemoveApp,
  [switch]$RemoveCerts,
  [switch]$RemoveModels,
  [switch]$RemoveOllama,
  [switch]$Purge,
  [switch]$DryRun,
  [switch]$KeepFirewall,
  [ValidateSet("en", "es")]
  [string]$Language = ""
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
$LanguageExplicit = -not [string]::IsNullOrWhiteSpace($Language) -or -not [string]::IsNullOrWhiteSpace($env:TRINAXAI_LANG)
if ([string]::IsNullOrWhiteSpace($Language)) { $Language = if ($env:TRINAXAI_LANG -match '^es') { 'es' } elseif ((Get-Culture).Name -match '^es') { 'es' } else { 'en' } }
function T($English, $Spanish) { if ($Language -eq 'es') { return $Spanish }; return $English }

if (-not $LanguageExplicit -and -not $NonInteractive -and -not $DryRun) {
  $Reply = Read-Host "Select language / Selecciona idioma [en/es, default: $Language]"
  if ($Reply -match '^es') { $Language = 'es' } elseif ($Reply -match '^en') { $Language = 'en' }
}

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
  if (-not $PythonExe) {
    $script:LastPythonExitCode = 127
    Write-Warn "Python was not found; skipped Python command: $($PythonArgs -join ' ')"
    return
  }
  if ($PythonExe -eq "py") {
    & py -3 @PythonArgs
  } else {
    & $PythonExe @PythonArgs
  }
  $script:LastPythonExitCode = $LASTEXITCODE
  if ($script:LastPythonExitCode -ne 0) {
    Write-Warn "Python command failed with exit code $($script:LastPythonExitCode): $($PythonArgs -join ' ')"
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
  $Parts = foreach ($Part in $UserPath.Split(";")) {
    if ([string]::IsNullOrWhiteSpace($Part)) { continue }
    try {
      if ([IO.Path]::GetFullPath($Part).TrimEnd('\') -ne $Expected) { $Part }
    } catch {
      $Part
    }
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
function Read-EnvValue($Key) {
  $EnvPath = Join-Path $Repo ".env"
  if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) { return "" }
  foreach ($Line in Get-Content -LiteralPath $EnvPath) {
    if ($Line -match "^\s*$([regex]::Escape($Key))=(.*)$") {
      return $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
  return ""
}
function Add-ConfiguredModel([System.Collections.Generic.List[string]]$List, [string]$Model) {
  if (-not [string]::IsNullOrWhiteSpace($Model) -and -not $List.Contains($Model)) {
    $List.Add($Model) | Out-Null
  }
}
function Get-ConfiguredModels {
  $List = New-Object System.Collections.Generic.List[string]
  Add-ConfiguredModel $List (Read-EnvValue "TRINAXAI_MODEL_CODE")
  Add-ConfiguredModel $List (Read-EnvValue "TRINAXAI_MODEL_DEEP")
  Add-ConfiguredModel $List (Read-EnvValue "TRINAXAI_MODEL_GENERAL")
  Add-ConfiguredModel $List (Read-EnvValue "TRINAXAI_MODEL_FAST")
  Add-ConfiguredModel $List (Read-EnvValue "TRINAXAI_EMBED")
  if ($List.Count -eq 0) {
    foreach ($Model in @("qwen3.5:2b", "qwen3.5:4b", "qwen3-embedding:0.6b", "qwen3-embedding:4b")) {
      Add-ConfiguredModel $List $Model
    }
  }
  return $List
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
    try {
      $Full = [IO.Path]::GetFullPath($Candidate)
      $Leaf = Split-Path -Leaf $Full.TrimEnd('\')
      if ($Leaf -ine "models") {
        Write-Warn "Skipped unsafe Ollama model path: $Full"
        continue
      }
      if ($Seen.ContainsKey($Full)) { continue }
      $Seen[$Full] = $true
      Remove-KnownDirectory $Full "Ollama models: $Full"
    } catch {
      Write-Warn "Skipped unsafe Ollama model path: $Candidate"
    }
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

if ($DryRun) {
  Write-Host (T "DRY-RUN: nothing will be stopped, removed, or changed." "SIMULACIÓN: no se detendrá, borrará ni modificará nada.") -ForegroundColor Yellow
  Write-Step (T "Services and autostart" "Servicios e inicio automático")
  Write-Host (T "  Would stop services and disable Windows startup" "  Se detendrían los servicios y se desactivaría el inicio de Windows")
  Write-Step (T "Automatic updates" "Actualizaciones automáticas")
  Write-Host (T "  Would disable the weekly update task" "  Se desactivaría la tarea semanal de actualización")
  Write-Step (T "Runtime files" "Archivos de ejecución")
  Write-Host (T "  Would remove .venv, frontend build, logs, and generated .env" "  Se eliminarían .venv, la compilación frontend, los logs y el .env generado")
  Write-Host (T "  Would preserve source code, indexes, models, and personal data by default" "  El código fuente, los índices, los modelos y los datos personales se conservarían por defecto")
  Write-Step (T "Ollama" "Ollama")
  Write-Host (T "  Would remove configured models/app only when explicitly requested" "  Solo se eliminarían los modelos o la aplicación configurados si se solicita explícitamente")
  Write-Host ""
  Write-Host (T "Links to enter" "Enlaces de acceso") -ForegroundColor Cyan
  Write-Host "  Localhost:       https://localhost:3334"
  Write-Host "  LAN:             https://[YOUR-LAN-IP]:3334"
  Write-Host (T "  RAG health:      https://localhost:3333/health" "  Salud de RAG:    https://localhost:3333/health")
  Write-Ok (T "Dry-run finished; no changes were made" "Simulación terminada; no se hicieron cambios")
  exit 0
}

if (-not ($Interactive -or $Yes -or $NonInteractive)) {
  $Interactive = $true
}

if ($NonInteractive -and -not ($Yes -or $DryRun)) {
  throw (T "Non-interactive uninstall requires -Yes." "La desinstalación no interactiva requiere -Yes.")
}

if ($Interactive -and -not ($Yes -or $NonInteractive)) {
  $Confirm = Read-Host (T "Type UNINSTALL to continue" "Escribe UNINSTALL para continuar")
  if ($Confirm -ne "UNINSTALL") {
    Write-Warn (T "Cancelled." "Cancelado.")
    exit 0
  }
} elseif (-not ($Yes -or $NonInteractive)) {
  $Yes = $true
}

$StopServices = -not $KeepServices
$DisableAutostart = -not $KeepAutostart
$RemoveVenv = -not $KeepVenv
$RemoveFrontend = -not $KeepFrontend
$RemoveLogs = -not $KeepLogs
$RemoveEnvRequested = [bool]$RemoveEnv -and -not $KeepEnv
$RemoveRuntimeData = $RemoveData -or $Purge
$RemoveRuntimeCerts = $RemoveCerts -or $Purge
$RemoveOllamaModels = $RemoveModels -or $RemoveOllama -or $Purge
$RemoveOllamaApp = $RemoveOllama -or $Purge
$RemoveFirewallRules = -not $KeepFirewall

if (-not ($Yes -or $NonInteractive)) {
  $StopServices = Read-YesNo (T "Stop running TrinaxAI services now?" "¿Detener los servicios activos de TrinaxAI?") $true
  $DisableAutostart = Read-YesNo (T "Disable TrinaxAI auto-start on boot?" "¿Desactivar el arranque automático de TrinaxAI?") $true
  $RemoveVenv = Read-YesNo (T "Remove Python virtual environment (.venv)?" "¿Eliminar el entorno virtual de Python (.venv)?") $true
  $RemoveFrontend = Read-YesNo (T "Remove frontend dependencies/build?" "¿Eliminar dependencias/build del frontend?") $true
  $RemoveLogs = Read-YesNo (T "Remove logs?" "¿Eliminar logs?") $true
  $RemoveEnvRequested = Read-YesNo (T "Remove generated .env configuration and admin token?" "¿Eliminar la configuración .env y el token admin generado?") $false
  $RemoveRuntimeData = Read-YesNo (T "Remove RAG index, memory, and local_sources data?" "¿Eliminar el índice RAG, memoria y local_sources?") $false
  $RemoveRuntimeCerts = Read-YesNo (T "Remove generated local HTTPS cert files?" "¿Eliminar certificados HTTPS locales generados?") $false
  $RemoveOllamaModels = Read-YesNo (T "Remove known Ollama models used by TrinaxAI?" "¿Eliminar los modelos Ollama conocidos usados por TrinaxAI?") $false
  $RemoveOllamaApp = Read-YesNo (T "Remove Ollama application too?" "¿Eliminar también la aplicación Ollama?") $false
  if ($RemoveOllamaApp) { $RemoveOllamaModels = $true }
  $RemoveFirewallRules = Read-YesNo (T "Remove TrinaxAI Windows Firewall rules?" "¿Eliminar las reglas de Firewall de Windows de TrinaxAI?") $true
}

# Read the configured fleet before optional removal of .env; model-only cleanup
# must never fall back to a directory-wide deletion or to a stale hardcoded list.
$ModelsToRemove = @(Get-ConfiguredModels)
foreach ($Model in @("qwen3-embedding:0.6b", "qwen3-embedding:4b")) {
  if ($ModelsToRemove -notcontains $Model) { $ModelsToRemove += $Model }
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
if ($RemoveEnvRequested) { $Targets.Add(".env") | Out-Null }
if ($RemoveRuntimeData) {
  $Targets.Add("storage") | Out-Null
  $Targets.Add("local_sources") | Out-Null
}
if ($RemoveRuntimeCerts) { $Targets.Add("chat-pwa\certs") | Out-Null }
if ($RemoveApp) {
  if ((Test-Path (Join-Path $Repo ".trinaxai-managed")) -and (Test-Path (Join-Path $Repo "scripts\source_update.py"))) {
    Invoke-Python @((Join-Path $Repo "scripts\source_update.py"), "remove", "--root", $Repo)
    if ($script:LastPythonExitCode -eq 0) { Write-Ok "Managed TrinaxAI application files removed" }
    else { Write-Warn "Managed TrinaxAI application files could not be removed completely." }
  } else {
    Write-Warn "Application source was kept because this is not a managed installation."
  }
}
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
    foreach ($Model in $ModelsToRemove) {
      Write-Host "  Removing $Model..."
      & $Ollama rm $Model 2>$null
      if ($LASTEXITCODE -ne 0) { Write-Warn "Could not remove configured model $Model." }
    }
  } else {
    Write-Warn "Ollama not found; model removal skipped."
  }
  if ($RemoveOllamaApp) { Remove-OllamaModelsAndState }
}

if ($RemoveOllamaApp) {
  Write-Step "Ollama application"
  Remove-OllamaApp
}

Write-Ok "TrinaxAI uninstall finished"
