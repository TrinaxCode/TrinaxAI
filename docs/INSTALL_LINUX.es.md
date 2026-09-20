<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🐧 Linux
</h1>

<p align="center"><sub><a href="INSTALL_LINUX.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="TROUBLESHOOTING.es.md">Problemas</a></sub></p>

Esta guía explica los requisitos de Linux, la instalación npm, el primer
inicio y las operaciones de servicio. Cubre Ubuntu, Debian, Fedora, Arch,
openSUSE y distribuciones similares.

## Estado de soporte

Linux es la plataforma principal de CI. El release comprueba backend, frontend,
CLI, preparación pública, seguridad y el lanzador npm en Linux. Los drivers,
permisos y la velocidad de descarga de modelos dependen de tu equipo.

## Requisitos

| Recurso | Mínimo | Recomendado |
| --- | ---: | ---: |
| Node.js y npm | Node.js 22 con npm | Node.js LTS actual |
| RAM | 8 GB | 16 GB o más |
| Disco libre | 5 GB | 10–25 GB |
| Arquitectura | x86_64 o arm64 | Un destino compatible con Ollama |

No necesitas Git para una instalación normal. Instala los drivers NVIDIA o AMD
antes de descargar modelos grandes. TrinaxAI también funciona solo con CPU.

Comprueba las herramientas antes de configurar:

~~~bash
node --version
npm --version
~~~

## Instalar con npm

Usa la misma ruta pública en todas las plataformas compatibles:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

El lanzador npm descarga el instalador correspondiente y verifica su checksum
SHA-256. Después comprueba Python, Node.js, Ollama, almacenamiento,
modelos, certificados y la PWA. Acepta el aviso del gestor de paquetes cuando
Linux pida permisos.

Usa opciones solo si las necesitas:

~~~bash
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
~~~

El lanzador npm es la entrada compatible para usuarios finales. No ejecutes
install.sh desde un checkout para una instalación normal; esa ruta pertenece a
los internals del release y al desarrollo.

## Primer inicio

Comprueba los servicios:

~~~bash
trinaxai doctor
trinaxai status
~~~

Abre https://localhost:3334. El navegador puede pedirte que confíes en el
certificado local. Si aplazaste los modelos, ejecuta setup de nuevo sin
--no-models.

Indexa una carpeta y haz una pregunta con citas:

~~~bash
trinaxai index ~/Documents
trinaxai ask "Resume mis archivos indexados" --engine rag
~~~

## Operaciones de servicio en Linux

La instalación administrada guarda la aplicación en XDG_DATA_HOME/trinaxai,
normalmente ~/.local/share/trinaxai. También reconoce una instalación antigua
en ~/trinaxai. Usa la CLI desde cualquier carpeta:

~~~bash
trinaxai start
trinaxai stop
trinaxai restart
trinaxai status
~~~

La configuración puede activar el autoarranque con systemd de usuario. Mantén
la administración del host solo en localhost salvo que entiendas el modelo de
seguridad.

## Acceso desde la red local

Para emparejar un teléfono o navegador de la misma red, actualiza la dirección
y el certificado local:

~~~bash
trinaxai network refresh
trinaxai pair start
~~~

Sigue [Pairing LAN](NETWORK_PAIRING.es.md). No expongas directamente los
puertos 3333, 3334 ni 11434 a Internet.

## Actualizar, respaldar y eliminar

Crea una copia antes de actualizar o modificar el índice:

~~~bash
trinaxai update
trinaxai doctor --strict
trinaxai uninstall
~~~

La desinstalación predeterminada conserva índices y modelos de Ollama. Usa las
opciones de purge solo después de leer la [referencia CLI](CLI_REFERENCE.es.md).

## Docker y desarrollo desde código

Docker Compose y los checkouts del código son rutas separadas para operadores y
desarrolladores. No son instaladores alternativos para usuarios finales.
Consulta la [guía del desarrollador](DEVELOPER_GUIDE.es.md) para trabajar desde
un checkout y la documentación de compose del repositorio para contenedores.

## Problemas comunes

| Síntoma | Acción |
| --- | --- |
| Falta npm o node | Instala un Node.js LTS activo, abre una terminal nueva y reintenta |
| Ollama no está listo | Ejecuta trinaxai doctor y revisa el servicio de Ollama |
| El certificado de la PWA es rechazado | Abre la URL que muestra trinaxai network y confía en la CA local |
| Un modelo es demasiado lento | Elige un perfil menor con trinaxai setup --profile 8gb |
| El servicio está desconectado | Ejecuta trinaxai status y trinaxai doctor --strict |

Si el problema continúa, sigue [Solución de problemas](TROUBLESHOOTING.es.md) e
incluye una salida de diagnóstico redactada al pedir soporte.
