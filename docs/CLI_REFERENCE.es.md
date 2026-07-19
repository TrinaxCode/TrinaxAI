# Referencia de la CLI de TrinaxAI

La CLI `trinaxai` ofrece chat directo con Ollama, consultas RAG, indexación, administración de memoria y colecciones, y control de servicios. Requiere Python 3.10 o superior.

## Instalación y ayuda

```bash
python -m pip install -e .
trinaxai --help
trinaxai help
trinaxai COMMAND --help
```

Sin subcomando, `trinaxai` abre el chat interactivo. Las opciones globales deben colocarse antes del subcomando:

```bash
trinaxai --api-url https://localhost:3333 --insecure ask "Estado del índice"
```

| Opción global | Uso |
|---|---|
| `--api-url URL` | Sobrescribe la URL de la API RAG. |
| `--install-root PATH` | Indica la raíz de una instalación completa. |
| `--insecure` | Desactiva la validación TLS; úsalo solo con certificados locales de confianza conocida. |
| `--config PATH` | Carga un TOML concreto. |
| `--no-color` | Desactiva color ANSI. |
| `-v`, `--verbose` | Activa logs de depuración. |
| `--version` | Muestra la versión. |

## Chat y consultas

```bash
trinaxai chat
trinaxai chat --prompt "Resume este proyecto" --engine rag --collections default,docs
trinaxai ask "Escribe una prueba para esta función" --engine ollama
trinaxai agent --workspace . --prompt "Corrige las pruebas"
trinaxai research --query "Compara los módulos de seguridad" --depth 2 --collections default
```

`--engine general` es un alias del chat directo con Ollama; `rag` usa documentos indexados. `--collections` acepta IDs separados por comas.

`research` intenta leer texto acotado de las páginas (`full_page`) y conserva el
extracto del buscador como fallback (`snippet_only`); las fuentes indican cuál
se usó.

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
| `/yolo` | Alterna la aprobación automática peligrosa. |
| `/index [RUTA]` | Indexa una carpeta. |
| `/memory` | Lista memorias persistentes. |
| `/collections` | Lista colecciones indexadas. |
| `/watch` | Muestra el estado del watcher. |
| `/status` | Muestra el estado de servicios. |

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

## Emparejar dispositivos LAN

Crea y administra emparejamientos desde el host (o con la supercredencial
admin):

```bash
trinaxai pair start
trinaxai pair start --scopes chat,read_private,index --ttl 180 --device-ttl-days 30
trinaxai pair list
trinaxai pair revoke ID_DISPOSITIVO
```

`pair` sin acción equivale a `pair start`. Muestra un código de un solo uso y un
enlace PWA. El código dura 60–900 segundos (`300` por defecto). Los scopes
iniciales son `chat,read_private`; los elevados disponibles incluyen `index`,
`system`, `agent` y `web`. `agent_yolo` queda reservado a política local y nunca vuelve
automática la aprobación de herramientas HTTP remotas.

El navegador conserva el bearer en `localStorage` para mantener su identidad
revocable entre reinicios. Una CLI empaquetada
que actúa como dispositivo remoto emparejado lee `TRINAXAI_DEVICE_TOKEN` y envía
`X-TrinaxAI-Device-Token`; apunta `--api-url` a la base RAG del gateway, por
ejemplo `https://host:3334/api/rag`. No pongas tokens en el historial ni en TOML
versionado. Pairing representa una capability revocable, no una cuenta.

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
trinaxai export --session SESSION --format md --output conversacion.md
```

El watcher requiere `watchdog`, incluido en las dependencias de servidor. La exportación disponible actualmente es Markdown.

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

Consulta `trinaxai update --help` y `trinaxai uninstall --help` antes de automatizar mantenimiento. `uninstall --purge` puede eliminar datos, modelos, certificados y Ollama.

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
model = "qwen2.5-coder:1.5b"
collections = ["default"]

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
nonzero si falla una comprobación crítica. Consulta también la
[guía de desarrollo](DEVELOPER_GUIDE.es.md). MCP no se anuncia como comando
utilizable en esta versión.
