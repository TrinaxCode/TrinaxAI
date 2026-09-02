<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a>
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="Estrellas en GitHub"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Release estable: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="Estado de CI"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="Licencia AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Plataformas: macOS, Windows y Linux">
</p>

<p align="center"><sub><a href="README.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="docs/README.es.md">Documentación</a> · <a href="docs/CHANGELOG.es.md">Cambios</a> · <a href="LICENSE">Licencia</a></sub></p>

> Tu asistente privado para trabajar con tus archivos desde tu propio equipo.

TrinaxAI es un asistente local basado en Ollama. Combina chat directo, RAG con
citas, investigación web opcional, un agente de código con sandbox, una CLI y
una PWA instalable. La inferencia y los datos indexados permanecen en el equipo
configurado salvo que elijas explícitamente un servicio remoto.

## Inicio rápido

### Linux y macOS

El instalador estable detecta CPU, RAM, GPU y VRAM, elige un perfil seguro,
verifica el checksum del paquete fuente, compila la PWA, comprueba Ollama y los
modelos necesarios, ejecuta una inferencia de smoke test e inicia la app.

```bash
set -e; version="1.2.1"; base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"; installer="$(mktemp)"; trap 'rm -f "$installer"' EXIT; curl -fsSL "$base/TrinaxAI-${version}-installer.sh" -o "$installer"; expected="$(curl -fsSL "$base/SHA256SUMS" | awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }')"; actual="$( (shasum -a 256 "$installer" 2>/dev/null || sha256sum "$installer") | awk '{print $1}' )"; test "$expected" = "$actual"; bash "$installer"
```

### Windows PowerShell

```powershell
$ErrorActionPreference="Stop"; $version="1.2.1"; $base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"; $installer=Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"; Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer; $line=Invoke-RestMethod -Uri "$base/SHA256SUMS" | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1; $expected=if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }; $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash; if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Installer SHA-256 verification failed." }; & $installer
```

Los instaladores de release están fijados a una versión y nunca vuelven a
`main`. Para verificar una descarga de forma independiente, sigue los comandos
breves de [firma de releases](docs/RELEASE_SIGNING.es.md). Un checkout local
(`bash install.sh` o `powershell -ExecutionPolicy Bypass -File .\install.ps1`)
es el modo de operador/desarrollo.

Al terminar, abre **https://localhost:3334**. Con `--no-models`, los modelos de
Ollama configurados deben estar instalados previamente; el instalador verifica
cada uno antes de declarar éxito.

Opciones útiles:

```bash
bash install.sh --no-start       # prepara sin iniciar servicios
bash install.sh --profile 16gb  # sobrescribe el perfil detectado
```

```powershell
.\install.ps1 -NoStart
.\install.ps1 -Profile 16gb
```

Actualiza o elimina una instalación existente con los scripts guiados:

```bash
bash update.sh
bash uninstall.sh
```

```powershell
.\update.ps1
.\uninstall.ps1
```

Consulta las guías de [Linux](docs/INSTALL_LINUX.es.md),
[macOS](docs/INSTALL_MACOS.es.md) y [Windows](docs/INSTALL_WINDOWS.es.md)
para requisitos, certificados, emparejamiento LAN, Docker y recuperación.

## Qué incluye

- Chat directo con Ollama y enrutamiento determinista para chat, código, razonamiento y matemáticas.
- RAG híbrido sobre código y documentos con citas, colecciones, indexación incremental y reranker opcional.
- Agente de código aislado y limitado a los espacios de trabajo aprobados.
- Búsqueda web, investigación profunda, memoria, voz y visión opcionales.
- PWA HTTPS para escritorio y móvil, con emparejamiento revocable y sincronización local.
- CLI para chat, indexación, investigación, ciclo de vida, diagnósticos y exportaciones.

## Modelos y hardware

El instalador usa CPU, RAM, GPU y VRAM para elegir los perfiles `8gb`, `16gb`,
`32gb` o `64gb`. Apple Silicon usa memoria unificada. Puedes sobrescribir el
perfil en `.env` o con `--profile` / `-Profile`.

| Perfil | Chat/código | Rápido | Embeddings |
| --- | --- | --- | --- |
| `8gb` | `qwen3.5:2b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `16gb` | `qwen3.5:4b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `32gb` | `qwen3.5:9b` | `qwen3.5:4b` | `qwen3-embedding:4b` |
| `64gb` | `qwen3.5:35b` / `qwen3-coder:30b` | `qwen3.5:4b` | `qwen3-embedding:4b` |

El perfil `8gb` funciona con CPU; no necesitas GPU. Los modelos grandes solo se
descargan cuando el perfil los requiere. Consulta la
[configuración](docs/CONFIGURATION.es.md) para cambiar nombres o límites.

## CLI

Después de instalar, abre una terminal nueva y usa:

```bash
trinaxai ask "Resume mi proyecto indexado" --engine rag
trinaxai index .
trinaxai agent --workspace .
trinaxai research --query "Compara estos documentos" --depth 2
trinaxai doctor --strict --json
trinaxai start
trinaxai stop
trinaxai status
```

Ejecuta `trinaxai --help` o consulta la [referencia CLI](docs/CLI_REFERENCE.es.md).
`trinaxai doctor` es el diagnóstico inicial más rápido.

## Privacidad y seguridad

Los servicios se enlazan a loopback por defecto y Ollama nunca se expone como
proxy genérico. Los navegadores LAN deben emparejarse con un código de un solo
uso y reciben únicamente capacidades explícitas; indexación, administración,
agente y gestión de modelos quedan en el host. El agente está aislado y las
acciones peligrosas requieren aprobación.

Mantén privados los puertos `3333` y `11434`, protege
`storage/.proxy_secret` y usa una VPN en vez de abrir el equipo a Internet.
Consulta [seguridad](docs/SECURITY.es.md), [emparejamiento](docs/NETWORK_PAIRING.es.md)
y [firma de releases](docs/RELEASE_SIGNING.es.md).

## Plataformas compatibles

| Plataforma | Instalador | Ciclo de vida | Cobertura automatizada |
| --- | --- | --- | --- |
| Linux (Ubuntu, Debian, Fedora, Arch) | `install.sh` | systemd de usuario | backend, CLI, PWA, E2E, instalador |
| macOS (Intel y Apple Silicon) | `install.sh` | launchctl | backend, CLI, instalador shell |
| Windows 10/11 | `install.ps1` | supervisor de procesos | backend, CLI, instalador PowerShell |

La release se prueba en runners fijados de GitHub. Descargas de modelos,
permisos y certificados dependen del equipo destino; sigue el checklist de
[TESTING.es.md](TESTING.es.md) para una instalación limpia.

## Documentación

Empieza en el [hub de documentación](docs/README.es.md):

- [Arquitectura y flujo](docs/ARCHITECTURE.es.md)
- [Configuración](docs/CONFIGURATION.es.md)
- [Variables de entorno](docs/ENVIRONMENT_VARIABLES.es.md)
- [API HTTP](docs/API_REFERENCE.es.md)
- [Solución de problemas y recuperación](docs/TROUBLESHOOTING.es.md)
- [Guía de desarrollo](docs/DEVELOPER_GUIDE.es.md)

La PWA también incluye esta documentación en **Docs**.

## Desarrollo

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock
(cd chat-pwa && npm ci && npm run dev)
```

Ejecuta `make check` antes de enviar cambios. Consulta
[CONTRIBUTING.es.md](docs/CONTRIBUTING.es.md) para el flujo completo.

## Licencia

TrinaxAI usa AGPL-3.0-or-later. Consulta [LICENSE](LICENSE) y la
[guía de marca](docs/TRADEMARK.es.md).

Creado por [TrinaxCode](https://github.com/TrinaxCode) · [trinaxai.app](https://www.trinaxai.app/)
