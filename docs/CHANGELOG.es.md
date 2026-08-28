# Registro de cambios

[English](CHANGELOG.md)

Todos los cambios importantes de TrinaxAI se documentan aquí. El proyecto sigue
el formato de [Keep a Changelog](https://keepachangelog.com/).

## [Sin publicar]

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
- La publicación de releases ahora compila todos los Gestores nativos antes de
  crear el release de GitHub, los incluye en `SHA256SUMS` y verifica sus URLs de descarga.

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

[1.2.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0
[1.1.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.1.0
[1.0.2]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.2
[1.0.1]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.1
[1.0.0]: https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.0.0
