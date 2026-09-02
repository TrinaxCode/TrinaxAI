<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🪟 Instalación en Windows
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="INSTALL_WINDOWS.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

Guía para instalar, configurar, iniciar y dejar listo TrinaxAI en Windows 10/11 con PowerShell.

## Estado de soporte

El instalador de Windows está disponible y el CI valida smoke tests de Python/CLI, sintaxis, dry-runs de PowerShell y el flujo de descarga de código por URL. La instalación completa con descargas reales de dependencias/modelos y el primer inicio todavía requiere el smoke test en máquina descrito en [TESTING.es.md](../TESTING.es.md).

## Qué queda funcionando

Al terminar deberías tener:

- Ollama instalado y respondiendo en `http://localhost:11434`.
- API RAG en `https://localhost:3333` cuando existe el certificado administrado (HTTP es el fallback).
- PWA en `https://localhost:3334`.
- Entorno Python `.venv`.
- Dependencias de la PWA.
- Modelos base descargados si eliges esa opción.
- `.env` generado.
- Autoarranque opcional desde la carpeta Startup de Windows: la PWA vuelve al iniciar el equipo y la IA respeta si quedo encendida o apagada.

## Requisitos

| Recurso | Mínimo | Recomendado |
|---|---:|---:|
| Windows | 10/11 | 11 |
| RAM | 8 GB | 16 GB o más |
| Disco libre | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 22 | 24 LTS |
| Ollama | Sí | Última versión |
| PowerShell | 5+ | PowerShell 7 |

## Instalación recomendada fijada a un release

> Estado del release: `v1.2.1` es Production/Stable. Sus paquetes fuente, instaladores, wheel, checksums y firmas están publicados en GitHub. El instalador nunca vuelve a `main`.

Abre PowerShell y ejecuta:

```powershell
$ErrorActionPreference="Stop"; $version="1.2.1"; $base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"; $installer=Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"; Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer; $line=Invoke-RestMethod -Uri "$base/SHA256SUMS" | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1; $expected=if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }; $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash; if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }; & $installer
```

El instalador descarga directamente el ZIP fuente desde GitHub. No necesita Git, Python ni Node.js previamente; instala las dependencias necesarias, configura Ollama, compila la PWA, verifica una inferencia de smoke test e inicia TrinaxAI. Acepta los permisos de administrador cuando Windows los solicite. Para revisar checksum o GPG manualmente, consulta [firma de releases](RELEASE_SIGNING.es.md).

## Opciones del instalador

El comando fijado de arriba es la ruta normal. Instala en
`%LOCALAPPDATA%\TrinaxAI` por defecto; usa un checkout local o una carpeta
personalizada cuando necesites revisar o controlar el código fuente:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador:

- Detecta RAM y elige perfil.
- Crea `.env`.
- Instala dependencias automáticamente. Ollama prueba primero el instalador oficial, verifica el fallback firmado `OllamaSetup.exe` si hace falta y deja `winget` como último recurso.
- Crea `.venv`.
- Instala paquetes Python.
- Instala y compila la PWA.
- Pregunta si quieres descargar modelos de Ollama.
- Pregunta si quieres habilitar inicio con Windows.
- Pregunta si quieres iniciar los servicios ahora.

Las dependencias necesarias se instalan automáticamente. Las opciones como modelos, inicio con Windows e inicio de servicios se preguntan por defecto. La configuración legacy de sistema por LAN se acepta por compatibilidad, pero nunca concede administración remota del host. Usa `-NonInteractive` para instalaciones automatizadas. Si las rutas automáticas no terminan, se abre la ventana del `OllamaSetup.exe` oficial firmado; pulsa **Install**, espera y vuelve a ejecutar el instalador si PowerShell aún no encuentra `ollama.exe`.

Usa `-NoStart` para dejar TrinaxAI detenido; también se omite el inicio automático de Windows y podrás activarlo después de iniciar TrinaxAI.

La ejecución desde un checkout local es un modo de operador/desarrollo y no se bloquea intencionalmente; revisa y protege ese checkout por separado del flujo de descarga de releases verificado.

Después administra TrinaxAI desde cualquier carpeta:

```powershell
trinaxai doctor
trinaxai update
trinaxai uninstall
```

`trinaxai uninstall -y` aplica opciones seguras. Los índices y modelos se conservan salvo que pidas eliminarlos.

## Instalar dependencias manualmente

Puedes instalar con `winget`:

```powershell
winget install --id Python.Python.3.12 --silent
winget install --id OpenJS.NodeJS.LTS --silent
winget install --id Ollama.Ollama --silent
```

O descarga manualmente:

- Python: `https://python.org`
- Node.js LTS: `https://nodejs.org`
- Ollama: `https://ollama.com/download/windows`

Cierra y vuelve a abrir PowerShell después de instalar para refrescar `PATH`.

Verifica:

```powershell
python --version
node --version
npm --version
ollama --version
```

## Instalación manual

### 1. Descargar el archivo del release

```powershell
$ErrorActionPreference = "Stop"
$version = "1.2.1"
if ($version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Versión de release inválida" }
$base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
$zip = "$env:TEMP\TrinaxAI-$version.zip"
$manifest = "$env:TEMP\TrinaxAI-$version-SHA256SUMS"
Invoke-WebRequest -Uri "$base/TrinaxAI-$version.zip" -OutFile $zip
Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
$line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version\.zip$" } | Select-Object -First 1
$expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Falló la verificación SHA-256 del archivo fuente." }
Expand-Archive $zip $env:TEMP -Force
Move-Item "$env:TEMP\TrinaxAI-$version" "$env:USERPROFILE\trinaxai"
cd $env:USERPROFILE\trinaxai
```

### 2. Crear entorno Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
```

### 3. Instalar la PWA

```powershell
cd chat-pwa
npm ci
npm run build
cd ..
```

### 4. Iniciar Ollama

Abre la app de Ollama o ejecuta:

```powershell
ollama serve
```

En otra terminal verifica:

```powershell
ollama list
```

### 5. Crear `.env`

```powershell
Copy-Item .env.example .env
```

Valores recomendados (deja el perfil automático salvo que necesites sobrescribirlo):

```text
# Déjalo sin definir para detectar CPU/RAM/GPU.
#TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=./local_sources
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
TRINAXAI_RAG_HTTPS=1
TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
```

Tras cambiar de Wi-Fi, renueva la dirección local y el certificado HTTPS:

```powershell
trinaxai network refresh
```

Usa desde el teléfono la URL por IP que muestra; la URL `.local` es una alternativa cuando mDNS funciona en el router.

## Descargar modelos

Perfil `16gb` recomendado:

```powershell
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
```

Para los demás perfiles, consulta la
[tabla vigente de modelos y perfiles](../README.es.md#modelos-y-perfiles-de-hardware). El
instalador selecciona y descarga automáticamente la flota de texto/RAG. La visión
se descarga al analizar la primera imagen.

## Indexar tus archivos

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe index.py
```

También puedes abrir la PWA, ir a configuración, elegir una carpeta y asignarla a una colección. TrinaxAI copiará los archivos a `local_sources\collections\` antes de indexarlos.

## Iniciar TrinaxAI

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe service_manager.py start --base-dir "$PWD"
```

El gateway escucha en loopback por defecto. Para un acceso LAN intencional,
establece `TRINAXAI_PWA_HOST=0.0.0.0` en `.env`, reinicia TrinaxAI y vincula el
navegador remoto antes de usarlo.

Abrir:

```text
https://localhost:3334
```

Desde teléfono o tablet en la misma WiFi:

```text
https://TU-IP-LAN:3334
```

Si el navegador informa que el certificado no es confiable, instala la CA pública
que muestra `trinaxai network` y confía en ella en ese dispositivo. No omitas la
advertencia en una conexión LAN; consulta [pairing LAN y confianza HTTPS](NETWORK_PAIRING.es.md).

## Apagar, reiniciar y revisar estado

Apagar IA y dejar la PWA disponible:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-ai --base-dir "$PWD"
```

Apagar todo:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-all --base-dir "$PWD"
```

Esto deja solo la página de recuperación por loopback en `https://localhost:3334`; el acceso LAN permanece cerrado hasta iniciar TrinaxAI allí.

Ver estado:

```powershell
.\.venv\Scripts\python.exe service_manager.py status --base-dir "$PWD"
```

Supervisor manual:

```powershell
.\.venv\Scripts\python.exe service_manager.py watch --base-dir "$PWD"
```

## Autoarranque en Windows

El instalador lo habilita automáticamente. El supervisor siempre intenta mantener la PWA disponible; si apagaste la IA desde la PWA o con `service_manager.py stop-ai`, el siguiente arranque no levanta Ollama/RAG hasta que vuelvas a encender la IA.

Habilitar:

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe service_manager.py enable-autostart --base-dir "$PWD"
```

Esto crea `TrinaxAI.vbs` en la carpeta Startup de Windows para que no quede una consola visible.

Deshabilitar:

```powershell
.\.venv\Scripts\python.exe service_manager.py disable-autostart --base-dir "$PWD"
```

También puedes revisar la carpeta Startup:

```powershell
explorer "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
```

## Verificar que todo funciona

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe test_system.py --verbose
```

Pruebas manuales:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
Invoke-RestMethod https://localhost:3333/health
```

Si tu PowerShell no soporta `-SkipCertificateCheck`, abre en navegador:

```text
https://localhost:3333/health
```

## Uso diario

1. Abre `https://localhost:3334`.
2. Usa Ollama para chat general.
3. Usa RAG para consultar archivos indexados.
4. Usa colecciones para separar proyectos.
5. Instala la PWA desde Chrome o Edge con el icono de instalación de la barra de direcciones.

## Actualizar

Usa el actualizador nativo de Windows:

```powershell
cd $env:USERPROFILE\trinaxai
powershell -ExecutionPolicy Bypass -File .\update.ps1
```

El actualizador pregunta si quieres crear backup, descargar código nuevo, actualizar modelos, cambiar autoarranque, reiniciar servicios y correr la auditoría. Las dependencias Python/npm y el build de la PWA siguen siendo automáticos.

El instalador crea la tarea semanal `TrinaxAI Weekly Update`. Aunque conserva
el nombre histórico, solo comprueba: registra disponibilidad en
`logs\auto-update.log` y nunca descarga/ejecuta un updater ni cambia la
instalación. Revisa el release etiquetado y ejecuta `update.ps1` manualmente.

## Copias de seguridad

Respaldar manualmente:

- `.env`
- `storage\`
- `local_sources\`

Si tienes Bash:

```bash
./backup.sh create
```

El archivo contiene `.env`, chats, adjuntos, fuentes e índices. El script lo
deja privado (`0600` donde esté soportado); cifra copias fuera del host. La
restauración valida rutas/tipos, usa staging y revierte un reemplazo fallido.
Pruébala antes de actualizar.

## Desinstalar

Usa el desinstalador nativo de Windows:

```powershell
cd $env:USERPROFILE\trinaxai
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

Pregunta qué archivos runtime quieres quitar. Los datos RAG y modelos de Ollama se conservan salvo que elijas borrarlos.

## Firewall y red local

| Puerto | Servicio | Uso |
|---:|---|---|
| 11434 | Ollama | Modelos locales |
| 3333 | RAG API | Backend |
| 3334 | PWA | Interfaz web |

Para abrirla desde un teléfono o tablet, permite el gateway PWA en el puerto
`3334` solo en redes privadas. Mantén FastAPI `3333` y Ollama `11434` en
loopback y no los permitas en redes públicas.

## Problemas comunes

| Problema | Solución |
|---|---|
| `python` no se reconoce | Reinstala Python marcando `Add python.exe to PATH`. |
| `npm` no se reconoce | Instala Node.js LTS y abre una terminal nueva. |
| `ollama` no se reconoce | Vuelve a ejecutar `install.ps1`; refresca PATH y abre el instalador oficial firmado si las rutas automáticas fallan. |
| Error de permisos PowerShell | Ejecuta con `-ExecutionPolicy Bypass`. |
| La PWA no abre desde el teléfono | Ejecuta `trinaxai network refresh`, abre la URL `https://HOST-LAN-IP:3334` que muestra y permite el gateway en el firewall de red privada. |
| API HTTPS muestra certificado no valido | Instala/confía en la CA pública que muestra `trinaxai network`; no omitas TLS en una LAN. Consulta [pairing LAN y confianza HTTPS](NETWORK_PAIRING.es.md). |
| Out of memory | Usa el perfil `8gb`. Sus roles de texto usan `qwen3.5:2b` y `qwen3-embedding:0.6b`; reduce el contexto si es necesario. |

## Nota sobre WSL

Puedes ejecutar TrinaxAI dentro de WSL2 usando la guía Linux, pero para usuarios
de Windows el camino más directo es PowerShell + `install.ps1`. Si usas WSL2,
ten en cuenta que la red, el firewall y el acceso a archivos funcionan de forma
diferente entre Windows y Linux.

## Seguridad

Mantén FastAPI `3333` y Ollama `11434` en loopback; expón solo el gateway PWA
en `3334` dentro de una red privada confiable. No expongas estos puertos a
Internet. Para acceso remoto usa VPN. La administración del sistema siempre
queda solo en localhost; la variable legacy se acepta para `.env` antiguos,
pero nunca concede autoridad por LAN:

```text
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=un-token-largo
```
