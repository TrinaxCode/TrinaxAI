# Pruebas de instaladores

[English](TESTING.md)

Estas comprobaciones se dividen entre pruebas del Gestor, simulaciones de scripts y pruebas en máquinas reales. El modo dry-run nunca descarga el paquete de código ni Ollama, instala paquetes, inicia servicios, modifica `PATH`, edita launch agents ni elimina archivos.

## Prueba rápida del Gestor gráfico

Prueba primero el recorrido normal del usuario:

1. Descarga el paquete del Gestor para el sistema objetivo desde el [release de TrinaxAI 1.2.0](https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0).
   Usa el `.exe` en Windows, `.dmg` en macOS o `.deb` en Debian/Ubuntu. Los ZIP/TAR.GZ portátiles se publican junto con ellos.
2. Ábrelo y pulsa **Instalar**. Confirma que no sea necesario copiar ni escribir comandos.
3. Vuelve a abrirlo y prueba **Actualizar** y después **Desinstalar**.
4. Confirma que Git no se instale ni se solicite y que el perfil detectado sea `8gb`, `16gb`, `32gb` o `64gb`.

Las comprobaciones por comandos siguientes validan los scripts alternativos avanzados; no son las instrucciones normales de instalación.

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
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh -o /tmp/trinaxai-install.sh
bash /tmp/trinaxai-install.sh --dry-run
bash /tmp/trinaxai-install.sh

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
Set-ExecutionPolicy -Scope Process Bypass
$installer = Join-Path $env:TEMP "trinaxai-install.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.ps1" -OutFile $installer
Get-Content -Path $installer
& $installer
```

Para una simulación segura desde un script descargado:

```powershell
irm https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.ps1 -OutFile "$env:TEMP\trinaxai-install.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\trinaxai-install.ps1" -DryRun
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

`.github/workflows/test-installers.yml` ejecuta comprobaciones de sintaxis y dry-run en `ubuntu-latest`, `macos-latest` y `windows-latest`, y compila/empaqueta el artefacto smoke del Gestor de Windows. No instala Ollama ni intenta emular otro sistema operativo. El workflow de release compila los tres paquetes nativos y los formatos portátiles en sus runners nativos y verifica cada URL publicada.

## Evaluación de calidad RAG

Con la API en ejecución y el corpus golden indexado en `rag-eval`, ejecuta la
misma evaluación reproducible de los checks de release:

```bash
make rag-eval RAG_API_URL=http://127.0.0.1:3333
```

El comando escribe `rag-eval-report.json` y falla si recuperación,
fundamentación, citas o abstención quedan por debajo de los umbrales. Requiere
intencionadamente una API indexada en vivo; validar el fixture por sí solo no
es una afirmación de calidad del modelo.

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
