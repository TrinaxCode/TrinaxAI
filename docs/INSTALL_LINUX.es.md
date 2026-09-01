<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🐧 Instalación en Linux
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="INSTALL_LINUX.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

Guía para instalar, configurar, iniciar y dejar listo TrinaxAI en Linux. Aplica para Ubuntu, Debian, Fedora, Arch, openSUSE y distribuciones similares.

## Estado de soporte

Linux es la plataforma principal validada por CI. El CI actual valida tests backend, tests/build frontend, smoke tests de CLI, public-readiness y sintaxis shell en Ubuntu. La validación end-to-end del instalador en todas las distribuciones listadas sigue pendiente.

## Qué queda funcionando

Al terminar deberías tener:

- Ollama corriendo localmente en `http://localhost:11434`.
- API RAG de TrinaxAI en `https://localhost:3333` cuando existe el certificado administrado (HTTP es el fallback).
- PWA de TrinaxAI en `https://localhost:3334`.
- Modelos base descargados si eliges esa opción.
- Entorno Python `.venv` instalado.
- Dependencias del frontend instaladas.
- `.env` generado con el perfil de tu equipo.
- Autoarranque opcional de usuario con systemd: la PWA vuelve al iniciar el equipo y la IA respeta si quedo encendida o apagada.

## Requisitos

| Recurso | Mínimo | Recomendado |
|---|---:|---:|
| RAM | 8 GB | 16 GB o más |
| Disco libre | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 22 | 24 LTS |
| Ollama | Sí | Última versión |

Si usas NVIDIA, instala los drivers antes de descargar modelos grandes. TrinaxAI también funciona solo con CPU, pero las respuestas serán más lentas.

## Instalación recomendada fijada a un release

> Estado del release: `v1.2.0` es el candidato actual, pero sus assets del Release de GitHub todavía no se han publicado. El comando siguiente queda listo para cuando se publique el release; para probarlo ahora, usa el checkout local con `bash install.sh`. El instalador se niega intencionalmente a caer en `main`.

```bash
set -eu
version="1.2.0"
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

El instalador descarga directamente el archivo fuente desde GitHub. No necesita Git, detecta tu hardware, instala las dependencias necesarias, configura Ollama, compila la PWA e inicia TrinaxAI. Acepta la solicitud de contraseña cuando tu distribución la pida para instalar paquetes del sistema.
La comprobación del manifiesto SHA-256 anterior es obligatoria antes de ejecutar. La verificación GPG separada es un control adicional opcional, sólo cuando hayas obtenido y confiado en la huella de la clave de firma por un canal independiente; una clave o huella descargada del mismo release no es un ancla de autenticidad. El repositorio todavía no incluye un ancla de confianza de clave pública fijada.

## Alternativa avanzada por terminal

Desde una terminal:

```bash
set -eu
installer="$(mktemp)"
manifest="$(mktemp)"
trap 'rm -f "$installer" "$manifest"' EXIT
version="1.2.0"
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
curl --fail --location --output "$installer" "${base}/TrinaxAI-${version}-installer.sh"
curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
expected="$(awk -v asset="TrinaxAI-${version}-installer.sh" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$installer" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$installer" | awk '{print $1}')"; else echo "Se necesita una herramienta SHA-256 (sha256sum o shasum)." >&2; exit 2; fi
if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Falló la verificación SHA-256 del instalador." >&2; exit 1; fi
bash -n "$installer"
less "$installer"
bash "$installer"
```

Una instalación nueva se guarda en `$XDG_DATA_HOME/trinaxai` (normalmente `~/.local/share/trinaxai`), manteniendo compatibilidad con instalaciones anteriores en `~/trinaxai`. Para elegir otra ruta, sustituye el último comando del bloque anterior por el siguiente. El instalador detecta tu RAM, crea `.env`, instala dependencias y prepara la PWA.

Usa `./install.sh --no-start` para dejar TrinaxAI detenido; también se omite el inicio automático y podrás activarlo después de iniciar TrinaxAI.

```bash
bash "$installer" --install-dir "/ruta/a/trinaxai"
```

Después puedes administrarla desde cualquier carpeta:

```bash
trinaxai doctor
trinaxai update
trinaxai uninstall
```

`trinaxai uninstall -y` usa opciones seguras y conserva índices y modelos salvo que pidas eliminarlos.

Si ya clonaste el repositorio:

```bash
cd /ruta/a/TrinaxAI
chmod +x install.sh
./install.sh
```

Ejecutar desde un checkout local es un modo de operador/desarrollo y no se bloquea intencionalmente; revisa y protege ese checkout por separado del flujo de descarga de releases verificado.

El perfil se elige automáticamente según CPU, RAM, GPU y VRAM. En modo interactivo, elige `Normal` salvo que sepas que quieres un perfil manual:

- `8gb`: equipos con poca memoria.
- `16gb`: equipos equilibrados.
- `32gb`: más RAM o una GPU capaz.
- `64gb`: memoria abundante o una GPU potente.

## Instalación manual

Usa estos pasos si prefieres revisar cada parte.

### 1. Instalar dependencias del sistema

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv curl unzip nodejs npm
```

Fedora:

```bash
sudo dnf install -y python3 python3-pip curl unzip nodejs npm
```

Arch:

```bash
sudo pacman -Sy --needed python python-pip curl unzip nodejs npm
```

openSUSE:

```bash
sudo zypper install python3 python3-pip curl unzip nodejs npm
```

### 2. Descargar el archivo del release

```bash
set -eu
version="1.2.0"
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/v${version}"
mkdir -p ~/trinaxai
archive="$(mktemp)"
manifest="$(mktemp)"
trap 'rm -f "$archive" "$manifest"' EXIT
curl --fail --location --output "$archive" "${base}/TrinaxAI-${version}.tar.gz"
curl --fail --location --output "$manifest" "${base}/SHA256SUMS"
expected="$(awk -v asset="TrinaxAI-${version}.tar.gz" '$2 == asset || $2 == "*" asset { print $1; exit }' "$manifest")"
if command -v sha256sum >/dev/null 2>&1; then actual="$(sha256sum "$archive" | awk '{print $1}')"; elif command -v shasum >/dev/null 2>&1; then actual="$(shasum -a 256 "$archive" | awk '{print $1}')"; else echo "Se necesita una herramienta SHA-256 (sha256sum o shasum)." >&2; exit 2; fi
if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo "Falló la verificación SHA-256 del archivo fuente." >&2; exit 1; fi
tar -xzf "$archive" --strip-components=1 -C ~/trinaxai
cd ~/trinaxai
```

### 3. Crear el entorno Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements.lock
```

### 4. Instalar la PWA

```bash
cd chat-pwa
npm ci
npm run build
cd ..
```

### 5. Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verifica que responda:

```bash
ollama --version
ollama list
```

### 6. Crear `.env`

Puedes copiar la plantilla:

```bash
cp .env.example .env
```

Valores recomendados para empezar (deja el perfil automático salvo que necesites sobrescribirlo):

```bash
# Déjalo sin definir para detectar CPU/RAM/GPU.
#TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=127.0.0.1
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=./local_sources
# Valor de compatibilidad obsoleto; la administración del host siempre es solo localhost.
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
TRINAXAI_RAG_HTTPS=1
TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=https://127.0.0.1:3333
```

Si cambias de red o quieres conectar un teléfono en el mismo Wi-Fi, deja que TrinaxAI renueve la dirección local y el certificado HTTPS:

```bash
trinaxai network refresh
```

Abre la URL por IP que muestra. La URL `.local` es una alternativa cuando mDNS funciona en el router. Una PWA cacheada en la IP anterior es una copia offline, no otra instalación activa.

## Descargar modelos

Perfil `16gb` recomendado:

```bash
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
```

Para `8gb`, `32gb` y `64gb`, usa la flota vigente de la
[tabla de modelos y perfiles](../README.es.md#modelos-y-perfiles-de-hardware). El instalador
descarga el conjunto de texto/RAG. La visión se descarga al analizar la primera
imagen; los pulls manuales solo hacen falta en configuraciones personalizadas.

## Indexar tus archivos

El indexado crea la base de conocimiento local que usa RAG.

```bash
cd ~/trinaxai
source .venv/bin/activate
python index.py
```

También puedes indexar desde la PWA: abre `https://localhost:3334`, ve a configuración, elige una carpeta y asígnala a una colección.

Los archivos importados desde navegador se copian a `local_sources/collections/`. El navegador no entrega la ruta absoluta original por seguridad.

## Iniciar TrinaxAI

Camino recomendado:

```bash
cd ~/trinaxai
./startup_ai.sh
```

Alternativa directa:

```bash
.venv/bin/python service_manager.py start --base-dir "$PWD"
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

Apagar solo los servicios de IA, dejando la PWA disponible:

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

Supervisor en primer plano:

```bash
.venv/bin/python service_manager.py watch --base-dir "$PWD"
```

## Autoarranque

El instalador lo habilita automáticamente. El supervisor siempre intenta mantener la PWA disponible; si apagaste la IA con `./shutdown_ai.sh` o desde la PWA, el siguiente arranque no levanta Ollama/RAG hasta que vuelvas a encender la IA.

### Opción segura por usuario

Esta opción crea un servicio systemd de usuario y no requiere escribir en `/etc`:

```bash
cd ~/trinaxai
.venv/bin/python service_manager.py enable-autostart --base-dir "$PWD"
```

Desactivar:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

### Opción avanzada con systemd de sistema

`setup_trinaxai.sh` es solo para Linux. Crea unidades systemd en `/etc/systemd/system`, configura Ollama y agrega una regla sudoers para permitir iniciar/apagar desde la PWA sin pedir contraseña.

Ejecútalo solo si entiendes ese cambio de permisos:

```bash
cd ~/trinaxai
sudo ./setup_trinaxai.sh
```

Revisar servicios:

```bash
systemctl status ollama
systemctl status ai-rag
systemctl status trinaxai-frontend
```

Logs:

```bash
journalctl -u ai-rag -f
journalctl -u trinaxai-frontend -f
```

## Verificar que todo funciona

```bash
cd ~/trinaxai
.venv/bin/python test_system.py --verbose
```

También puedes revisar manualmente:

```bash
curl http://localhost:11434/api/tags
curl -k https://localhost:3333/health
```

La PWA debe abrir en:

```text
https://localhost:3334
```

## Uso diario

1. Inicia TrinaxAI con `./startup_ai.sh` o deja autoarranque habilitado.
2. Abre `https://localhost:3334`.
3. Usa modo Ollama para chat general.
4. Usa modo RAG para preguntas sobre tus archivos indexados.
5. Crea colecciones para separar proyectos o temas.
6. Adjunta archivos temporales si no quieres indexarlos.
7. Usa frases como `recuerda que...` para guardar memoria local explícita.

## Backend opcional con Docker

Esta primera etapa containeriza únicamente la API RAG. La PWA, el gateway de
seguridad y Ollama siguen ejecutándose en el host.

Requisitos: Docker Compose y Ollama instalado en el host.

```bash
cd ~/trinaxai
cp .env.example .env
mkdir -p projects storage local_sources
```

En `.env`, cambia el destino de la API a HTTP porque el contenedor no termina
TLS:

```dotenv
TRINAXAI_RAG_TARGET=http://127.0.0.1:3333
VITE_TRINAXAI_RAG_TARGET=http://127.0.0.1:3333
```

Después inicia solo el gateway PWA del host y la API en Docker:

```bash
export TRINAXAI_DOCKER_UID="$(id -u)"
export TRINAXAI_DOCKER_GID="$(id -g)"
export TRINAXAI_DOCKER_IMAGE=ghcr.io/trinaxcode/trinaxai:1.2.0
docker compose pull
docker compose up --no-build -d
.venv/bin/python service_manager.py start-frontend --base-dir "$PWD"
```

El registro también publica las etiquetas `1.2`, `1` y `latest`. Fija `1.2.0`
para un despliegue reproducible. Para construir el checkout actual, omite
`TRINAXAI_DOCKER_IMAGE` y ejecuta `docker compose up --build -d`.

La API queda publicada solo en `127.0.0.1:3333`, por lo que la PWA nativa puede
seguir usando su gateway en `3334`. Los índices, fuentes y secretos permanecen
en `storage/` y `local_sources/` mediante montajes persistentes.

Por defecto, el contenedor busca Ollama en
`http://host.docker.internal:11434`. En Linux, Ollama debe aceptar conexiones
desde la red de Docker; configura su bind de forma consciente y limita el
acceso con el firewall. Compose usa la subred privada `172.31.0.0/24` para
transportar la identidad HMAC; si ya está ocupada, cambia
`TRINAXAI_DOCKER_NETWORK_CIDR` por otra subred privada libre. Para otra
dirección de Ollama:

```bash
TRINAXAI_DOCKER_OLLAMA_URL=http://host.docker.internal:11434 \
  docker compose up --no-build -d
```

La carpeta indexada por el contenedor es `./projects` en modo lectura. Para
usar otra carpeta del host, define `TRINAXAI_DOCKER_INDEX_DIR` antes de iniciar:

```bash
TRINAXAI_DOCKER_INDEX_DIR=/ruta/a/documentos docker compose up --no-build -d
```

Comprobar estado y detenerlo:

```bash
curl http://127.0.0.1:3333/health
docker compose ps
docker compose down
```

Este perfil no containeriza todavía la PWA ni Ollama, y no debe exponerse el
puerto `3333` fuera del host. No uses `startup_ai.sh` ni `start-ai` mientras
este Compose esté activo: intentarían iniciar otra API en el mismo puerto.

El archivo `.env` es opcional para Compose. Si no existe, se usan los valores
seguros de `compose.yaml`; añádelo solo cuando necesites sobrescribir la configuración.

## Actualizar

```bash
cd ~/trinaxai
./update.sh
```

El actualizador pregunta si quieres crear backup, descargar código nuevo, actualizar modelos, cambiar autoarranque, reiniciar servicios y correr la auditoría. Las dependencias Python/npm y el build de la PWA siguen siendo automáticos.

El instalador activa un timer que comprueba GitHub semanalmente y registra si
hay una actualización en `logs/auto-update.log`. Es solo comprobación: no
descarga/ejecuta un updater ni modifica servicios. Revisa el release etiquetado
y ejecuta manualmente el actualizador local guiado. Desactívalo con
`python scripts/auto_update.py disable`.

## Copias de seguridad

Crear backup:

```bash
./backup.sh create
```

El archivo se publica con modo `0600` y contiene `.env`, chats, adjuntos,
fuentes e índices privados. Cifra toda copia fuera del host. La restauración
valida rutas y tipos, extrae a staging y revierte un reemplazo fallido; aun así
pruébala antes de actualizar.

Respaldar manualmente lo importante:

- `.env`
- `storage/`
- `local_sources/`

## Desinstalar

```bash
./uninstall.sh
```

El desinstalador pregunta qué archivos runtime quieres quitar. Los datos RAG y modelos de Ollama se conservan salvo que elijas borrarlos.

Para dejar preseleccionada la opción de quitar modelos de Ollama:

```bash
./uninstall.sh --remove-models
```

## Puertos y firewall

| Puerto | Servicio | Uso |
|---:|---|---|
| 11434 | Ollama | Modelos locales |
| 3333 | RAG API | Backend FastAPI |
| 3334 | PWA | Interfaz web |

Si usas teléfono o tablet, permite solo el gateway PWA en `3334` dentro de tu
red privada. Mantén FastAPI `3333` y Ollama `11434` en loopback; no los expongas
a la LAN ni a Internet.

Ollama no trae autenticación integrada. Si `OLLAMA_HOST=0.0.0.0`, otros dispositivos de tu LAN podrían usar tus modelos. Para acceso remoto, usa una VPN como Tailscale o WireGuard.

## Problemas comunes

| Problema | Solución |
|---|---|
| `python3 -m venv` falla | Instala `python3-venv`. |
| PWA no abre | Ejecuta `cd chat-pwa && npm run dev`. |
| API no responde | Ejecuta `./startup_ai.sh` y revisa `logs/rag_api.log`. |
| Modelo no encontrado | Ejecuta `ollama pull nombre-del-modelo`. |
| El teléfono no conecta | Ejecuta `trinaxai network refresh`, abre la URL `https://HOST-LAN-IP:3334` que muestra y permite solo el gateway en el firewall de red privada. |
| Certificado no confiable | Instala/confía en la CA pública que muestra `trinaxai network`; no omitas TLS en una LAN. Consulta [pairing LAN y confianza HTTPS](NETWORK_PAIRING.es.md). |
| Respuestas lentas | Usa la matriz de modelos/perfiles del README raíz, reduce la concurrencia o elige `8gb`/un modelo instalado más pequeño. |
