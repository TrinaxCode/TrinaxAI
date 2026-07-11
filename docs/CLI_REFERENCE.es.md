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
trinaxai research --query "Compara los módulos de seguridad" --depth 2 --collections default
```

`--engine general` es un alias del chat directo con Ollama; `rag` usa documentos indexados. `--collections` acepta IDs separados por comas.

## Indexación y exploración

```bash
trinaxai index . --collection default
trinaxai index ~/Documents --collection documentos --append
trinaxai browse list-collections
trinaxai browse list-files --collection default
trinaxai browse show-chunks --collection default --file README.md --limit 20
trinaxai obsidian --vault ~/Notas --collection notas
```

`--append` añade cambios sin eliminar del índice los archivos que ya no están en la fuente. Sin esta opción, el indexador mantiene el índice sincronizado con la carpeta.

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
verify_tls = false

[defaults]
engine = "ollama"
model = "qwen2.5-coder:3b"
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

Para resolver problemas, ejecuta `trinaxai --verbose doctor` y revisa también la [guía de desarrollo](DEVELOPER_GUIDE.es.md).

`trinaxai mcp` existe como placeholder y todavía no configura una integración MCP utilizable.
