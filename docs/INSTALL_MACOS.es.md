# TrinaxAI en macOS

[English](INSTALL_MACOS.md)

Guía para instalar, configurar, iniciar y dejar listo TrinaxAI en macOS, tanto Apple Silicon como Intel.

## Estado de soporte

El instalador de macOS está disponible y el CI ahora valida tests Python, smoke tests de CLI y sintaxis bash en macOS. La validación end-to-end del instalador en hardware macOS real sigue pendiente.

## Qué queda funcionando

Al terminar deberías tener:

- Ollama corriendo localmente en `http://localhost:11434`.
- API RAG de TrinaxAI en `https://localhost:3333` cuando existe el certificado administrado (HTTP es el fallback).
- PWA en `https://localhost:3334`.
- Entorno Python `.venv` preparado.
- Dependencias de la PWA instaladas.
- Modelos base descargados si eliges esa opción.
- `.env` generado.
- Autoarranque opcional con LaunchAgent: la PWA vuelve al iniciar el equipo y la IA respeta si quedo encendida o apagada.

## Requisitos

| Recurso | Mínimo | Recomendado |
|---|---:|---:|
| macOS | Versión moderna soportada por Homebrew/Ollama | Última estable |
| RAM | 8 GB | 16 GB o más |
| Disco libre | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 22 | 24 LTS |
| Homebrew | Recomendado | Si |
| Ollama | Sí | Última versión |

Apple Silicon usa Metal automáticamente a través de Ollama cuando el modelo lo permite.

## Instalación gráfica recomendada

1. [Descarga el Gestor de TrinaxAI para macOS](https://github.com/TrinaxCode/TrinaxAI/releases/download/v1.2.0/TrinaxAI-Manager-macOS.dmg).
2. Abre la imagen de disco, arrastra **Gestor de TrinaxAI** a Aplicaciones y ábrelo.
3. Pulsa **Instalar** y espera a que termine el proceso.

El Gestor descarga y configura TrinaxAI directamente. No necesitas Git ni comandos de terminal. macOS puede solicitar tu contraseña o confirmación para abrir la aplicación descargada; acéptala y mantén abierta la ventana de progreso. Usa el mismo Gestor después para **Actualizar** o **Desinstalar**. También hay un ZIP portátil en la página del release.

Si Gatekeeper informa que el desarrollador es desconocido, verifica el archivo y
`SHA256SUMS` con las [notas de firma del release](RELEASE_SIGNING.es.md) antes
de decidir si continúas. No desactives Gatekeeper globalmente.

## Avanzado: instalar herramientas base manualmente

Instala Xcode Command Line Tools:

```bash
xcode-select --install
```

Instala Homebrew si no lo tienes:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Instala dependencias:

```bash
brew install python@3.12 node curl ollama
```

También puedes instalar Ollama desde la app oficial para macOS y dejarla abierta.

## Alternativa avanzada por terminal

Si ya tienes el repositorio:

```bash
cd /ruta/a/TrinaxAI
bash install.sh
```

Si todavia no lo tienes, el instalador de un comando lo guarda en `~/Library/Application Support/TrinaxAI`:

```bash
installer="$(mktemp)"
trap 'rm -f "$installer"' EXIT
curl --fail --location --output "$installer" "https://github.com/TrinaxCode/TrinaxAI/releases/download/v1.2.0/TrinaxAI-1.2.0-installer.sh"
bash -n "$installer"
less "$installer"
bash "$installer"
```

El instalador detecta RAM, crea `.env`, prepara Python e instala la PWA automáticamente. Las opciones como descargar modelos, autoarranque e iniciar servicios se preguntan por defecto. La configuración legacy de sistema por LAN se acepta por compatibilidad, pero nunca concede administración remota del host. Usa `bash install.sh --non-interactive` para instalaciones automatizadas.

El perfil se elige automáticamente según CPU, RAM, GPU y VRAM. En modo interactivo, elige `Normal` para usar el perfil recomendado. Usa `Advanced` solo si quieres forzar `8gb`, `16gb`, `32gb` o `64gb`.

La administracion posterior funciona desde cualquier carpeta:

```bash
trinaxai doctor
trinaxai update
trinaxai uninstall
```

## Instalación manual

### 1. Descargar el proyecto

```bash
mkdir -p ~/trinaxai
curl -fsSL https://github.com/TrinaxCode/TrinaxAI/releases/download/v1.2.0/TrinaxAI-1.2.0.tar.gz | tar -xz --strip-components=1 -C ~/trinaxai
cd ~/trinaxai
```

### 2. Crear entorno Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements.lock
```

### 3. Instalar la PWA

```bash
cd chat-pwa
npm ci
npm run build
cd ..
```

### 4. Iniciar Ollama

Si instalaste Ollama con Homebrew:

```bash
ollama serve
```

Deja ese proceso abierto o usa el autoarranque de TrinaxAI. Si instalaste la app oficial de Ollama, abre la app y verifica:

```bash
ollama list
```

### 5. Crear `.env`

```bash
cp .env.example .env
```

Valores recomendados:

```bash
TRINAXAI_PROFILE=16gb
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

```bash
trinaxai network refresh
```

Usa desde el teléfono la URL por IP que muestra; la URL `.local` es una alternativa cuando mDNS funciona en el router.

## Descargar modelos

Perfil `16gb` recomendado:

```bash
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
```

Para los demás perfiles, consulta la
[tabla vigente de modelos y perfiles](../README.es.md#modelos-y-perfiles-de-hardware). El
instalador selecciona y descarga automáticamente la flota de texto/RAG. La visión
se descarga al analizar la primera imagen.

## Indexar tus archivos

```bash
cd ~/trinaxai
source .venv/bin/activate
python index.py
```

También puedes hacerlo desde la PWA en configuración: elige una carpeta, asígnala a una colección y espera a que termine el progreso de subida/indexación.

macOS puede pedir permiso para acceder a carpetas como Documents, Desktop o Downloads. Acepta el permiso si quieres indexar esas ubicaciones.

## Iniciar TrinaxAI

```bash
cd ~/trinaxai
./startup_ai.sh
```

Alternativa:

```bash
.venv/bin/python service_manager.py start --base-dir "$PWD"
```

El gateway escucha en loopback por defecto. Para un acceso LAN intencional,
establece `TRINAXAI_PWA_HOST=0.0.0.0` en `.env`, reinicia TrinaxAI y vincula el
navegador remoto antes de usarlo.

Abre:

```text
https://localhost:3334
```

Desde teléfono/tablet en la misma WiFi:

```text
https://TU-IP-LAN:3334
```

Si el navegador informa que el certificado no es confiable, instala la CA pública
que muestra `trinaxai network` y confía en ella en ese dispositivo. No omitas la
advertencia en una conexión LAN; consulta [pairing LAN y confianza HTTPS](NETWORK_PAIRING.es.md).

## Apagar, reiniciar y revisar estado

Apagar IA y dejar la PWA disponible:

```bash
./shutdown_ai.sh
```

Apagar todo:

```bash
.venv/bin/python service_manager.py stop-all --base-dir "$PWD"
```

Esto deja solo la página de recuperación por loopback en `https://localhost:3334`; el acceso LAN permanece cerrado hasta iniciar TrinaxAI allí.

Ver estado:

```bash
.venv/bin/python service_manager.py status --base-dir "$PWD"
```

Supervisor manual:

```bash
.venv/bin/python service_manager.py watch --base-dir "$PWD"
```

## Autoarranque en macOS

El instalador lo habilita automáticamente. TrinaxAI usa un LaunchAgent en `~/Library/LaunchAgents/`. El supervisor siempre intenta mantener la PWA disponible; si apagaste la IA con `./shutdown_ai.sh` o desde la PWA, el siguiente arranque no levanta Ollama/RAG hasta que vuelvas a encender la IA.

Habilitar:

```bash
cd ~/trinaxai
.venv/bin/python service_manager.py enable-autostart --base-dir "$PWD"
```

Deshabilitar:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

Verificar con `launchctl`:

```bash
launchctl list | grep trinax
```

Logs:

```bash
tail -f logs/supervisor.log
tail -f logs/rag_api.log
tail -f logs/frontend.log
```

## Verificar que todo funciona

```bash
cd ~/trinaxai
.venv/bin/python test_system.py --verbose
```

Pruebas manuales:

```bash
curl http://localhost:11434/api/tags
curl -k https://localhost:3333/health
```

La PWA debe abrir en:

```text
https://localhost:3334
```

## Uso diario

1. Abre `https://localhost:3334`.
2. Usa Ollama para chat general.
3. Usa RAG para preguntar sobre carpetas y colecciones indexadas.
4. Instala la PWA desde Chrome/Edge o agregala a pantalla de inicio desde Safari en iPhone/iPad.

## Actualizar

```bash
cd ~/trinaxai
./update.sh
```

El actualizador pregunta si quieres crear backup, descargar código nuevo, actualizar modelos, cambiar autoarranque, reiniciar servicios y correr la auditoría. Las dependencias Python/npm y el build de la PWA siguen siendo automáticos.

El instalador crea un LaunchAgent semanal solo de comprobación. Registra
disponibilidad en `logs/auto-update.log`, pero nunca descarga/ejecuta un updater
ni cambia la instalación. Revisa el release y ejecuta manualmente el updater
local; desactívalo con `python scripts/auto_update.py disable`.

## Copias de seguridad

```bash
./backup.sh create
```

El archivo se publica con modo `0600` y contiene `.env`, chats, adjuntos,
fuentes e índices. Cifra copias fuera del host. La restauración valida
rutas/tipos, extrae a staging y revierte un reemplazo fallido; pruébala antes de
actualizar.

Datos importantes:

- `.env`
- `storage/`
- `local_sources/`

## Desinstalar

```bash
./uninstall.sh
```

El desinstalador pregunta qué archivos runtime quieres quitar. Los datos RAG y modelos de Ollama se conservan salvo que elijas borrarlos.

Para dejar preseleccionada la opción de quitar también los modelos:

```bash
./uninstall.sh --remove-models
```

Si habilitaste autoarranque:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

## Problemas comunes

| Problema | Solución |
|---|---|
| `brew` no existe | Instala Homebrew y abre una terminal nueva. |
| `python3` apunta a una versión antigua | Instala `python@3.12` y usa `python3.12 -m venv .venv`. |
| Ollama no responde | Abre la app Ollama o ejecuta `ollama serve`. |
| macOS bloquea acceso a carpetas | Revisa Ajustes del Sistema > Privacidad y seguridad > Archivos y carpetas. |
| La PWA no conecta desde iPhone | Ejecuta `trinaxai network refresh`, abre la URL `https://HOST-LAN-IP:3334` que muestra y permite el gateway en la red privada. |
| Certificado no confiable | Instala/confía en la CA pública que muestra `trinaxai network`; no omitas TLS en una LAN. Consulta [pairing LAN y confianza HTTPS](NETWORK_PAIRING.es.md). |
| Respuestas lentas | Usa la matriz de modelos/perfiles del README raíz, reduce la concurrencia o elige `8gb`/un modelo instalado más pequeño. |

## Seguridad

Mantén FastAPI `3333` y Ollama `11434` en loopback; expón solo el gateway PWA
en `3334` dentro de una red privada confiable. No expongas estos puertos a
Internet. Para acceso remoto usa VPN. La administración del sistema siempre
queda solo en localhost; la variable legacy se acepta para `.env` antiguos,
pero nunca concede autoridad por LAN:

```bash
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=un-token-largo
```
