# TrinaxAI en macOS

Guía para instalar, configurar, iniciar y dejar listo TrinaxAI en macOS, tanto Apple Silicon como Intel.

## Estado de soporte

El instalador de macOS esta disponible y el CI ahora valida tests Python, smoke tests de CLI y sintaxis bash en macOS. La validacion end-to-end del instalador en hardware macOS real sigue pendiente.

## Que queda funcionando

Al terminar deberias tener:

- Ollama corriendo localmente en `http://localhost:11434`.
- API RAG de TrinaxAI en `http://localhost:3333`.
- PWA en `https://localhost:3334`.
- Entorno Python `.venv` preparado.
- Dependencias de la PWA instaladas.
- Modelos base descargados si eliges esa opcion.
- `.env` generado.
- Autoarranque opcional con LaunchAgent: la PWA vuelve al iniciar el equipo y la IA respeta si quedo encendida o apagada.

## Requisitos

| Recurso | Minimo | Recomendado |
|---|---:|---:|
| macOS | Version moderna soportada por Homebrew/Ollama | Ultima estable |
| RAM | 8 GB | 16 GB o mas |
| Disco libre | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 18 | 20 LTS |
| Homebrew | Recomendado | Si |
| Ollama | Si | Ultima version |

Apple Silicon usa Metal automaticamente a traves de Ollama cuando el modelo lo permite.

## Instalar herramientas base

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
brew install python@3.12 node git curl ollama
```

Tambien puedes instalar Ollama desde la app oficial para macOS y dejarla abierta.

## Instalacion automatica recomendada

Si ya tienes el repositorio:

```bash
cd /ruta/a/TrinaxAI
bash install.sh
```

Si todavia no lo tienes, el instalador de un comando lo guarda en `~/Library/Application Support/TrinaxAI`:

```bash
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash
```

El instalador detecta RAM, crea `.env`, prepara Python e instala la PWA automaticamente. Las opciones como descargar modelos, control LAN, autoarranque e iniciar servicios se preguntan por defecto. Usa `bash install.sh --non-interactive` para instalaciones automatizadas.

El perfil se elige automaticamente. En modo interactivo, elige `Normal` para usar el perfil recomendado. Usa `Advanced` solo si quieres forzar `8gb`, `16gb`, `max` o `ultra`.

La administracion posterior funciona desde cualquier carpeta:

```bash
trinaxai doctor
trinaxai update
trinaxai uninstall
```

## Instalacion manual

### 1. Clonar el proyecto

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git ~/trinaxai
cd ~/trinaxai
```

### 2. Crear entorno Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Instalar la PWA

```bash
cd chat-pwa
npm install
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
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=127.0.0.1
VITE_TRINAXAI_RAG_TARGET=http://localhost:3333
```

Para usar un telefono en la misma WiFi, busca tu IP:

```bash
ipconfig getifaddr en0
```

Si `en0` no devuelve nada:

```bash
ipconfig getifaddr en1
```

Agrega esa IP a `TRINAXAI_CORS_ORIGINS`, por ejemplo:

```bash
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://192.168.1.25:3334,http://192.168.1.25:3334
```

## Descargar modelos

Perfil `16gb` recomendado:

```bash
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3-embedding:0.6b
```

Para los demás perfiles, consulta la
[tabla vigente de modelos y perfiles](../README.es.md#-modelos-y-perfiles). El
instalador selecciona y descarga automáticamente la flota de texto/RAG. Vision
se descarga al analizar la primera imagen.

## Indexar tus archivos

```bash
cd ~/trinaxai
source .venv/bin/activate
python index.py
```

Tambien puedes hacerlo desde la PWA en configuracion: elige una carpeta, asignala a una coleccion y espera a que termine el progreso de subida/indexacion.

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

Abre:

```text
https://localhost:3334
```

Desde telefono/tablet en la misma WiFi:

```text
https://TU-IP-LAN:3334
```

Acepta la advertencia del certificado local si aparece.

## Apagar, reiniciar y revisar estado

Apagar IA y dejar la PWA disponible:

```bash
./shutdown_ai.sh
```

Apagar todo:

```bash
.venv/bin/python service_manager.py stop-all --base-dir "$PWD"
```

Ver estado:

```bash
.venv/bin/python service_manager.py status --base-dir "$PWD"
```

Supervisor manual:

```bash
.venv/bin/python service_manager.py watch --base-dir "$PWD"
```

## Autoarranque en macOS

El instalador lo habilita automaticamente. TrinaxAI usa un LaunchAgent en `~/Library/LaunchAgents/`. El supervisor siempre intenta mantener la PWA disponible; si apagaste la IA con `./shutdown_ai.sh` o desde la PWA, el siguiente arranque no levanta Ollama/RAG hasta que vuelvas a encender la IA.

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
curl http://localhost:3333/health
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

El actualizador pregunta si quieres crear backup, descargar codigo nuevo, actualizar modelos, cambiar autoarranque, reiniciar servicios y correr la auditoria. Las dependencias Python/npm y el build de la PWA siguen siendo automaticos.

El instalador crea un LaunchAgent semanal solo de comprobación. Registra
disponibilidad en `logs/auto-update.log`, pero nunca descarga/ejecuta un updater
ni cambia la instalación. Revisa el release y ejecuta manualmente el updater
local; desactívalo con `python scripts/auto_update.py disable`.

Actualizacion manual:

```bash
git pull
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
cd chat-pwa
npm ci
npm run build
cd ..
```

## Copias de seguridad

```bash
./backup.sh create
```

El archive se publica con modo `0600` y contiene `.env`, chats, adjuntos,
fuentes e índices. Cifra copias off-host. Restore valida rutas/tipos, extrae a
staging y revierte un reemplazo fallido; pruébalo antes de actualizar.

Datos importantes:

- `.env`
- `storage/`
- `local_sources/`

## Desinstalar

```bash
./uninstall.sh
```

El desinstalador pregunta que archivos runtime quieres quitar. Los datos RAG y modelos de Ollama se conservan salvo que elijas borrarlos.

Para dejar preseleccionada la opcion de quitar tambien los modelos:

```bash
./uninstall.sh --remove-models
```

Si habilitaste autoarranque:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

## Problemas comunes

| Problema | Solucion |
|---|---|
| `brew` no existe | Instala Homebrew y abre una terminal nueva. |
| `python3` apunta a una version antigua | Instala `python@3.12` y usa `python3.12 -m venv .venv`. |
| Ollama no responde | Abre la app Ollama o ejecuta `ollama serve`. |
| macOS bloquea acceso a carpetas | Revisa Ajustes del Sistema > Privacidad y seguridad > Archivos y carpetas. |
| PWA no conecta desde iPhone | Asegura misma WiFi, IP LAN en CORS y firewall permitido. |
| Certificado no confiable | Acepta el certificado local para `localhost` o tu IP LAN. |
| Respuestas lentas | Usa modelos 3B o 7B segun RAM disponible. |

## Seguridad

No expongas `3333`, `3334` ni `11434` a internet. Para acceso remoto usa VPN. Si necesitas cerrar acciones de sistema a solo localhost, configura:

```bash
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=un-token-largo
```
