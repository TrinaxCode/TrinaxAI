# TrinaxAI en Windows

Guía para instalar, configurar, iniciar y dejar listo TrinaxAI en Windows 10/11 con PowerShell.

## Que queda funcionando

Al terminar deberias tener:

- Ollama instalado y respondiendo en `http://localhost:11434`.
- API RAG en `http://localhost:3333`.
- PWA en `https://localhost:3334`.
- Entorno Python `.venv`.
- Dependencias de la PWA.
- Modelos base descargados si eliges esa opcion.
- `.env` generado.
- Autoarranque opcional desde la carpeta Startup de Windows: la PWA vuelve al iniciar el equipo y la IA respeta si quedo encendida o apagada.

## Requisitos

| Recurso | Minimo | Recomendado |
|---|---:|---:|
| Windows | 10/11 | 11 |
| RAM | 8 GB | 16 GB o mas |
| Disco libre | 5 GB | 10-25 GB |
| Python | 3.10 | 3.12 |
| Node.js | 18 | 20 LTS |
| Git | Si | Si |
| Ollama | Si | Ultima version |
| PowerShell | 5+ | PowerShell 7 |

Instala Python marcando la opcion `Add python.exe to PATH`.

## Instalacion guiada recomendada

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador:

- Detecta RAM y elige perfil.
- Crea `.env`.
- Instala dependencias con `winget` si esta disponible.
- Crea `.venv`.
- Instala paquetes Python.
- Instala y compila la PWA.
- Pregunta si quieres descargar modelos de Ollama.
- Pregunta si quieres habilitar inicio con Windows.
- Pregunta si quieres iniciar los servicios ahora.

Las dependencias necesarias se instalan automaticamente. Las opciones como modelos, control LAN, inicio con Windows e inicio de servicios se preguntan por defecto. Usa `-NonInteractive` para instalaciones automatizadas.

Si todavia no tienes el proyecto:

```powershell
git clone https://github.com/TrinaxCode/TrinaxAI.git $env:USERPROFILE\trinaxai
cd $env:USERPROFILE\trinaxai
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

## Instalar dependencias manualmente

Puedes instalar con `winget`:

```powershell
winget install --id Python.Python.3.12 --silent
winget install --id Git.Git --silent
winget install --id OpenJS.NodeJS.LTS --silent
winget install --id Ollama.Ollama --silent
```

O descarga manualmente:

- Python: `https://python.org`
- Git: `https://git-scm.com`
- Node.js LTS: `https://nodejs.org`
- Ollama: `https://ollama.com/download/windows`

Cierra y vuelve a abrir PowerShell despues de instalar para refrescar `PATH`.

Verifica:

```powershell
python --version
git --version
node --version
npm --version
ollama --version
```

## Instalacion manual

### 1. Clonar el proyecto

```powershell
git clone https://github.com/TrinaxCode/TrinaxAI.git $env:USERPROFILE\trinaxai
cd $env:USERPROFILE\trinaxai
```

### 2. Crear entorno Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Instalar la PWA

```powershell
cd chat-pwa
npm install
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

Valores recomendados:

```text
TRINAXAI_PROFILE=16gb
TRINAXAI_HOST=0.0.0.0
TRINAXAI_PORT=3333
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_ALLOW_LAN_SYSTEM=1
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://127.0.0.1:3334,http://127.0.0.1:3334
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_HOST=0.0.0.0
VITE_TRINAXAI_RAG_TARGET=http://localhost:3333
```

Para usar telefono/tablet, busca tu IP LAN:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -match "^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[0-1]))" } |
  Select-Object -First 1 IPAddress
```

Agrega esa IP a `TRINAXAI_CORS_ORIGINS`, por ejemplo:

```text
TRINAXAI_CORS_ORIGINS=https://localhost:3334,http://localhost:3334,https://192.168.1.25:3334,http://192.168.1.25:3334
```

## Descargar modelos

Base:

```powershell
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull bge-m3
```

Vision:

```powershell
ollama pull qwen2.5vl:3b
```

Equipos con 16 GB o mas:

```powershell
ollama pull qwen2.5-coder:7b
```

Equipos con 32 GB o mas:

```powershell
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5vl:7b
```

## Indexar tus archivos

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe index.py
```

Tambien puedes abrir la PWA, ir a configuracion, elegir una carpeta y asignarla a una coleccion. TrinaxAI copiara los archivos a `local_sources\collections\` antes de indexarlos.

## Iniciar TrinaxAI

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe service_manager.py start --base-dir "$PWD"
```

Abrir:

```text
https://localhost:3334
```

Desde telefono o tablet en la misma WiFi:

```text
https://TU-IP-LAN:3334
```

Acepta la advertencia del certificado local si aparece.

## Apagar, reiniciar y revisar estado

Apagar IA y dejar la PWA disponible:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-ai --base-dir "$PWD"
```

Apagar todo:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-all --base-dir "$PWD"
```

Ver estado:

```powershell
.\.venv\Scripts\python.exe service_manager.py status --base-dir "$PWD"
```

Supervisor manual:

```powershell
.\.venv\Scripts\python.exe service_manager.py watch --base-dir "$PWD"
```

## Autoarranque en Windows

El instalador lo habilita automaticamente. El supervisor siempre intenta mantener la PWA disponible; si apagaste la IA desde la PWA o con `service_manager.py stop-ai`, el siguiente arranque no levanta Ollama/RAG hasta que vuelvas a encender la IA.

Habilitar:

```powershell
cd $env:USERPROFILE\trinaxai
.\.venv\Scripts\python.exe service_manager.py enable-autostart --base-dir "$PWD"
```

Esto crea `TrinaxAI.cmd` en la carpeta Startup de Windows.

Deshabilitar:

```powershell
.\.venv\Scripts\python.exe service_manager.py disable-autostart --base-dir "$PWD"
```

Tambien puedes revisar la carpeta Startup:

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
Invoke-RestMethod http://localhost:3333/health
```

Si tu PowerShell no soporta `-SkipCertificateCheck`, abre en navegador:

```text
http://localhost:3333/health
```

## Uso diario

1. Abre `https://localhost:3334`.
2. Usa Ollama para chat general.
3. Usa RAG para consultar archivos indexados.
4. Usa colecciones para separar proyectos.
5. Instala la PWA desde Chrome o Edge con el icono de instalacion de la barra de direcciones.

## Actualizar

Si usas los scripts desde Git Bash o WSL:

```bash
./update.sh
```

El actualizador pregunta si quieres crear backup, descargar codigo nuevo, actualizar modelos, cambiar autoarranque, reiniciar servicios y correr la auditoria. Las dependencias Python/npm y el build de la PWA siguen siendo automaticos.

En PowerShell manual:

```powershell
cd $env:USERPROFILE\trinaxai
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd chat-pwa
npm install
npm run build
cd ..
```

## Copias de seguridad

Respaldar manualmente:

- `.env`
- `storage\`
- `local_sources\`

Si tienes Git Bash:

```bash
./backup.sh create
```

## Desinstalar

Desde Git Bash o WSL, usa el desinstalador guiado:

```bash
./uninstall.sh
```

Pregunta que archivos runtime quieres quitar. Los datos RAG y modelos de Ollama se conservan salvo que elijas borrarlos.

Limpieza manual en PowerShell:

```powershell
.\.venv\Scripts\python.exe service_manager.py disable-autostart --base-dir "$PWD"
```

Deten servicios:

```powershell
.\.venv\Scripts\python.exe service_manager.py stop-all --base-dir "$PWD"
```

Luego puedes eliminar la carpeta del proyecto. Los modelos de Ollama se administran aparte:

```powershell
ollama list
ollama rm qwen2.5-coder:3b
ollama rm llama3.2:3b
ollama rm bge-m3
```

## Firewall y red local

| Puerto | Servicio | Uso |
|---:|---|---|
| 11434 | Ollama | Modelos locales |
| 3333 | RAG API | Backend |
| 3334 | PWA | Interfaz web |

Para abrir desde telefono/tablet, Windows Defender Firewall debe permitir Node/Python en red privada. No permitas estos puertos en redes publicas.

## Problemas comunes

| Problema | Solucion |
|---|---|
| `python` no se reconoce | Reinstala Python marcando `Add python.exe to PATH`. |
| `npm` no se reconoce | Instala Node.js LTS y abre una terminal nueva. |
| `ollama` no se reconoce | Instala Ollama para Windows y reinicia PowerShell. |
| Error de permisos PowerShell | Ejecuta con `-ExecutionPolicy Bypass`. |
| PWA no abre desde telefono | Revisa firewall, misma WiFi e IP LAN en `TRINAXAI_CORS_ORIGINS`. |
| API HTTPS muestra certificado no valido | Es normal con certificado local; acepta la advertencia. |
| Out of memory | Usa perfil `8gb` o modelos 3B. |

## Nota sobre WSL

Puedes ejecutar TrinaxAI dentro de WSL2 usando la guia Linux, pero para usuarios de Windows el camino mas directo es PowerShell + `install.ps1`. Si usas WSL2, ten en cuenta que la red, firewall y acceso a archivos funcionan diferente entre Windows y Linux.

## Seguridad

No expongas `3333`, `3334` ni `11434` a internet. Para acceso remoto usa VPN. Si necesitas bloquear acciones de sistema fuera de localhost:

```text
TRINAXAI_ALLOW_LAN_SYSTEM=0
TRINAXAI_ADMIN_TOKEN=un-token-largo
```
