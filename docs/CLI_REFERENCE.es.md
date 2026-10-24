<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 💻 Referencia de CLI
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.4.0"><img src="https://img.shields.io/badge/version-1.4.0-006bbd" alt="Stable release: 1.4.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="CLI_REFERENCE.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

La CLI `trinaxai` ofrece chat directo con Ollama, consultas RAG, indexación, administración de memoria y colecciones, y control de servicios. Los usuarios finales la reciben mediante la instalación npm. El comando de checkout que aparece abajo es para contribuidores y desarrollo. Para recuperar fallos por síntoma, consulta la [guía de solución de problemas](TROUBLESHOOTING.es.md).

## Instalación y ayuda

```bash
python -m pip install -e .
trinaxai --help
trinaxai help
trinaxai COMMAND --help
```

Sin subcomando, `trinaxai` abre el chat interactivo. Las opciones globales deben colocarse antes del subcomando:

```bash
trinaxai --api-url https://localhost:3333 --ca-file /ruta/rootCA.pem ask "Estado del índice"
```

| Opción global | Uso |
|---|---|
| `--api-url URL` | Sobrescribe la URL de la API RAG. |
| `--ca-file PATH` | Confía en un bundle CA explícito sin desactivar la validación HTTPS. |
| `--install-root PATH` | Indica la raíz de una instalación completa. |
| `--config PATH` | Carga un TOML concreto. |
| `--no-color` | Desactiva color ANSI. |
| `--language IDIOMA`, `--lang IDIOMA` | Selecciona `en` o `es` para la salida humana de la CLI; también admite `TRINAXAI_LANG` y `ui.language` en TOML. |
| `-v`, `--verbose` | Activa logs de depuración. |
| `--version` | Muestra la versión. |

## Mapa de comandos

```bash
trinaxai chat [--prompt TEXTO] [--file RUTA] [--engine MOTOR] [--collections IDS] [--thinking]
trinaxai ask [PREGUNTA ...] [--file RUTA] [--engine MOTOR] [--collections IDS] [--thinking]
trinaxai agent [TAREA ...] [-p TEXTO] [--workspace RUTA] [--model NOMBRE] [--max-steps N]
               [--permission-mode MODO] [--output-format text|json] [-c | -r SESIÓN] [--yolo]
trinaxai research TEXTO|--query TEXTO [--web] [--session NOMBRE] [--depth PROFUNDIDAD] [--collections IDS] [--thinking]
trinaxai index [RUTA] [--collection ID] [--append]
trinaxai browse list-collections
trinaxai browse list-files [--collection ID]
trinaxai browse show-chunks --file RUTA [--collection ID] [--limit N]
trinaxai memory ACCIÓN
trinaxai collections ACCIÓN
trinaxai watch ACCIÓN
trinaxai pair [start] [--scopes LISTA] [--ttl SEGUNDOS] [--device-ttl-days DÍAS] [--pwa-url URL]
trinaxai pair list
trinaxai pair set ID_DISPOSITIVO --scopes LISTA
trinaxai pair revoke ID_DISPOSITIVO
trinaxai obsidian --vault RUTA [--collection ID]
trinaxai export [--session NOMBRE] [--format FORMATO] [--output RUTA]
trinaxai status
trinaxai start
trinaxai restart
trinaxai models
trinaxai config
trinaxai doctor
trinaxai version
trinaxai stop
trinaxai stop --all
trinaxai network
trinaxai network refresh
trinaxai network off
trinaxai update
trinaxai uninstall
```

`MOTOR` es `general`, `ollama` o `rag`; `PROFUNDIDAD` es `1`, `2` o `3`.
`--no-thinking` es el inverso de `--thinking`. El mapa muestra la forma común;
ejecuta `trinaxai COMANDO --help` para ver cada opción y su valor predeterminado.

`trinaxai stop --all` detiene la PWA y el resto de la pila, y deja solo la
página de recuperación por loopback en `https://localhost:3334`; la LAN
permanece cerrada hasta iniciar TrinaxAI desde esa página local.

Usa `--append` solo cuando los archivos fuente eliminados deban seguir
indexados. Cada raíz tiene un `source_id` estable e independiente, así que
sincronizar otra raíz en la misma colección ya no reemplaza rutas homónimas de la
primera. El watcher requiere la dependencia de servidor `watchdog`. La
exportación de sesiones admite Markdown, PDF y Word (`docx`, también aceptado
como `word`) y conserva los metadatos públicos y las fuentes de DeepResearch. El
comando reservado `trinaxai mcp` devuelve el código de salida `2` y no inicia un
servidor MCP en esta versión; usa la API HTTP o los comandos de CLI compatibles.

## Chat y consultas

```bash
trinaxai chat
trinaxai chat --prompt "Resume este proyecto" --engine rag --collections default,docs --thinking
trinaxai chat --file ./foto.png --prompt "Describe esta imagen"
trinaxai ask --file ./manual.pdf "Resume este documento"
trinaxai ask "Escribe una prueba para esta función" --engine ollama --no-thinking
trinaxai agent --workspace . --prompt "Corrige las pruebas"
trinaxai research --query "Compara los módulos de seguridad" --session seguridad --depth 2 --collections default --thinking
```

En el chat automático, TrinaxAI enruta cada turno por capacidad: las consultas públicas directas van a búsqueda web, las preguntas sobre tus propios proyectos o archivos van a RAG y las solicitudes complejas con varias fuentes van a investigación profunda. La ejecución con Agent es explícita: usa `/agent` (o `trinaxai agent`) antes de pedirle que escriba archivos. Usa `/chat`, `/web`, `/research`, `/rag` o `/agent` para fijar un modo.

`--engine general` es un alias del chat directo con Ollama; `rag` usa documentos indexados. `--collections` acepta IDs separados por comas.

Usa `trinaxai chat --file RUTA --prompt "Describe esto"` para analizar una
imagen o archivo local de texto/documento. La ruta se valida localmente y la CLI
no sube el archivo.

Sin `--web`, `research` trabaja con tus documentos indexados (y busca en la web solo si la pregunta pide información actual); `--web` siempre la apoya en búsqueda web, lo que envía la pregunta al proveedor de búsqueda. `research` intenta leer texto acotado de las páginas (`full_page`) y conserva el
extracto del buscador como fallback (`snippet_only`); las fuentes indican cuál
se usó. Añade `--session NOMBRE` para guardar la pregunta, la respuesta, los
metadatos públicos y las fuentes, y después exportar la sesión.

## Indexación y exploración

```bash
trinaxai index . --collection default
trinaxai index ~/Documents --collection documentos --append
trinaxai browse list-collections
trinaxai browse list-files --collection default
trinaxai browse show-chunks --collection default --file README.md --limit 20
trinaxai obsidian --vault ~/Notas --collection notas
```

`--append` añade cambios sin eliminar del índice los archivos ausentes. Sin esta
opción sincroniza esa raíz. Cada raíz tiene `source_id` estable e independiente,
por lo que otra raíz de la misma colección ya no reemplaza rutas homónimas.

## Memoria y colecciones

```bash
trinaxai memory list
trinaxai memory add --text "Prefiero respuestas breves" --tags preferencia,estilo
trinaxai memory forget --memory-id ID
trinaxai memory refresh
trinaxai memory summary

trinaxai collections list
trinaxai collections create --name "Documentación"
trinaxai collections use --collection-id documentacion
trinaxai collections delete --collection-id documentacion
```

## Vigilancia y exportación

```bash
trinaxai watch start --paths ~/proyectos/app --collection default
trinaxai watch status
trinaxai watch stop
trinaxai export --session SESSION --format md --output conversacion
```

El watcher requiere `watchdog`, incluido en las dependencias de servidor. La exportación conserva metadatos públicos, fuentes y citas de investigación; admite `md`, `markdown`, `pdf`, `doc`, `docx` y `word`.

## Ciclo de vida y diagnóstico

```bash
trinaxai status
trinaxai start
trinaxai restart
trinaxai stop            # mantiene la PWA disponible
trinaxai stop --all      # también detiene la PWA
trinaxai models
trinaxai config
trinaxai doctor
trinaxai doctor --strict --json
trinaxai update
trinaxai uninstall
```

`trinaxai stop --all` detiene la PWA y el resto de la pila; después solo queda
la página de recuperación por loopback en `https://localhost:3334`. La LAN
permanece cerrada hasta iniciar TrinaxAI desde esa página local.

Consulta `trinaxai update --help` y `trinaxai uninstall --help` antes de automatizar mantenimiento. `uninstall --purge` puede eliminar datos, modelos, certificados y Ollama.

## Comandos slash interactivos

Dentro de `trinaxai` o `trinaxai chat`, escribe `/` para mostrar el menú. El
registro actual incluye:

| Comando | Uso |
|---|---|
| `/help` | Muestra el menú slash. |
| `/exit`, `/quit` | Sale del chat interactivo. |
| `/clear` | Borra la conversación en memoria. |
| `/chat`, `/general`, `/ollama` | Fija el chat general aislado. |
| `/agent [tarea]` | Fija el agente y opcionalmente ejecuta una tarea. |
| `/web [consulta]` | Fija una respuesta fundamentada en la web. |
| `/research [consulta]` | Fija investigación profunda multipaso. |
| `/rag [colección]` | Usa una colección indexada. |
| `/auto` | Restaura el enrutamiento automático por turno. |
| `/model [NOMBRE MODO]` | Elige modelo instalado y modo Ollama/RAG. |
| `/workspace [RUTA]` | Cambia el workspace del agente. |
| `cd [RUTA]` | Cambia el directorio de la sesión; las rutas relativas parten del directorio actual. |
| `/yolo` | Alterna la aprobación automática peligrosa. |
| `/thinking on|off` | Activa o desactiva el razonamiento eficiente; los turnos simples lo omiten. |
| `/index [RUTA]` | Indexa una carpeta. |
| `/memory` | Lista memorias persistentes. |
| `/collections` | Lista colecciones indexadas. |
| `/watch` | Muestra el estado del watcher. |
| `/status` | Muestra el estado de servicios. |

## Emparejar dispositivos LAN

Crea y administra emparejamientos desde el host mediante loopback:

```bash
trinaxai pair start
trinaxai pair start --scopes chat,read_private,web --ttl 180 --device-ttl-days 30
trinaxai pair list
trinaxai pair set ID_DISPOSITIVO --scopes chat,read_private,agent
trinaxai pair revoke ID_DISPOSITIVO
```

`pair` sin acción equivale a `pair start`. Muestra un código de un solo uso y un
enlace PWA. El código dura 60–900 segundos (`300` por defecto). Los scopes
iniciales son `chat,read_private`. Los adicionales opcionales son `web` y los
elevados `index`, `agent` y `modify`, que permiten a ese dispositivo modificar
el anfitrión (la CLI avisa al concederlos). `pair set` reemplaza los permisos de
un dispositivo existente. `system` y `agent_yolo` nunca se pueden conceder y se
rechazan incluso con credencial admin enviada desde LAN.

El navegador guarda las credenciales nuevas de pairing en una cookie
`HttpOnly; SameSite=Strict` con alcance `/api`; solo un bearer legacy se lee
del almacenamiento web durante la migración explícita de `/v1/pairing/me`. Una
CLI empaquetada que actúa como dispositivo remoto emparejado lee
`TRINAXAI_DEVICE_TOKEN` y envía
`X-TrinaxAI-Device-Token`; apunta `--api-url` a la base RAG del gateway, por
ejemplo `https://host:3334/api/rag`. No pongas tokens en el historial ni en TOML
versionado. Pairing representa una capability revocable, no una cuenta.

## Cambiar de red local

`trinaxai network` muestra el enlace PWA de la IP actual y una alternativa
`.local`. Tras cambiar de Wi-Fi, router o dirección LAN, ejecuta `trinaxai network
refresh` en el host para renovar HTTPS, CORS y la configuración activa. No borra
datos ni autoriza a todos los dispositivos; los scopes de pairing siguen
vigentes.

`trinaxai network` también indica si otros dispositivos pueden llegar a TrinaxAI.
Si lo permitiste y cambias de opinión, ejecuta `trinaxai network off` para
mantenerlo solo en este equipo (reinicia la app web); `trinaxai network refresh`
lo vuelve a permitir.

## Flujo del agente

`trinaxai agent` sigue el mismo flujo que otros agentes de código para terminal.

```bash
trinaxai agent                                 # sesión interactiva
trinaxai agent "añade una opción --verbose a cli.py"  # una tarea, solo la respuesta por stdout
echo "explica este repo" | trinaxai agent -p    # tarea desde stdin
trinaxai agent -p "arregla el test que falla" --output-format json
trinaxai agent --continue                      # retoma la última sesión
trinaxai agent --permission-mode plan          # solo lectura: pide primero un plan
```

| Función | Comportamiento |
|---|---|
| Transcripción | `● read_file(app.py)` seguido de `⎿ Read 120 lines`; la salida del shell se pliega a 8 líneas; cada turno termina con `✻ 12.3s · 3 tool calls · 90 tokens`. |
| Aprobaciones | Las ediciones muestran un diff unificado real; los comandos, el comando. Elige **Sí**, **Sí, y no volver a preguntar** (ediciones durante la sesión o un comando: los de solo lectura (`git status/diff/log/show`, `ls`, `cat`, `pytest`, …) se recuerdan por nombre y cualquier otro solo literalmente; los comandos compuestos con `;`, `\|`, `&&` o `$(…)` nunca se recuerdan) o **No**. |
| Modos de permisos | `default` pregunta, `accept-edits` aprueba ediciones de archivos, `plan` bloquea todo cambio, `yolo` aprueba todo. `Shift+Tab` alterna los tres primeros; `/mode` y `--permission-mode` fijan cualquiera. |
| Sin terminal | Las acciones peligrosas se rechazan salvo `--permission-mode accept-edits` o `--yolo`. |
| `@ruta` | Adjunta un archivo del workspace o el listado de una carpeta al prompt (Tab completa). Las rutas fuera del workspace se ignoran. |
| Lista de tareas | El modelo mantiene una lista visible en trabajos de varios pasos (`todo_write`; `/todos`). |
| Instrucciones del proyecto | `TRINAXAI.md`, `AGENTS.md` y `CLAUDE.md` en la raíz del workspace se añaden al prompt del sistema (8 000 caracteres en total). `/init` pide al agente escribir `TRINAXAI.md`. |
| Interrupción | `Ctrl-C` detiene el turno y revierte la conversación; pulsa `↑` para editar y reenviar. |
| Entrada | El historial persiste en `~/.local/share/trinaxai/agent_history`; `Alt+Enter` o una `\` final añade una línea; la barra inferior muestra modelo, workspace, modo y uso de contexto. |
| Comandos slash | `/help /clear /compact /model /mode /yolo /tools /status /todos /diff /init /resume /exit`. |
| Salida JSON | `--output-format json` imprime `result`, `status` (`complete` o `degraded`), `session`, `model`, `tool_calls`, `duration_s` y `tokens`. |

## Aislamiento del agente

Las herramientas de archivo de `trinaxai agent` permanecen en `--workspace`
después de resolver symlinks. Escritura/edición/terminal piden aprobación salvo
que el operador local pase `--yolo`. En Linux el terminal exige bubblewrap, no
tiene red, solo el workspace es escribible y un timeout termina el grupo de
procesos. En macOS/Windows o Linux sin bubblewrap, el terminal falla cerrado.
`TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1` concede acceso completo con los
permisos del usuario y no debe usarse en servicios alcanzables remotamente.

El agente HTTP restringe además raíces con `TRINAXAI_AGENT_WORKSPACE_ROOTS`; yolo
HTTP está apagado y nunca se permite desde un cliente no-loopback.

## Configuración TOML

Prioridad: `--config` → `TRINAXAI_CONFIG` → ruta nativa del sistema.

- Linux: `$XDG_CONFIG_HOME/trinaxai/config.toml` o `~/.config/trinaxai/config.toml`
- macOS: `~/Library/Application Support/TrinaxAI/config.toml`
- Windows: `%APPDATA%\TrinaxAI\config.toml`

```toml
[api]
base_url = "https://localhost:3333"
verify_tls = true

[defaults]
engine = "ollama"
model = ""  # vacío = automático: el modelo elegido para este equipo
collections = ["default"]
thinking = true

[ui]
color = "auto"

[session]
enabled = false
dir = ""
```

## Códigos de salida

- `0`: ejecución correcta.
- `1`: error de configuración, red, comando o servicio.
- `130`: interrupción mediante `Ctrl+C`.

`doctor` humano conserva salida diagnóstica. Para automatización,
`trinaxai doctor --strict --json` emite un único documento JSON y devuelve
nonzero si falla una comprobación crítica. Consulta la [guía de solución de
problemas](TROUBLESHOOTING.es.md) y la [guía de desarrollo](DEVELOPER_GUIDE.es.md).
`update` y `uninstall` pueden cambiar archivos instalados o borrar datos; lee su
salida de `--help` antes de automatizarlos. El comando reservado `trinaxai mcp`
termina con código `2` y no inicia un servidor MCP en esta versión; usa la API
HTTP o los comandos de CLI disponibles.

En una instalación nueva sin una carpeta del usuario indexada, el informe
humano de `doctor` muestra `Index built` como `INFO` e indica cómo ejecutar
`trinaxai index .`; es un estado normal de configuración, no un fallo del
servicio.
