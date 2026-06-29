# TrinaxAI en Linux

Guia para instalar, configurar, iniciar y dejar listo TrinaxAI en Linux. Aplica para Ubuntu, Debian, Fedora, Arch, openSUSE y distribuciones similares.

## Que queda funcionando

Al terminar deberias tener:

- Ollama corriendo localmente en `http://localhost:11434`.
- API RAG de TrinaxAI en `https://localhost:3333`.
- PWA de TrinaxAI en `https://localhost:3334`.
- Modelos base descargados.
- Entorno Python `.venv` instalado.
- Dependencias del frontend instaladas.
- `.env` generado con el perfil de tu equipo.
- Autoarranque de usuario con systemd: la PWA vuelve al iniciar el equipo y la IA respeta si quedo encendida o apagada.

## Requisitos

| Recurso | Minimo | Recomendado |
|---|---:|---:|
| RAM | 8 GB | 16 GB o mas |
| Disco libre | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 18 | 20 LTS |
| Git | Si | Si |
| Ollama | Si | Ultima version |

Si usas NVIDIA, instala los drivers antes de descargar modelos grandes. TrinaxAI tambien funciona solo con CPU, pero las respuestas seran mas lentas.

## Instalacion automatica recomendada

Desde una terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash
```

El instalador clona el proyecto en `~/trinaxai` si todavia no existe, detecta tu RAM, crea `.env`, instala dependencias, prepara la PWA, descarga los modelos recomendados, habilita autoarranque e inicia TrinaxAI. Usa `./install.sh --interactive` si quieres preguntas manuales.

Si ya clonaste el repositorio:

```bash
cd /ruta/a/TrinaxAI
chmod +x install.sh
./install.sh
```

El perfil se elige automaticamente. En modo interactivo, elige `Normal` salvo que sepas que quieres un perfil manual:

- `8gb`: equipos con poca memoria.
- `16gb`: perfil equilibrado.
- `max`: mas RAM/CPU, modelos mas grandes.
- `ultra`: 32 GB+ y hardware potente.

## Instalacion manual

Usa estos pasos si prefieres revisar cada parte.

### 1. Instalar dependencias del sistema

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv curl git unzip nodejs npm
```

Fedora:

```bash
sudo dnf install -y python3 python3-pip curl git unzip nodejs npm
```

Arch:

```bash
sudo pacman -Sy --needed python python-pip curl git unzip nodejs npm
```

openSUSE:

```bash
sudo zypper install python3 python3-pip curl git unzip nodejs npm
```

### 2. Clonar el proyecto

```bash
git clone https://github.com/TrinaxCode/TrinaxAI.git ~/trinaxai
cd ~/trinaxai
```

### 3. Crear el entorno Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Instalar la PWA

```bash
cd chat-pwa
npm install
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

Valores recomendados para empezar:

```bash
TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=0.0.0.0
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_ALLOW_LAN_SYSTEM=1
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=0.0.0.0
VITE_TRINAXAI_RAG_TARGET=https://localhost:3333
```

Si vas a abrir TrinaxAI desde un telefono en la misma red, agrega tu IP local a `TRINAXAI_CORS_ORIGINS`:

```bash
hostname -I
```

Ejemplo:

```bash
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://192.168.1.25:3334,http://192.168.1.25:3334
```

## Descargar modelos

Modelos base:

```bash
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull bge-m3
```

Vision:

```bash
ollama pull qwen2.5vl:3b
```

Equipos con mas memoria:

```bash
ollama pull qwen2.5-coder:7b
```

Perfil ultra:

```bash
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5vl:7b
```

## Indexar tus archivos

El indexado crea la base de conocimiento local que usa RAG.

```bash
cd ~/trinaxai
source .venv/bin/activate
python index.py
```

Tambien puedes indexar desde la PWA: abre `https://localhost:3334`, ve a configuracion, elige una carpeta y asignala a una coleccion.

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

Abrir:

```text
https://localhost:3334
```

Desde telefono o tablet en la misma WiFi:

```text
https://TU-IP-LAN:3334
```

Acepta la advertencia del certificado si aparece. Es un certificado local/autofirmado.

## Apagar, reiniciar y revisar estado

Apagar solo los servicios de IA, dejando la PWA disponible:

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

Supervisor en primer plano:

```bash
.venv/bin/python service_manager.py watch --base-dir "$PWD"
```

## Autoarranque

El instalador lo habilita automaticamente. El supervisor siempre intenta mantener la PWA disponible; si apagaste la IA con `./shutdown_ai.sh` o desde la PWA, el siguiente arranque no levanta Ollama/RAG hasta que vuelvas a encender la IA.

### Opcion segura por usuario

Esta opcion crea un servicio systemd de usuario y no requiere escribir en `/etc`:

```bash
cd ~/trinaxai
.venv/bin/python service_manager.py enable-autostart --base-dir "$PWD"
```

Desactivar:

```bash
.venv/bin/python service_manager.py disable-autostart --base-dir "$PWD"
```

### Opcion avanzada con systemd de sistema

`setup_trinaxai.sh` es solo para Linux. Crea unidades systemd en `/etc/systemd/system`, configura Ollama y agrega una regla sudoers para permitir iniciar/apagar desde la PWA sin pedir contrasena.

Ejecutalo solo si entiendes ese cambio de permisos:

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

Tambien puedes revisar manualmente:

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
7. Usa frases como `recuerda que...` para guardar memoria local explicita.

## Actualizar

```bash
cd ~/trinaxai
./backup.sh create
./update.sh
```

Si actualizas manualmente:

```bash
git pull
source .venv/bin/activate
python -m pip install -r requirements.txt
cd chat-pwa
npm install
npm run build
cd ..
```

## Copias de seguridad

Crear backup:

```bash
./backup.sh create
```

Respaldar manualmente lo importante:

- `.env`
- `storage/`
- `local_sources/`

## Desinstalar

```bash
./uninstall.sh
```

Tambien quitar modelos de Ollama:

```bash
./uninstall.sh --remove-models
```

## Puertos y firewall

| Puerto | Servicio | Uso |
|---:|---|---|
| 11434 | Ollama | Modelos locales |
| 3333 | RAG API | Backend FastAPI |
| 3334 | PWA | Interfaz web |

Si usaras telefono/tablet, permite `3333` y `3334` solo en tu red privada. No expongas estos puertos a internet.

Ollama no trae autenticacion integrada. Si `OLLAMA_HOST=0.0.0.0`, otros dispositivos de tu LAN podrian usar tus modelos. Para acceso remoto, usa VPN como Tailscale o WireGuard.

## Problemas comunes

| Problema | Solucion |
|---|---|
| `python3 -m venv` falla | Instala `python3-venv`. |
| PWA no abre | Ejecuta `cd chat-pwa && npm run dev`. |
| API no responde | Ejecuta `./startup_ai.sh` y revisa `logs/rag_api.log`. |
| Modelo no encontrado | Ejecuta `ollama pull nombre-del-modelo`. |
| Telefono no conecta | Agrega tu IP LAN a `TRINAXAI_CORS_ORIGINS` y revisa firewall. |
| Certificado no confiable | Acepta la advertencia para uso local. |
| Respuestas lentas | Usa modelos mas pequenos o un perfil menor con `TRINAXAI_PROFILE=8gb ./install.sh`. |
