# TrinaxAI

[English](https://github.com/TrinaxCode/TrinaxAI/blob/main/npm-package/README.md) · **Español**

Instala TrinaxAI en Linux, macOS o Windows con npm:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

El paquete es un lanzador verificado. No incluye el backend ni la PWA.
El comando setup descarga el instalador oficial de la versión correspondiente
desde GitHub, verifica su suma SHA-256 y ejecuta la instalación de la plataforma.

## Qué hace setup

La instalación es guiada y está disponible en inglés y español:

1. Una bienvenida y la pregunta de idioma (omítela con `--language en|es`).
2. Comprobaciones previas: espacio libre en disco y conexión con GitHub. Si un
   proxy bloquea la descarga directa, el lanzador reintenta con `curl`.
3. Todas las preguntas opcionales al principio: descarga de modelos, iniciar
   ahora, iniciar con el equipo, una comprobación semanal de actualizaciones que
   solo comprueba y nunca instala sin ti, y si otros dispositivos de tu red pueden
   abrir TrinaxAI (desactivado por defecto).
4. Un plan de instalación que debes confirmar. No cambia nada antes de que lo aceptes.
5. La instalación en sí, que se ejecuta sin más atención.

Si TrinaxAI ya está instalado, `trinaxai setup` ofrece repararlo o reinstalarlo
(se conservan tus datos y tu configuración), actualizarlo, desinstalarlo o
cancelar. Ejecutar `trinaxai` solo, antes de instalar, ofrece instalarlo.

## Primer uso

Comprueba la instalación y abre la aplicación local:

~~~bash
trinaxai doctor
trinaxai status
~~~

Abre https://localhost:3334. En la primera visita puede que se te pida confiar
en el certificado HTTPS local.

## Opciones de setup

Pasa opciones después de setup cuando necesites cambiar el flujo predeterminado:

~~~bash
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
trinaxai setup --language es
trinaxai setup --dry-run
trinaxai setup --yes
~~~

`--yes` (alias `--non-interactive`) acepta las respuestas recomendadas y no
pregunta nada, pensado para scripts y CI.

Ejecuta `trinaxai setup --help` para ver la lista completa de opciones.

## Después de la instalación

El lanzador reenvía los comandos a la CLI de TrinaxAI instalada:

~~~bash
trinaxai chat
trinaxai ask "Resume mis archivos indexados" --engine rag
trinaxai index ./documentos
trinaxai doctor --strict
trinaxai update
trinaxai update --dry-run
trinaxai uninstall
trinaxai uninstall --dry-run
~~~

`trinaxai uninstall` pregunta qué eliminar y por defecto conserva tus datos,
índices y modelos. Cuando termina, `npm uninstall -g trinaxai` elimina el propio
lanzador.

Usa `trinaxai --help` para ver la lista completa de comandos y la
[referencia de la CLI](https://github.com/TrinaxCode/TrinaxAI/blob/main/docs/CLI_REFERENCE.es.md)
para un uso detallado.

## Requisitos

El lanzador funciona con Node.js 18 o superior. Usa Node.js 22 o superior para la
instalación completa, que comprueba y prepara el resto del entorno local, incluidos
Python, Ollama, la PWA, los certificados y los perfiles de modelos. El paquete
admite Linux, macOS y Windows.

## Seguridad

Las descargas usan HTTPS y el lanzador verifica la suma de comprobación de la
versión antes de ejecutar el instalador de la plataforma. No sustituyas la URL de
la versión ni canalices a una shell un script sin verificar.

## Enlaces

- [Repositorio de TrinaxAI](https://github.com/TrinaxCode/TrinaxAI)
- [Documentación](https://github.com/TrinaxCode/TrinaxAI/tree/main/docs)
- [Seguimiento de incidencias](https://github.com/TrinaxCode/TrinaxAI/issues)
- [Sitio web](https://www.trinaxai.app/)
