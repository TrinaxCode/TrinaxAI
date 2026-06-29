# 🚀 TrinaxAI — Asistente de IA 100% Local

<p align="center">
  <strong>Asistente de IA open-source, local-first con RAG, visión, voz y PWA.</strong><br>
  Corre completamente en tu máquina. Sin nube. Sin suscripciones. Sin límites.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licencia-AGPL--3.0--or--later-blue.svg" alt="AGPL-3.0-or-later"></a>
  <a href="#"><img src="https://img.shields.io/badge/potenciado_por-Ollama-black.svg" alt="Ollama"></a>
  <a href="#"><img src="https://img.shields.io/badge/plataforma-Linux|macOS|Windows-lightgrey.svg" alt="Plataformas"></a>
  <a href="#"><img src="https://img.shields.io/badge/PWA-listo-brightgreen.svg" alt="PWA"></a>
</p>

---

## 🖥️ Plataformas Soportadas

| SO | Instalador | Gestor de Servicios | Auto-Restart |
|---|---|---|---|
| **Linux** (Ubuntu, Debian, Fedora, Arch, etc.) | `install.sh` | systemd de usuario vía `service_manager.py` | supervisor mantiene la PWA online; la IA respeta si el usuario la dejó encendida o apagada |
| **macOS** (Intel + Apple Silicon) | `install.sh` | launchctl vía `service_manager.py` | supervisor mantiene la PWA online; la IA respeta si el usuario la dejó encendida o apagada |
| **Windows** (10/11, PowerShell) | `install.ps1` | Inicio de Windows + supervisor de subprocesos | supervisor mantiene la PWA online; la IA respeta si el usuario la dejó encendida o apagada |
| **Docker** | (planeado) | — | — |

- **Guias completas por sistema:** [Linux](docs/INSTALL_LINUX.md) · [macOS](docs/INSTALL_MACOS.md) · [Windows](docs/INSTALL_WINDOWS.md)
- **`setup_trinaxai.sh` es setup legacy solo para Linux.** Las instalaciones nuevas deben usar `install.sh` / `install.ps1`; configuran `service_manager.py` para que la PWA siga disponible después de reiniciar y los servicios de IA solo vuelvan si el usuario dejó la IA encendida.
- La instalación nativa es el camino recomendado en V1 porque Ollama con GPU, indexación de archivos del host, HTTPS LAN y acceso desde teléfono son más predecibles que en un contenedor.

---

## ✨ Características

- 🧠 **Dos motores de IA** — Ollama (rápido, creativo) + RAG (preciso, contextual)
- 📇 **RAG personalizado** — Indexa tu biblioteca de proyectos. La IA responde con contexto real
- 🗂️ **Colecciones de conocimiento** — Crea espacios RAG separados y consulta uno o varios a la vez
- 📎 **Análisis temporal de archivos** — Adjunta archivos sin guardarlos/indexarlos; la indexación RAG es explícita
- 🧭 **Memoria local** — Los datos explícitos tipo "recuerda que..." persisten entre dispositivos locales
- 🎤 **Modo llamada** — Reconocimiento de voz + texto a voz. Conversaciones naturales
- 📸 **Visión** — Analiza imágenes con modelos de visión (qwen2.5-vl)
- 🌐 **Multi-idioma** — Español e inglés, auto-detectado. Fácil de expandir
- 🌓 **Modo claro/oscuro** — Auto-detectado de tu sistema
- 📱 **PWA** — Instala como app nativa en iOS, Android y escritorio
- ⚡ **Auto-enrutamiento** — Selección inteligente de modelo según tu consulta
- 🔄 **Indexación incremental** — Solo re-indexa archivos modificados. Chunking AST
- 📤 **Historial mejorado** — Busca chats, edita/reenvía mensajes y exporta a Markdown/PDF
- 📊 **Monitor de recursos** — Telemetría básica de RAM local en la PWA
- 🛡️ **100% Local** — Todo corre en tu máquina. Tus datos nunca salen de tu red
- 🧰 **Herramientas de release** — `backup.sh`, `update.sh`, `uninstall.sh`, CI, DCO y auditoría pública

---

## 🏗️ Arquitectura

```
┌──────────────────────────────────────────┐
│              Tu Dispositivo              │
│  ┌──────────┐  ┌─────────────────────┐   │
│  │ PWA (React)│  │ VSCode (Continue)  │   │
│  │ :3334     │  │ continue-config.yaml│   │
│  └─────┬─────┘  └──────────┬──────────┘   │
│        │                   │               │
│  ┌─────┴───────────────────┴──────────┐   │
│  │     RAG API (FastAPI) :3333        │   │
│  │  LlamaIndex • bge-m3 • BM25       │   │
│  └─────┬──────────────────────────────┘   │
│        │                                   │
│  ┌─────┴──────┐                            │
│  │  Ollama    │  qwen2.5 • llama3.2       │
│  │  :11434    │  bge-m3 • moondream       │
│  └────────────┘                            │
└──────────────────────────────────────────┘
```

---

## 🚀 Inicio Rápido

Para instrucciones completas por sistema, usa:

| Sistema | Guia completa |
|---|---|
| Linux | [docs/INSTALL_LINUX.md](docs/INSTALL_LINUX.md) |
| macOS | [docs/INSTALL_MACOS.md](docs/INSTALL_MACOS.md) |
| Windows | [docs/INSTALL_WINDOWS.md](docs/INSTALL_WINDOWS.md) |

### Requisitos
- Python 3.10+, Node.js 18+, 8GB+ RAM (16GB recomendado)
- Linux, macOS, o Windows

| Componente | Mínimo | Recomendado |
|-----------|--------|-------------|
| RAM | 8 GB | 16 GB, 32GB+ para Ultra |
| Espacio en disco | 5 GB | 10-25+ GB (modelos + índice) |
| Python | 3.10 | 3.12+ |
| Node.js | 18 | 20+ |
| Ollama | Última | Última |
| GPU | No requerida | NVIDIA CUDA / Apple Metal (auto-detectada) |

> 💡 Visita [canirun.ai](https://www.canirun.ai) para ver qué modelos puede ejecutar tu hardware.

### 1. Instalación automática
```bash
# Linux
curl -fsSL https://raw.githubusercontent.com/TrinaxCode/TrinaxAI/main/install.sh | bash

# macOS
bash install.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador es automático por defecto: detecta sistema/RAM, escribe `.env`, instala dependencias donde es soportado, prepara Python + PWA, descarga modelos recomendados de Ollama, activa inicio con el sistema, inicia TrinaxAI y configura acceso LAN para teléfonos/tablets. Usa `./install.sh --interactive` o `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Interactive` si quieres preguntas manuales.

### 2. Configuración manual
```bash
git clone https://github.com/TrinaxCode/trinaxai.git
cd trinaxai
./install.sh
```

### 3. Descargar Modelos
```bash
ollama pull qwen2.5-coder:3b
ollama pull llama3.2:3b
ollama pull bge-m3
# Modelo de visión
ollama pull qwen2.5vl:3b
```

### 4. Indexar tus Proyectos
```bash
python index.py
```

También puedes abrir la PWA, ir a **Configuración → Elegir carpeta e indexar**, seleccionar una carpeta desde el explorador de archivos, asignarla a una colección y TrinaxAI copiará los archivos a `local_sources/collections/` antes de indexarlos. La UI muestra progreso de subida/indexación, tiempo estimado, archivos omitidos y botón para cancelar. Los navegadores no exponen la ruta absoluta original por seguridad.

### 5. Iniciar Todo
```bash
./startup_ai.sh
```

### 6. Abrir la PWA
```
https://localhost:3334
```
Desde tu teléfono: `https://[TU-IP-LOCAL]:3334`

### Mantenimiento

```bash
./backup.sh create        # respalda .env, storage y fuentes importadas
./update.sh               # backup, pull, dependencias y rebuild de PWA
./uninstall.sh            # elimina runtime local con confirmación escrita
```

---

## ⚙️ Configuración

La mayoría debería usar `install.sh` / `install.ps1`; escriben `.env` automáticamente. Configuración avanzada:

| Ajuste | Medium | High | Ultra |
|--------|:------:|:----:|:-----:|
| NUM_CTX | 4096 | 8192 | 16384 |
| RERANK_ENABLED | false | false | false |
| EMBED_WORKERS | 2 | 4 | 6 |
| KEEP_ALIVE | 0s | 30m | 60m |
| Modelo profundo | 3B | 7B | 14B |

```bash
TRINAXAI_INDEX_DIR=~/Documents
TRINAXAI_CORS_ORIGINS=https://localhost:3334,https://TU-IP-LAN:3334
TRINAXAI_PROFILE=ultra
TRINAXAI_ALLOW_LAN_SYSTEM=1
TRINAXAI_UPLOAD_MAX_BYTES=536870912
VITE_TRINAXAI_RAG_TARGET=https://localhost:3333
```

💡 Revisa **[canirun.ai](https://www.canirun.ai)** para ver qué modelos soporta tu hardware.

### Notas de Seguridad

- Las acciones de sistema y la indexación desde navegador aceptan localhost + IPs privadas LAN por defecto para que el teléfono funcione sin tokens. Usa `TRINAXAI_ALLOW_LAN_SYSTEM=0` para volver a modo localhost/token.
- Si expones TrinaxAI fuera de tu LAN confiable, configura `TRINAXAI_ADMIN_TOKEN` y ponlo detrás de una VPN/proxy con autenticación.
- Las carpetas importadas se copian en `local_sources/collections/`; no se guarda la ruta absoluta original.
- Los límites de subida se configuran con `TRINAXAI_MAX_FILE_BYTES`, `TRINAXAI_UPLOAD_MAX_FILES` y `TRINAXAI_UPLOAD_MAX_BYTES`.
- El supervisor cross-platform mantiene la PWA online después de reiniciar. Si el usuario apaga la IA, en el siguiente arranque solo vuelve la PWA; si la IA quedó encendida, también vuelven Ollama + RAG.
- Ollama escucha en `0.0.0.0:11434` por defecto, lo que significa que cualquier dispositivo en tu red local puede usarlo. Usa un firewall para restringir el puerto 11434 si no quieres esto, o configura una VPN (Tailscale/WireGuard) para acceso remoto seguro.
- `setup_trinaxai.sh` configura una regla sudoers para que la PWA pueda encender/apagar TrinaxAI sin contraseña. Los scripts de startup deben estar en un directorio protegido; en producción, muévelos a `/usr/local/lib/trinaxai/`.

### Modelo de Seguridad

- **Local-first:** Ollama, RAG, colecciones, voz, visión y estado compartido corren en tu equipo o LAN confiable.
- **Acciones protegidas:** encender/apagar sistema, indexación desde navegador, sincronización de estado y escritura de colecciones requieren localhost/LAN confiable o token admin.
- **Protegido por LAN:** acciones de sistema, indexación desde navegador, sincronización de estado y escritura de colecciones aceptan localhost y clientes de LAN privada confiable por defecto.
- **Opción con token:** usa `TRINAXAI_ADMIN_TOKEN` y `TRINAXAI_ALLOW_LAN_SYSTEM=0` si expones TrinaxAI fuera de tu LAN personal.
- **Configuración segura recomendada:** mantén TrinaxAI en localhost/WiFi privada, no expongas puertos a internet y usa VPN para acceso remoto.

## Colecciones

- Las colecciones viven en `storage/collections.json`; los chunks indexados guardan `collection_id` y `collection_name`.
- El chat RAG puede usar una o varias colecciones activas como contexto. También puedes subir archivos directamente desde el chat a la colección activa.
- Los archivos adjuntos en el chat son temporales por defecto. En modo RAG la UI pregunta si quieres indexarlos y en qué colección.
- La memoria de largo plazo es explícita: mensajes como "recuerda que mi proyecto principal es X" se guardan localmente en `tc-user-memory` y se inyectan en prompts futuros.
- Restaurar configuración inicial limpia el navegador local y el estado compartido del host (`storage/app_state.json`) cuando el backend está disponible.

## Comparación

| Proyecto | Enfoque | Diferencia de TrinaxAI |
|---------|---------|-------------------------|
| Open WebUI / Ollama WebUI | Chat general con Ollama | TrinaxAI prioriza RAG/proyectos, indexación local, citas, acceso PWA desde teléfono y setup automático. |
| AnythingLLM | Asistente con base de conocimiento | TrinaxAI está pensado para workstation local/desarrolladores: chunking de código, Continue.dev, auto-routing Ollama y cero nube. |
| Continue.dev | Asistente dentro del IDE | TrinaxAI lo complementa: `continue-config.yaml` conecta Continue al mismo RAG local y flota Ollama. |

---

## 📁 Estructura del Proyecto

| Archivo | Propósito |
|---------|-----------|
| `rag_api.py` | Backend FastAPI — chat, health, control del sistema |
| `index.py` | Indexador de proyectos — chunking AST, modo incremental |
| `trinaxai_cli.py` | TrinaxAI CLI local (`ollama` / `rag`) |
| `query.py` | Wrapper compatible para TrinaxAI CLI |
| `config.py` | Toda la configuración — modelos, ctx, workers |
| `startup_ai.sh` | Iniciar todos los servicios |
| `shutdown_ai.sh` | Apagado controlado |
| `backup.sh` | Backup/restore de estado local |
| `update.sh` | Actualizar código/dependencias y reconstruir |
| `uninstall.sh` | Eliminar runtime local |
| `service_manager.py` | Supervisor cross-platform start/stop/status/watch |
| `test_system.py` | Verificación de salud automática |
| `chat-pwa/` | Frontend React PWA |

### Qué No Debe Publicarse

El repo ignora datos locales/runtime:

- `.venv/`, `chat-pwa/node_modules/`, `chat-pwa/dist/`
- `storage/`, `storage.bak.nomic/`, `local_sources/`, `projects/`
- `logs/`, `backups/`
- `.env`, certificados locales y servicios generados

Ejecuta `python3 scripts/public_readiness.py` antes de publicar.

## Docker

Docker puede servir para usuarios avanzados, demos y despliegues en servidor/NAS, pero no debería ser el camino principal de TrinaxAI V1. Ollama con GPU, indexación de archivos del host, certificados HTTPS locales y acceso desde teléfono funcionan de forma más predecible con instalación nativa.

Docker Compose sí vale la pena como opción futura para:

- demos y smoke tests de CI,
- servidores/NAS,
- usuarios que ya ejecutan Ollama fuera del contenedor,
- pruebas aisladas sin tocar Python del host.

Para V1, la instalación nativa sigue siendo la recomendada.

---

## 📱 Instalación PWA

**iOS (Safari):** Abre la URL → Compartir → "Añadir a pantalla de inicio"  
**Android (Chrome):** Abre la URL → ⋮ → "Instalar aplicación"  
**Escritorio:** Icono de instalación en la barra de direcciones (Chrome/Edge)

---

## 🔧 Solución de Problemas

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| "No se encontró índice" en PWA | Índice no construido | Ejecuta `python index.py` |
| Ollama no inicia | Puerto 11434 ocupado | Verifica con `lsof -i :11434` |
| Advertencia de certificado HTTPS | Certificado autofirmado | Acepta la advertencia — solo uso local |
| Error CORS desde el teléfono | `TRINAXAI_CORS_ORIGINS` no configurado | Agrega `https://TU-IP-LAN:3334` |
| "Modelo no encontrado" | Modelo no descargado | Ejecuta `ollama pull <modelo>` |
| Sin memoria suficiente | Demasiados modelos cargados | Reduce `OLLAMA_MAX_LOADED_MODELS` |
| "sudo no encontrado" | macOS sin sudo, o Windows | Usa `python service_manager.py` para gestionar procesos |
| Frontend no carga | Servidor Vite no iniciado | `cd chat-pwa && npm run dev` |
| Índice atascado al 0% | Archivos ilegibles en el directorio | Revisa permisos; el indexador omite archivos ilegibles |

## 🧪 Pruebas

```bash
make audit
make build
python test_system.py --verbose
python trinaxai_cli.py --engine rag
```

Para preparar una publicación, revisa [docs/PUBLIC_RELEASE.es.md](docs/PUBLIC_RELEASE.es.md).

### ✅ Verificar

Antes de hacer push o abrir un PR, ejecuta estos tres comandos. Son los mismos chequeos que ejecuta `make audit` y el pipeline de CI:

```bash
python3 scripts/public_readiness.py   # archivos requeridos, hardcodes locales, claves i18n
python3 -m py_compile rag_api.py index.py config.py trinaxai_cli.py service_manager.py test_system.py scripts/public_readiness.py
cd chat-pwa && npx tsc --noEmit && npm run build
```

Una ejecución limpia imprime `Public readiness audit passed.` y termina con código `0`.

---

## 🤝 Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md). ¡Toda contribución es bienvenida!

- 🐛 Reporta bugs · 💡 Sugiere funcionalidades · 📝 Mejora la documentación · 🌍 Traduce · 🔧 Envía PRs

---

## Desinstalar

Para eliminar TrinaxAI completamente de tu sistema:

```bash
./uninstall.sh
# Opcional: ./uninstall.sh --remove-models
```

## Licencia

AGPL-3.0-or-later — ver [LICENSE](LICENSE). Revisa [TRADEMARK.md](TRADEMARK.md) para uso del nombre/logo.

---

## ⭐ Apoya el Proyecto

Si TrinaxAI te ayuda, ¡**dale una estrella al repo** ⭐! Ayuda a que otros descubran el proyecto.

[![Star History Chart](https://api.star-history.com/svg?repos=TrinaxCode/TrinaxAI&type=Date&locale=es)](https://star-history.com/#TrinaxCode/TrinaxAI)

<p align="center">
  <strong>Hecho por <a href="https://github.com/TrinaxCode">TrinaxCode</a></strong><br>
  <sub>La IA debe ser libre, privada y local.</sub>
</p>
