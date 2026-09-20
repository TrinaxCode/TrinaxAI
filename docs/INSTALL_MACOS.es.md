<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🍎 macOS
</h1>

<p align="center"><sub><a href="INSTALL_MACOS.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="TROUBLESHOOTING.es.md">Problemas</a></sub></p>

Esta guía cubre los requisitos de macOS, la instalación npm, el primer inicio,
la red local y las operaciones de servicio en Intel y Apple Silicon.

## Estado de soporte

macOS está incluido en las comprobaciones de backend, frontend, CLI, Python,
seguridad y lanzador npm. Apple Silicon usa memoria unificada cuando la
configuración elige un perfil de modelos.

## Requisitos

| Recurso | Mínimo | Recomendado |
| --- | ---: | ---: |
| Node.js y npm | Node.js 22 con npm | Node.js LTS actual |
| RAM | 8 GB | 16 GB o más |
| Disco libre | 5 GB | 10–25 GB |
| CPU | Intel o Apple Silicon | Apple Silicon para modelos locales |

Mantén macOS actualizado y permite que Terminal acceda a las carpetas que
quieras indexar. Comprueba las herramientas antes de configurar:

~~~bash
node --version
npm --version
~~~

## Instalar con npm

Usa la misma ruta pública que en Linux y Windows:

~~~bash
npm install -g trinaxai@latest
trinaxai setup
~~~

El lanzador npm descarga el instalador correspondiente y verifica su checksum
SHA-256. La configuración prepara Python, Node.js, Ollama, la PWA,
los certificados locales y los modelos elegidos.

Usa opciones solo cuando las necesites:

~~~bash
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
~~~

El lanzador npm es la entrada compatible para usuarios finales. El instalador
shell es código interno del release; no lo ejecutes directamente en una
instalación normal.

## Primer inicio

Ejecuta la comprobación de salud:

~~~bash
trinaxai doctor
trinaxai status
~~~

Abre https://localhost:3334. Confía en el certificado local en el navegador
cuando macOS pida autorización. Después indexa una carpeta:

~~~bash
trinaxai index ~/Documents
trinaxai ask "Resume mis archivos indexados" --engine rag
~~~

## Operaciones de servicio en macOS

Usa la CLI desde cualquier carpeta:

~~~bash
trinaxai start
trinaxai stop
trinaxai restart
trinaxai status
~~~

La instalación administrada usa un ciclo de vida launchd a nivel de usuario.
No borres la carpeta de la aplicación mientras haya servicios activos. Detén
TrinaxAI primero.

## Acceso desde la red local

Actualiza la dirección y el certificado local antes de emparejar otro dispositivo:

~~~bash
trinaxai network refresh
trinaxai pair start
~~~

Sigue [Pairing LAN](NETWORK_PAIRING.es.md). Mantén privados los puertos y usa
una VPN en redes que no controles.

## Actualizar, respaldar y eliminar

Usa la CLI para el mantenimiento:

~~~bash
trinaxai update
trinaxai doctor --strict
trinaxai uninstall
~~~

La desinstalación predeterminada conserva índices y modelos de Ollama. Lee la
[referencia CLI](CLI_REFERENCE.es.md) antes de usar opciones de purge.

## Problemas comunes

| Síntoma | Acción |
| --- | --- |
| Falta npm o node | Instala un Node.js LTS activo y abre una terminal nueva |
| macOS bloquea una acción local | Revisa Sistema, Privacidad y seguridad, y reintenta |
| El certificado de la PWA es rechazado | Abre la URL de trinaxai network y confía en la CA local |
| Un modelo usa demasiada memoria | Repite setup con un perfil menor |
| El servicio está desconectado | Ejecuta trinaxai status y trinaxai doctor --strict |

Para consultar una tabla completa, lee [Solución de problemas](TROUBLESHOOTING.es.md).
