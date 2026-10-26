<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="chat-pwa/public/logo.webp" alt="TrinaxAI" width="220" valign="middle"></a>
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="Estrellas en GitHub"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.4.0"><img src="https://img.shields.io/badge/version-1.4.0-006bbd" alt="Release estable: 1.4.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="Estado de CI"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="Licencia AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Plataformas compatibles: macOS, Windows y Linux">
</p>

<p align="center"><sub><a href="README.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="docs/README.es.md">Documentación</a> · <a href="docs/CHANGELOG.es.md">Cambios</a> · <a href="LICENSE">Licencia</a></sub></p>

> Un asistente privado y local para tus archivos, investigaciones y código.

TrinaxAI se ejecuta en tu equipo y mantiene la inferencia y los datos indexados
en el host configurado salvo que elijas explícitamente un servicio remoto.
Combina chat local, generación aumentada por recuperación (RAG) con citas,
investigación web opcional, un agente de código confinado al workspace, una interfaz de
terminal y una aplicación web progresiva (PWA) instalable.

## Instalar con npm

Usa el paquete npm en Linux, macOS o Windows. Necesitas Node.js 22 o posterior
con npm disponible en la terminal.

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

El lanzador descarga el release oficial correspondiente, verifica su checksum
SHA-256 e inicia la configuración de la plataforma. El flujo prepara el
backend, la PWA, Ollama y los modelos recomendados.

La instalación empieza con una bienvenida y te pregunta el idioma (español o
inglés). Luego comprueba el espacio en disco y la conexión, te hace todas las
preguntas opcionales al principio (descargar modelos, iniciar ahora,
autoarranque, comprobación semanal de actualizaciones, acceso desde otros
dispositivos) y muestra un plan de
instalación para que lo confirmes antes de cambiar nada. Ejecuta `trinaxai setup`
de nuevo sobre una instalación existente para repararla, actualizarla o
desinstalarla.

El lanzador npm es la única ruta de instalación pública para usuarios finales.
Los scripts de plataforma del repositorio implementan el release por debajo;
no necesitas descargarlos ni ejecutarlos directamente.

## Empezar a usar TrinaxAI

Ejecuta primero la comprobación de salud:

~~~bash
trinaxai doctor
trinaxai status
~~~

Después abre [https://localhost:3334](https://localhost:3334). El navegador
puede pedirte que confíes en el certificado local la primera vez.

Haz una pregunta sobre los archivos indexados:

~~~bash
trinaxai ask "Resume mi proyecto indexado" --engine rag
~~~

Si aplazaste la descarga de modelos, ejecuta `trinaxai setup` cuando estés
listo. Usa `trinaxai --help` para consultar todos los comandos.

## Opciones de configuración

| Necesidad | Comando |
| --- | --- |
| Aplazar modelos | `trinaxai setup --no-models` |
| Preparar sin iniciar servicios | `trinaxai setup --no-start` |
| Permitir que otros dispositivos de tu red abran TrinaxAI (por defecto: solo este equipo) | `trinaxai setup --lan-access` |
| Elegir un perfil | `trinaxai setup --profile 16gb` |
| Previsualizar cambios | `trinaxai setup --dry-run` |
| Omitir la pregunta de idioma | `trinaxai setup --language es` |
| Automatizar | `trinaxai setup --yes` (o `--non-interactive`) |

El instalador detecta CPU, memoria, GPU y VRAM. Consulta
[configuración](docs/CONFIGURATION.es.md) para ajustar modelos, límites o proveedores.

## Comandos diarios

| Objetivo | Comando |
| --- | --- |
| Abrir el asistente interactivo | `trinaxai chat` |
| Hacer una pregunta | `trinaxai ask "..." --engine rag` |
| Indexar una carpeta | `trinaxai index ./documentos` |
| Ejecutar investigación (añade `--web` para apoyarla en búsqueda web) | `trinaxai research "..." --depth 2` |
| Usar el agente | `trinaxai agent --workspace .` |
| Revisar servicios | `trinaxai status` |
| Ver o cambiar quién puede abrir TrinaxAI | `trinaxai network` / `trinaxai network off` |
| Iniciar o detener servicios | `trinaxai start` / `trinaxai stop` |
| Diagnosticar | `trinaxai doctor --strict` |
| Actualizar | `trinaxai update` |
| Eliminar TrinaxAI | `trinaxai uninstall` |

## Qué incluye TrinaxAI

- Chat local con Ollama y enrutamiento por tipo de tarea
- RAG híbrido sobre código y documentos con citas, colecciones e indexación incremental
- Búsqueda web, investigación profunda, memoria, voz y visión opcionales
- Agente de código con workspaces aprobados y aprobación de acciones. Su herramienta de
  terminal se ejecuta en un sandbox bubblewrap sin red en Linux y permanece desactivada en
  macOS y Windows; las herramientas de archivos funcionan en todas (ver la [guía de seguridad](docs/SECURITY.es.md))
- PWA HTTPS para escritorio y móvil con emparejamiento por scopes
- Interfaz de terminal para chat, indexación, investigación, diagnósticos y exportaciones

## Modelos y hardware

La configuración elige un perfil según la memoria y los recursos gráficos:

| Perfil | Chat y código | Respuestas rápidas | Embeddings |
| --- | --- | --- | --- |
| `8gb` | `qwen3.5:2b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `16gb` | `qwen3.5:4b` | `qwen3.5:2b` | `qwen3-embedding:0.6b` |
| `32gb` | `qwen3.5:9b` | `qwen3.5:4b` | `qwen3-embedding:4b` |
| `64gb` | `qwen3.5:35b` / `qwen3-coder:30b` | `qwen3.5:4b` | `qwen3-embedding:4b` |

El perfil `8gb` funciona solo con CPU. Consulta la
[referencia de configuración](docs/CONFIGURATION.es.md) para modelos y recursos.

## Límites conocidos

- Preguntas sobre código respondidas por modelos locales pequeños: las fuentes
  citadas a veces son erróneas o incompletas, así que abre el archivo citado
  antes de fiarte de una respuesta.
- `trinaxai research` es lento en un equipo sin GPU.
- No medido: el flujo completo (instalación, chat, RAG, agente y app web) en
  Windows, con GPU y con modelos grandes. macOS y Windows están cubiertos por las
  comprobaciones automáticas de CI, no por ejecuciones de extremo a extremo.

## Privacidad y seguridad

TrinaxAI enlaza los servicios locales a loopback por defecto. Ollama no se
expone como proxy genérico. Los navegadores LAN deben emparejarse con un código
de un solo uso y reciben únicamente las capacidades que concedas. La
indexación, administración, herramientas del agente y gestión de modelos
permanecen en el host.

Mantén privados los puertos `3333` y `11434`, protege `storage/.proxy_secret` y
usa una VPN en vez de exponer el host. Lee [seguridad](docs/SECURITY.es.md) y
[pairing LAN](docs/NETWORK_PAIRING.es.md) antes de conectar otro dispositivo.

## Documentación

| Quieres… | Consulta |
| --- | --- |
| Instalar, actualizar o eliminar | [Centro de documentación](docs/README.es.md) |
| Configurar modelos, RAG, red o límites | [Configuración](docs/CONFIGURATION.es.md) |
| Consultar una variable de entorno | [Variables de entorno](docs/ENVIRONMENT_VARIABLES.es.md) |
| Usar todos los comandos | [Referencia CLI](docs/CLI_REFERENCE.es.md) |
| Entender la arquitectura | [Arquitectura](docs/ARCHITECTURE.es.md) |
| Integrar la API HTTP | [Referencia de API](docs/API_REFERENCE.es.md) |
| Resolver un error | [Solución de problemas](docs/TROUBLESHOOTING.es.md) |
| Emparejar otro dispositivo | [Pairing LAN](docs/NETWORK_PAIRING.es.md) |
| Desarrollar o contribuir | [Guía del desarrollador](docs/DEVELOPER_GUIDE.es.md) |

La PWA también expone estas guías en **Configuración → Documentación**.

## Desarrollo

Esta sección es para contribuidores que trabajan desde un checkout. Los
usuarios finales deben usar la instalación npm anterior.

~~~bash
git clone https://github.com/TrinaxCode/TrinaxAI.git
cd TrinaxAI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
(cd chat-pwa && npm ci && npm run dev)
~~~

Ejecuta `make check` antes de enviar cambios. Consulta la
[guía para contribuir](docs/CONTRIBUTING.es.md).

## Capturas

| Flujo | English | Español |
| --- | --- | --- |
| Chat con citas | [Abrir](docs/assets/screenshots/chat-citations-en.png) | [Abrir](docs/assets/screenshots/chat-citations-es.png) |
| Trabajo de indexación | [Abrir](docs/assets/screenshots/indexing-job-en.png) | [Abrir](docs/assets/screenshots/indexing-job-es.png) |
| Pairing | [Abrir](docs/assets/screenshots/pairing-en.png) | [Abrir](docs/assets/screenshots/pairing-es.png) |
| Aprobación del agente | [Abrir](docs/assets/screenshots/agent-approval-en.png) | [Abrir](docs/assets/screenshots/agent-approval-es.png) |

## Licencia

TrinaxAI se distribuye bajo AGPL-3.0-or-later. Consulta [LICENSE](LICENSE) y
la [guía de marca](docs/TRADEMARK.es.md).

Creado por [TrinaxCode](https://github.com/TrinaxCode) ·
[trinaxai.app](https://www.trinaxai.app/)
