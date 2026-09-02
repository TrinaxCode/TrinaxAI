<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🧪 Pruebas de instaladores
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="TESTING.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="docs/README.es.md">Documentación</a> · <a href="README.es.md">Inicio</a> · <a href="docs/CHANGELOG.es.md">Cambios</a></sub></p>

Estas comprobaciones cubren los scripts del ciclo de vida basados en URL, el comportamiento de la CLI y pruebas en máquinas reales. El modo dry-run nunca descarga el paquete de código ni Ollama, instala paquetes, inicia servicios, modifica `PATH`, edita launch agents ni elimina archivos.

> Estado del release: `v1.2.1` es Production/Stable. Sus assets del Release de GitHub están publicados y los instaladores fijados nunca vuelven a `main`.

## Prueba rápida del instalador por URL

Prueba el recorrido normal en una máquina limpia con el release estable publicado. La comprobación del manifiesto SHA-256 de cada bloque de descarga es obligatoria antes de ejecutar. La clave pública fijada y el procedimiento de verificación GPG están documentados en [firma de releases](docs/RELEASE_SIGNING.es.md).

1. Descarga, revisa y ejecuta un instalador fijado al release.
   Linux/macOS:
   ```bash
   set -eu
   version="1.2.1"
   base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
   installer="$(mktemp)"
   manifest="$(mktemp)"
   trap 'rm -f "$installer" "$manifest"' EXIT
   curl --fail --location --output "$installer" "${base}/TrinaxAI-${version}-installer.sh"
   curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
   expected="$(awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
   if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$installer" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$installer" | awk '{print $1}')"; else echo "Se necesita una herramienta SHA-256 (sha256sum o shasum)." >&2; exit 2; fi
   if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Falló la verificación SHA-256 del instalador." >&2; exit 1; fi
   bash -n "$installer"
   bash "$installer"
   ```
   Windows PowerShell:
   ```powershell
   $ErrorActionPreference = "Stop"
   $version = "1.2.1"
   $base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
   $installer = Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"
   $manifest = Join-Path $env:TEMP "TrinaxAI-$version-SHA256SUMS"
   Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer
   Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
   $line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1
   $expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
   $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
   if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Falló la verificación SHA-256 del instalador." }
   Get-Content -Path $installer
   & $installer
   ```
2. Confirma que el archivo fuente se descarga directamente y que Git no se instala ni se solicita.
3. Abre `https://localhost:3334` y después ejecuta `trinaxai update` y `trinaxai uninstall`.
4. Confirma que el perfil detectado sea uno de `8gb`, `16gb`, `32gb` o `64gb`.

Las comprobaciones por comandos siguientes validan variantes avanzadas del mismo flujo.

## Simulación local

Desde la raíz del repositorio:

```bash
chmod +x test-installers.sh
./test-installers.sh
./install.sh --dry-run
./update.sh --dry-run
./uninstall.sh --dry-run
```

En Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -DryRun
.\update.ps1 -DryRun
.\uninstall.ps1 -DryRun
```

La salida debe contener la etiqueta de enlaces de acceso del idioma seleccionado: `Links to enter` en inglés o `Enlaces de acceso` en español. La simulación de instalación de Windows también muestra las instrucciones oficiales de respaldo de Ollama.

## Prueba avanzada de scripts: máquina real con macOS

Usa una cuenta de usuario normal con Homebrew disponible o permite que el instalador ofrezca instalarlo. Revisa el script antes de ejecutar un instalador descargado de la red.

```bash
set -eu
version="1.2.1"
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
installer="$(mktemp)"
manifest="$(mktemp)"
trap 'rm -f "$installer" "$manifest"' EXIT
curl --fail --location --output "$installer" "${base}/TrinaxAI-${version}-installer.sh"
curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
expected="$(awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$installer" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$installer" | awk '{print $1}')"; else echo "Se necesita una herramienta SHA-256 (sha256sum o shasum)." >&2; exit 2; fi
if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Falló la verificación SHA-256 del instalador." >&2; exit 1; fi
bash -n "$installer"
bash "$installer" --dry-run
bash "$installer"

cd "$HOME/Library/Application Support/TrinaxAI"
./update.sh --dry-run
./update.sh
./uninstall.sh --dry-run
./uninstall.sh
```

Para eliminar de forma destructiva los datos de ejecución, modelos, certificados y Ollama, usa `./uninstall.sh --purge` solo después de confirmar que tienes una copia de seguridad.

Verifica la instalación real con `ollama list`, `curl -kfsS https://127.0.0.1:3333/health`, el enlace local y el enlace LAN desde otro dispositivo de la misma red.

## Prueba avanzada de scripts: máquina real con Windows

Ejecuta PowerShell con el usuario que utilizará TrinaxAI. El instalador puede solicitar permisos de administrador para las reglas del firewall.

```powershell
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process Bypass
$version = "1.2.1"
$base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
$installer = Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"
$manifest = Join-Path $env:TEMP "TrinaxAI-$version-SHA256SUMS"
Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer
Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
$line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1
$expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Falló la verificación SHA-256 del instalador." }
Get-Content -Path $installer
& $installer
```

Para una simulación segura desde un script descargado:

```powershell
$ErrorActionPreference = "Stop"
$version = "1.2.1"
$base = "https://github.com/TrinaxCode/TrinaxAI/releases/download/v$version"
$installer = Join-Path $env:TEMP "TrinaxAI-$version-installer.ps1"
$manifest = Join-Path $env:TEMP "TrinaxAI-$version-SHA256SUMS"
Invoke-WebRequest -Uri "$base/TrinaxAI-$version-installer.ps1" -OutFile $installer
Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $manifest
$line = Get-Content -LiteralPath $manifest | Where-Object { $_ -match "\s\*?TrinaxAI-$version-installer\.ps1$" } | Select-Object -First 1
$expected = if ($line -match '^\s*([0-9a-fA-F]{64})\s+') { $Matches[1] } else { "" }
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ine $expected) { throw "Falló la verificación SHA-256 del instalador." }
powershell -NoProfile -ExecutionPolicy Bypass -File $installer -DryRun
```

Después de instalar, ejecuta desde el directorio de instalación:

```powershell
.\update.ps1 -DryRun
.\update.ps1
.\uninstall.ps1 -DryRun
.\uninstall.ps1
```

Si falla la instalación automática de Ollama, se abre el instalador oficial `OllamaSetup.exe`. Pulsa `Install`, espera a que termine y luego pulsa Enter en la ventana del instalador. Confirma el resultado con `Get-Command ollama` y `& (Get-Command ollama).Source list`.

## GitHub Actions

`.github/workflows/test-installers.yml` ejecuta comprobaciones de sintaxis y dry-run en los runners fijados `ubuntu-24.04`, `macos-15` y `windows-2025`. No instala Ollama ni intenta emular otro sistema operativo. El workflow de release publica archivos fuente e instaladores por URL y verifica cada URL publicada.

## Evaluación de calidad RAG

El gate obligatorio de CI es determinista y no pretende demostrar calidad del
modelo:

```bash
python scripts/evaluate_rag.py --deterministic --output rag-eval-report.json
```

Para obtener evidencia real, inicia Ollama y el backend de TrinaxAI; después
sube e indexa el fixture heterogéneo mediante la API pública antes de evaluarlo:

```bash
python scripts/evaluate_rag.py \
  --golden tests/fixtures/rag_live_golden.json \
  --api-url http://127.0.0.1:3333 \
  --index-corpus tests/fixtures/rag_eval/corpus \
  --collection-id rag-eval \
  --embed-model qwen3-embedding:0.6b \
  --timeout 900 \
  --output live-backend-rag-report.json
```

Como alternativa, con el corpus golden completo ya indexado en `rag-eval`, ejecuta:

```bash
make rag-eval RAG_API_URL=http://127.0.0.1:3333
```

El comando live falla si recuperación, fundamentación, citas o abstención quedan
por debajo de los umbrales. El job manual `Live backend RAG` de GitHub Actions
recorre esta ruta completa con Ollama; es opt-in porque las descargas de modelos
y la inferencia dependen del hardware.

## Comprobaciones de documentación

Para cambios solo documentales, ejecuta las comprobaciones mínimas relevantes y
la prueba de Docs de la PWA:

```bash
cd chat-pwa
npx vitest run src/components/Docs.test.tsx
npx tsc --noEmit
cd ..
git diff --check
```

Revisa manualmente los destinos locales de Markdown después de mover un archivo.
Mantén alineados los equivalentes en inglés y `.es.md`, comprueba cada comando
contra el código actual en lugar de copiar un ejemplo antiguo y confirma que la
guía de recuperación coincida con las acciones expuestas por `api_errors.ts` y
`MessageList.tsx`.
