<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🧭 Registro de cambios
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.3.0"><img src="https://img.shields.io/badge/version-1.3.0-006bbd" alt="Release estable: 1.3.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="CHANGELOG.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

Todos los cambios importantes de TrinaxAI se documentan aquí. El proyecto sigue
el formato de [Keep a Changelog](https://keepachangelog.com/).

## [Sin publicar]

## [1.4.0] — 2026-10-23

### Añadido

- `trinaxai ask` y el chat con RAG listan los archivos de los que sale la
  respuesta (`Fuentes: aurora.md, manual.pdf (p. 3)`), como ya hacía la app web.
  Una respuesta que dice que falta la información no lista ninguno.
- El instalador pregunta si otros dispositivos de tu red doméstica o local pueden
  abrir TrinaxAI. Por defecto, solo este equipo; un sí escribe
  `TRINAXAI_PWA_HOST=0.0.0.0` y cada dispositivo sigue necesitando un código de
  emparejamiento de un solo uso. Usa `--lan-access` / `--no-lan-access` (o
  `TRINAXAI_LAN_ACCESS`) para responder sin que pregunte. La administración del
  equipo se queda en este equipo elijas lo que elijas.
- Instalación guiada y centrada en el cliente. `trinaxai setup` empieza con una
  bienvenida y la elección de idioma (español o inglés), comprueba el espacio
  libre en disco y la conexión con GitHub, hace todas las preguntas opcionales
  al principio y muestra un plan de instalación para confirmar antes de cambiar
  nada. Sobre una instalación existente ofrece repararla, actualizarla o
  desinstalarla, y un `trinaxai` suelto antes de instalar ofrece configurarlo.
  El instalador de Windows ahora también pregunta el idioma. El lanzador
  reintenta las descargas fallidas, recurre a `curl` detrás de un proxy, acepta
  `--yes`, `--interactive` y `--language`, y responde en tu idioma.
- `trinaxai uninstall` acepta `--remove-app`, `--remove-env`, `--remove-certs`
  y `--dry-run`; `trinaxai update` acepta `--dry-run`.

- `trinaxai agent` ahora funciona como otros agentes de código para terminal:
  transcripción `● herramienta(args)` / `⎿ resultado` con estado "Trabajando…",
  diffs unificados reales al pedir aprobación, aprobación en tres opciones
  (sí / no volver a preguntar / no), modos de permisos (`default`,
  `accept-edits`, `plan`, `yolo`) con Shift+Tab, adjuntos `@archivo`, lista de
  tareas `todo_write`, instrucciones de proyecto (`TRINAXAI.md`, `AGENTS.md`,
  `CLAUDE.md`), historial persistente, Ctrl-C que revierte el turno,
  `/compact`, `/status`, `/diff`, `/init`, `/resume`, `--continue`/`--resume` y
  ejecución no interactiva con `-p`, stdin y `--output-format json`.

- Permisos por dispositivo: el anfitrión elige qué puede hacer cada dispositivo
  vinculado al generar el código y puede cambiarlo después en **Configuración →
  Avanzado → Dispositivos vinculados → Permisos** o con `trinaxai pair set`.
  Los nuevos permisos concedibles son `index` (indexar/vigilar carpetas y
  administrar colecciones y fuentes), `agent` (usar TrinaxAI Agent, que sigue
  pidiendo confirmación en cada acción peligrosa) y `modify` (editar la memoria
  y los ajustes de búsqueda web, borrar adjuntos). El anfitrión pide
  confirmación antes de conceder cualquiera de ellos.
- `PATCH /v1/pairing/devices/{id}` para reemplazar los permisos de un
  dispositivo (solo loopback).

- El instalador de Linux ahora instala `bubblewrap` (mejor esfuerzo) para que la
  terminal del Agente funcione de inmediato, y `trinaxai doctor` informa una
  fila «Agent shell sandbox» (informativa, nunca hace fallar `--strict`).
- `tests/fixtures/rag_docs_golden.json`: un benchmark de recuperación más
  exigente sobre la propia documentación de TrinaxAI (20 archivos, corpus en
  inglés, consultas en español e inglés, casos de abstención), ejecutado en
  vivo en CI junto al corpus de humo.
- `tests/test_route_scope_contract.py` fija el scope de dispositivo de cada
  ruta HTTP, de modo que añadir o reescopar un endpoint sea un cambio explícito
  y revisado.
- Equivalentes en español de `npm-package/README.md` y del ADR 0001, más una
  comprobación de `public_readiness.py` que exige que cada documento Markdown
  tenga su gemelo `.es.md` con los mismos encabezados y bloques de código.

### Cambiado

- `trinaxai ask` y `trinaxai chat` usan el modelo que el instalador eligió para
  tu equipo (`TRINAXAI_MODEL_GENERAL`) en lugar de un `qwen3.5:2b` fijo, que los
  dejaba en el modelo más pequeño incluso en equipos con margen para uno mejor.
  Para fijar uno, pon `model` en `[defaults]` de la config de la CLI.
- El `trinaxai agent` interactivo carga el modelo y su prompt fijo en segundo
  plano mientras escribes tu primera tarea. En una CPU de 4 núcleos con
  `qwen3.5:4b`, la primera tarea pasó de 82,6 s a 35,2 s tras el precalentamiento.
  Las ejecuciones de una sola tarea (`-p`) no cambian: la tarea se envía de inmediato.
- Paridad de documentación inglés/español: `CONFIGURATION`, `API_REFERENCE`,
  `CLI_REFERENCE`, `ENVIRONMENT_VARIABLES`, `SECURITY` y el README de la PWA
  tienen ahora las mismas secciones en ambos idiomas, y la CLI en español
  localiza el texto de ayuda restante (`pair`, `agent --permission-mode`),
  los encabezados de tablas y las líneas de estado.
- El perfil `8gb` usa ahora una ventana de 4096 tokens por defecto. Con 2048,
  tres fragmentos recuperados la llenaban y el modelo podía detenerse tras un token.
- El README y la guía de seguridad indican que la terminal del Agente solo está
  aislada en Linux y permanece desactivada en macOS y Windows salvo
  `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS=1`; las herramientas de archivos
  funcionan en todas.
- Los módulos de tests de casos límite se nombran por dominio en vez de
  `*_coverage*`; se eliminó el prototipo `trinaxai-ui-preview`, sin uso.
- Los módulos Python planos de la raíz (`config`, `trinaxai_core`,
  `trinaxai_errors`, `trinaxai_index_{documents,state,storage}`, el indexador,
  `service_manager` y `recovery_server`) viven ahora en el paquete `trinaxai`
  ([ADR 0001](adr/0001-python-package-layout.es.md)). Se conservan todas
  las rutas antiguas: los nombres de biblioteca son alias del mismo objeto de
  módulo, y `index.py`, `service_manager.py`, `recovery_server.py` y `rag_api.py`
  siguen en la raíz como lanzadores, de modo que instaladores, unidades, tareas
  programadas y la CLI que los ejecutan por ruta siguen funcionando tras una
  actualización, incluso antes de que `pip install -e .` renueve la instalación
  editable. Los scripts de instalación y actualización no cambian; el nuevo
  diseño solo se ha ejecutado en Linux, no en macOS ni en Windows.

### Corregido

- Una respuesta larga y correcta ya no se confunde con una negativa (ni pierde sus
  fuentes) solo porque una frase como «no está disponible» aparezca a mitad de la
  explicación. Las negativas solo se reconocen al comienzo de la respuesta.
- `./install.sh --dry-run` ya no anuncia un enlace LAN cuando elegiste mantener
  TrinaxAI solo en este equipo; lo indica, igual que la instalación real.
- `trinaxai models` muestra el tamaño de los modelos como `3.1 GB` en vez de bytes, y la
  fila de `trinaxai doctor` sobre el sandbox de la terminal del agente está traducida.
- El asistente de terminal ahora envía al agente de código las peticiones sobre
  archivos y control de versiones en vez de responderlas como chat normal:
  «arregla el bug en calc.py», «lee main.py y dime qué hace», «haz commit de los
  cambios». Las preguntas sobre esos temas («¿qué es un commit de git?», «¿qué
  hace next.js?») siguen en el chat.
- `trinaxai status` muestra un servicio que no está en marcha como `detenido` en
  lugar del contradictorio `detenido no encontrado`.
- La app web ya no te pide «preparar esta red» cuando TrinaxAI está solo en este
  equipo. Un cambio de dirección Wi-Fi o un certificado de red local
  desactualizado solo importa si otros dispositivos pueden conectarse, así que el
  aviso aparece únicamente si permitiste el acceso desde tu red local.
- Los errores nombran la causa real. Con TrinaxAI detenido, la CLI ya no dice
  «la conexión a Internet no está disponible» sino «No se puede conectar con el
  servicio local de TrinaxAI. Inícialo con: trinaxai start». Un modelo no
  instalado se informa como tal («El modelo 'x' no está instalado. Instálalo
  con: ollama pull x») en la CLI y en la API, en lugar de un genérico «inicia
  TrinaxAI» o «servicio externo no disponible», y «Reintenta» solo se sugiere
  cuando reintentar puede ayudar.
- `trinaxai index` ya no imprime las líneas internas `TRINAXAI_PROGRESS`, y
  `trinaxai collections list` muestra una fecha legible en vez de un número.
- Las respuestas ya no se ralentizan por usar demasiados hilos de CPU.
  `TRINAXAI_NUM_THREAD` valía 8 fijo; en un equipo de 4 núcleos la misma
  respuesta tardaba 76-93 s en lugar de 16 s. Ahora vale el menor entre 8 y las
  CPU que tienes.
- Se reconoce una negativa como «no tengo acceso a esa información» (también con
  el apóstrofo tipográfico y las formas habituales en español), así que
  TrinaxAI ya no muestra un archivo sin relación como fuente de una respuesta
  que dice que falta la información.
- `trinaxai stop`, `restart` y `status` ya no tocan procesos que no son de
  TrinaxAI. Buscaban palabras como `npm run dev`, `vite --host`, `node server.mjs`
  u `ollama` en cualquier parte de la línea de comandos, así que `status` podía
  dar la PWA por activa por el servidor de desarrollo de otro proyecto y `stop`
  terminaba ese servidor. Ahora un proceso cuenta solo si es el programa esperado
  y corre desde la carpeta de esta instalación (Linux y macOS; Windows conserva la
  coincidencia anterior).
- `uninstall.sh --remove-ollama` y `update.sh --remove-ollama` se terminaban a sí
  mismos: detenían Ollama con `pkill -f ollama`, que también coincide con su
  propio argumento `--remove-ollama`, y la eliminación quedaba a medias. Ahora
  (igual que los scripts de Windows) detienen Ollama por el nombre exacto del
  proceso.
- La comprobación previa de investigación ya no bloquea la API mientras consulta
  a Ollama.
- El prompt del Agente ahora indica usar la herramienta `git` para git, y una
  llamada a `git` que nunca puede funcionar (opción rechazada, subcomando
  desconocido) se informa al modelo de inmediato en vez de pedirte aprobarla.
- Las comprobaciones de fundamentación de revisión de código del agente reconocen la redacción de los docstrings de `turtle` en Python 3.13, de modo que la evidencia verificada sigue detectando afirmaciones falsas sobre `goto` en todos los intérpretes compatibles.
- El badge de versión del changelog apunta ahora a 1.3.0 en ambos idiomas.

### Seguridad

- `nltk` actualizado a 3.10.4 (GHSA-8mgp-746c-j5xp, recorrido de rutas en sus
  API de modelos) y eliminada la excepción de auditoría: `pip-audit` falla ante
  cualquier vulnerabilidad conocida.
- Se actualizaron `pypdf` a 6.21.2 (CVE-2026-115572, CVE-2026-115580,
  CVE-2026-115585) y `setuptools` a 84.1.0 (GHSA-xmj3-9gf7-h52w) en el lock de
  dependencias, y `zod` (solo desarrollo) a 4.6.7 (GHSA-mrhx-c7xc-m3w5) en el
  lockfile de la PWA, además de `undici` (7.30.1), `fast-uri` (3.1.9) y
  `serialize-javascript` (7.1.4), solo de desarrollo, tras nuevos avisos.
- El sandbox del terminal del Agente ahora monta `.git/config` y `.git/hooks`
  del workspace en solo lectura. Las herramientas de archivo ya se negaban a
  escribir metadatos de git, pero un comando de shell podía plantar alias o
  hooks que git ejecuta después por ti fuera del sandbox. `git add` y
  `git commit` siguen funcionando en el sandbox, con tu nombre y correo de git
  (si no, no ve tu configuración global de git).
- El Agente tiene una herramienta `git` que ejecuta git en tu equipo con tu
  propia configuración de git, así que puede hacer commit, push y pull cuando lo
  pides. Los comandos de lectura (status, diff, log) corren sin preguntar, los
  que cambian algo preguntan antes y todo lo que contacta un remoto pregunta
  siempre (sin «no volver a preguntar»; solo `--yolo` lo omite). Acepta una lista
  fija de subcomandos, rechaza opciones que ejecutan programas o leen fuera del
  repositorio, mantiene los hooks apagados salvo con `TRINAXAI_AGENT_GIT_HOOKS=1`,
  exige que el workspace sea la raíz del repositorio y rechaza los comandos
  remotos desde dispositivos emparejados.
- La API y el gateway de la PWA ahora rechazan peticiones cuya cabecera `Host`
  nombra un dominio ajeno (`421`). Esto impide que páginas con DNS rebinding
  lean datos privados cuando TrinaxAI funciona por HTTP (sin certificado local o
  en Docker). Añade nombres de host propios en `TRINAXAI_ALLOWED_HOSTS`.
- Endurecimiento del Agente: «no volver a preguntar» ya no se amplía a ejecutores
  de pruebas ni verificadores de tipos, las reglas de comandos que ejecutan
  código del workspace caducan una a una cuando el Agente edita un archivo, las
  herramientas de archivo rechazan cualquier grafía de `.git` y `/diff` ejecuta
  git dentro del sandbox (o con configuración forzada).
- `system` y el modo de autoaprobación (YOLO) del Agente siguen sin poder
  concederse a un dispositivo. Los permisos elevados solo los concede el
  operador en localhost, se ignoran en registros anteriores a este cambio hasta
  que se concedan de nuevo y un token admin enviado por la red no los desbloquea.
- Un dispositivo con `index` solo puede vigilar carpetas dentro de las raíces de
  indexación configuradas en el anfitrión.
- Un dispositivo con `agent` nunca puede usar ni explorar un workspace que
  contenga archivos propios de TrinaxAI (directorio de instalación, `.env`,
  storage, secretos de credenciales), aunque las raíces del anfitrión los
  incluyan.
- Borrar una fuente importada resuelve los symlinks antes de comprobar que la
  ruta sigue dentro de la carpeta de importaciones.

### Corregido

- Pasar `--language es` (en dos palabras) al instalador, actualizador o
  desinstalador ya no vuelve a preguntar el idioma.
- Responder "sí" o "s" a una pregunta con valor por defecto No ya no cuenta como
  No, y los avisos en español ahora muestran `[S/n]`.
- Los mensajes del instalador que aparecían en inglés en modo español están
  traducidos, y una instalación fallida indica que se puede ejecutar de nuevo
  sin riesgo.

## [1.3.0] — 2026-10-18

### Cambiado

- Se reorganizó la documentación pública alrededor de una única instalación
  npm, se aclararon el primer inicio y las operaciones por plataforma, se
  alinearon las guías en inglés y español y se eliminó el onboarding obsoleto
  de instaladores directos.
- Se estabilizaron las comprobaciones de release multiplataforma, las rutas de
  prueba en Windows y macOS y el estado del watcher.

### Corregido

- Estado compartido: un error pasajero de lectura ya no parece un almacén vacío
  que la siguiente sincronización sobrescribiría; los archivos corruptos se
  ponen en cuarentena.
- Restauración de backup: la reversión ya no puede borrar los datos originales
  si falla apartarlos.
- Actualización del código fuente: el marcador de reversión se elimina antes que
  el backup, así nunca se restaura un backup borrado a medias.
- Indexado: el worker del watcher sobrevive a falta de espacio y otros fallos de
  lote y sigue procesando la cola; los manifiestos y listas de colecciones
  ilegibles ya no se tratan como vacíos.
- PWA: el aviso de red se cierra bien tras preparar un enlace nuevo y el enlace
  de `trinaxai pair` abre Ajustes > Avanzado en lugar del chat.
- Voz: el texto leído en voz alta ya no se corta a mitad de palabra, las
  llamadas mantienen la pantalla activa al volver a la pestaña, el TTS del
  sistema elige la voz del idioma correcto y los audios temporales se limpian
  si falla la escritura.
- Piper usa ahora la API real del paquete `piper`, Coqui elige el modelo según
  el idioma y las conversiones simultáneas con LibreOffice ya no fallan.

## [1.2.6] — 2026-09-20

### Añadido

- Se añadió el lanzador npm verificado: `npm install --global trinaxai@latest` seguido de `trinaxai setup`.
- Se añadió un flujo para vincular un dispositivo nuevo en LAN y más cobertura de regresión para release y UI.

### Cambiado

- Se actualizaron las superficies de Chat y Agent, el traspaso de documentos, la voz, el feedback de indexación y la documentación bilingüe.
- La publicación valida y publica la CLI npm antes de hacer público el release de GitHub.

### Corregido

- Se reforzaron las cookies de dispositivos, los servicios de ciclo de vida, el runtime de investigación/RAG, los instaladores, las actualizaciones y los límites de búsqueda web.

## [1.2.5] — 2026-09-13

### Corregido

- `chat-pwa/node_modules` y `chat-pwa/dist` se conservan durante las
  actualizaciones para que los enlaces `.bin` generados por npm no se confundan
  con enlaces inseguros del código fuente.

## [1.2.4] — 2026-09-11

### Corregido

- Las instalaciones y actualizaciones pueden dejar pendientes las descargas de modelos con `--no-models`.
- Las cachés npm de macOS ya no dependen de entradas propiedad de root en `~/.npm`.
- Las comprobaciones del desinstalador funcionan con la canonicalización de `/tmp` en macOS y no dejan activo el recovery local.

## [1.2.3] — 2026-09-11

### Corregido

- El control de aprobación de Agent ahora permanece dentro del menú de
  herramientas móvil, exponiendo los mismos controles en pantallas estrechas y
  vistas ampliadas.

## [1.2.2] — 2026-09-11

### Cambiado

- Se separó la API del frontend por dominios detrás de una fachada estable
  `api.ts`.
- Se separaron el renderizado, ejecución, voz y contratos compartidos de Agent
  en módulos enfocados, conservando el comportamiento y las pruebas existentes.
- La generación, el streaming, el runtime, la indexación y el chat de RAG
  permanecen detrás de fachadas de compatibilidad pequeñas, sin seguir
  creciendo los puntos de entrada.

### Documentación

- Se añadió una guía bilingüe de solución de problemas y recuperación que mapea
  fallos comunes a acciones seguras, incluido el flujo **Abrir indexación** de la
  PWA para colecciones vacías.
- Se alinearon README, API, CLI, configuración, PWA, soporte y Docs integrada con
  los perfiles actuales, la confianza HTTPS, los jobs recuperables y el comando
  MCP reservado.

### Corregido

- Se hizo explícita la instalación de una línea para Linux, macOS y Windows,
  manteniendo el paquete del release fijado y verificado con SHA-256.
- Se corrigió el parseo de PowerShell 5.1 publicando los instaladores con BOM
  UTF-8 y los fallos de dependencias nativas ahora detienen claramente la instalación.
- Los errores del frontend y del ciclo de vida en macOS permanecen visibles en
  lugar de cerrar la terminal sin contexto accionable.
- Los ejemplos de checksum de PowerShell ahora interpretan `SHA256SUMS` línea por línea.

## [1.2.1] — 2026-09-02

### Cambiado

- Se promovió la release de escritorio validada a Production/Stable y se alinearon
  paquete Python, CLI, PWA, instaladores, actualizador y documentación en una versión.
- Se simplificó la instalación pública a un comando corto por plataforma, manteniendo
  archivos fuente verificados por checksum y firmados.
- Se fijó la clave pública del release en el repositorio y se cerraron las alertas
  de dependencias restantes.

### Corregido

- La evaluación RAG independiente ahora importa el paquete desde un checkout limpio,
  coherente con el contrato del wheel aislado de CLI.
- Las URLs de release de PowerShell se interpretan correctamente en Windows y el
  instalador rechaza paquetes fuente sin verificación o sin pinning.

## [1.2.0] — 2026-08-17

### Añadido

- Se añadió una traza de razonamiento desplegable con tiempo transcurrido,
  metadatos explícitos de finalización y continuación automática acotada para
  respuestas que alcanzan su límite de longitud.
- Se añadió selección autónoma entre búsqueda web, investigación profunda,
  conocimiento local y herramientas del Agente, conservando las preferencias
  explícitas del usuario.
- Se añadieron adjuntos de chat persistentes, alternativas para PDF en móvil,
  descarga de archivos Office y apertura con la aplicación nativa solo desde
  localhost.
- Se añadieron una página de recuperación loopback para instalaciones apagadas,
  un gestor de servicios de escritorio, perfiles según hardware y dry-runs del
  ciclo de vida de los instaladores.

### Cambiado

- La administración del equipo ahora falla cerrada y se limita a localhost. Los
  dispositivos LAN vinculados solo reciben scopes de chat, lectura privada y
  web; la PWA muestra controles según la capacidad efectiva informada por el
  servidor.
- El instalador de Windows ahora escribe los mismos perfiles canónicos `8gb`,
  `16gb`, `32gb` y `64gb` que el backend, y migra los valores legacy `max`/`ultra`.
- `trinaxai network` muestra ahora la ruta de la CA/certificado público que debe
  confiar un navegador LAN, con una guía bilingüe de pairing HTTPS para Android/iOS.
- Las guías en español e inglés de instalación, seguridad, API, CLI y pruebas
  describen los instaladores, recuperación, selección de modelos y límites LAN
  actuales.
- Se ampliaron el índice de documentación y las referencias de configuración/API,
  se alineó la Docs integrada de la PWA con el repositorio y se sustituyó su
  imagen de arquitectura pendiente por una vista accesible.

### Corregido

- Las respuestas largas de chat, RAG, investigación y Agente terminan con un
  estado explícito completo, por longitud, cancelado o con error, sin presentar
  silenciosamente una respuesta truncada como completa.
- Se mejoraron la navegación adaptable de la PWA, teclado y foco, etiquetas
  accesibles, funcionamiento sin conexión y acciones de adjuntos en escritorio,
  tableta y teléfono.
- La publicación de releases ahora compila archivos fuente, instaladores y el
  wheel solo de CLI con firma, los incluye en `SHA256SUMS` y verifica cada asset
  publicado después de descargarlo.

## [1.1.0] — 2026-08-05

### Añadido

- Se agregó `trinaxai network refresh` y un aviso accesible en la PWA para
  recuperar orígenes cacheados tras cambiar de Wi-Fi, router o dirección LAN.
- La copia offline permite borrar explícitamente su caché, datos locales y
  service worker para retirar una instalación guardada en una dirección anterior.
- Una dirección nueva detecta el estado existente del servidor y abre la
  recuperación por vinculación en vez de repetir la configuración inicial.
- La CLI ahora es traducible mediante `trinaxai_cli/i18n.py`, con cobertura en
  la aplicación, el cliente, el diagnóstico, la ayuda y la interfaz.
- La aplicación web publica un manifiesto por idioma, de modo que una
  instalación conserva su idioma en el lanzador.
- Se añadieron las guías en español del inventario de variables de entorno y
  del benchmark de modelos.

### Cambiado

- La documentación comunitaria (registro de cambios, contribución, seguridad,
  soporte, código de conducta y marca) se movió a `docs/`, dejando en la raíz
  solo los puntos de entrada, la configuración de build y ejecución, y los
  scripts de ciclo de vida.
- Los documentos traducidos usan una única convención `*.es.md`; `docs/es/`
  desapareció.
- `service_manager` devuelve códigos de salida correctos en las acciones de
  arranque y añade la acción `reload-network`.
- Los datos estáticos de traducción se empaquetan en su propio fragmento de
  JavaScript: el fragmento mayor baja de 384.5 KiB a 302.3 KiB sin cambiar el
  tamaño total.

### Eliminado

- Se retiró `install_ollama_16gb_profile.sh`, un envoltorio que solo delegaba en
  `install.sh --profile 16gb`. Usa ese comando directamente.

### Corregido

- `trinaxai doctor` limita a 10s el sondeo de servicios, así que un gestor lento
  se reporta como comprobación fallida en lugar de dejar el comando colgado.
- Las llamadas de voz y los ajustes de búsqueda web funcionan correctamente, y
  la cobertura de i18n se extiende al chat, el explorador de conocimiento, los
  ajustes y la vinculación.
- Los scripts de instalación, actualización, desinstalación y respaldo son más
  robustos en Linux, macOS y Windows.
- Las respuestas de identidad y autoría se resuelven de forma determinista, así
  que los modelos locales pequeños ya no las distorsionan.
- Las páginas en español enlazan destinos en español; todos los enlaces
  relativos del repositorio resuelven.

### Seguridad

- El material criptográfico, los certificados, las credenciales y los archivos
  de entorno quedan excluidos del indexado (`.key`, `.pem`, `.p12`, `.pfx`,
  `.netrc`, `credentials.json`, `secrets.json` y similares).
- Se actualizó `aiohttp` a 3.14.3, resolviendo CVE-2026-59881, CVE-2026-69243 y
  CVE-2026-69244.
- Se corrigieron tres avisos de severidad alta en el frontend:
  `brace-expansion` 5.0.9, `fast-uri` 3.1.5 y `undici` 7.29.0.

## [1.0.2] — 2026-08-01

### Corregido

- Inicialización del driver de contenedor de Buildx para publicar la imagen en
  GHCR con atestaciones de SBOM y procedencia.

## [1.0.1] — 2026-07-31

### Añadido

- Publicación de assets mediante un único workflow de release verificado.
- Cobertura del gateway de producción y pruebas multiplataforma de CLI,
  instaladores, servicios, cancelación, timeouts y rutas de error.

### Cambiado

- Los perfiles escalan embeddings Qwen3 oficiales desde 0.6B/1024d en equipos
  de poca memoria hasta 4B/2560d en equipos de 32/64 GB.
- Docker Compose puede iniciar con valores seguros aunque no exista `.env`.

### Corregido

- Se reforzaron timeouts de inferencia, verificación TLS, identidad del proxy,
  errores de API, limpieza de recursos y checks de Windows/macOS/Linux.

## [1.0.0] — 2026-07-21

### Añadido

- PWA local-first con chat de Ollama, RAG citado, investigación web opcional,
  visión, voz y emparejamiento de dispositivos por capacidades.
- Indexación híbrida de proyectos y documentos con colecciones, chunks de código
  con AST, progreso persistente, cancelación, reintento y publicación incremental segura.
- Una sola CLI empaquetada, `trinaxai`, para chat, agente, indexación,
  investigación, memoria, colecciones, watcher, pairing, diagnóstico y servicios.
- Agente con herramientas limitado a workspaces aprobados, confirmación para
  acciones peligrosas y shell Linux aislada sin red.
- Instaladores y supervisión multiplataforma para Linux, macOS y Windows, además
  de documentación bilingüe de producto y técnica.

### Cambiado

- Los perfiles automáticos cubren desde equipos con poca memoria hasta sistemas
  con 64+ GB y usan embeddings multilingües `qwen3-embedding:0.6b` por defecto.
- La PWA incluye iconos de instalación renovados, un modo llamada más claro y
  animaciones accesibles que respetan la reducción de movimiento.
- La CLI mantiene HTTPS verificado y acepta autoridades privadas mediante
  `--ca-file` o `TRINAXAI_CA_FILE`.

### Corregido

- Los saludos simples en modo automático de la CLI usan el chat normal de Ollama
  en vez de forzar una búsqueda RAG vacía.
- Los fallos de generación, RAG, investigación, agente, memoria, pairing,
  servicios y búsqueda web terminan de forma predecible y conservan el estado.
- Los streams del micrófono, nodos de Web Audio, timers, previews y listeners de
  subida se liberan al cancelar, navegar o recibir un error.
- Los documentos y subidas grandes usan lotes, timeouts y limpieza acotados; una
  indexación fallida nunca publica una generación parcial.
- El paquete expone solo la CLI modular y genera wheel, archivo fuente,
  instaladores y checksums coherentes.

### Seguridad

- Las URLs base de Ollama se restringen centralmente a endpoints HTTP(S) válidos
  antes del acceso de red desde backend, CLI, agente y diagnósticos.
- Las aserciones del proxy se firman, caducan y son de un solo uso; las operaciones
  protegidas exigen pairing con scope o credenciales administrativas explícitas.
- CI revisa dependencias Python/frontend, hallazgos estáticos de severidad alta,
  secretos, paquetes, flujos del navegador y preparación para release pública.

[1.2.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.2
[1.2.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1
[1.2.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0
[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.1.0
[1.0.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.2
[1.0.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.1
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
