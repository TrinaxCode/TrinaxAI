<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🪟 Windows
</h1>

<p align="center"><sub><a href="INSTALL_WINDOWS.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="TROUBLESHOOTING.es.md">Problemas</a></sub></p>

Esta guía cubre los requisitos de Windows, la instalación npm, el primer
inicio, los servicios, el firewall y los límites de WSL.

## Estado de soporte

Windows está incluido en las comprobaciones de backend, frontend, CLI, Python,
PowerShell, seguridad y lanzador npm. La configuración usa un supervisor local
de procesos y mantiene la PWA y la API en el host por defecto.

## Requisitos

| Recurso | Mínimo | Recomendado |
| --- | ---: | ---: |
| Windows | Windows 10 | Windows 11 |
| Node.js y npm | Node.js 22 con npm | Node.js LTS actual |
| RAM | 8 GB | 16 GB o más |
| Disco libre | 5 GB | 10–25 GB |
| Shell | PowerShell 5.1+ | PowerShell 7 |

Usa una ventana normal de PowerShell para configurar TrinaxAI. Windows puede
pedir permisos de administrador al instalar Python, Ollama o dependencias.

Comprueba las herramientas:

~~~powershell
node --version
npm --version
~~~

## Instalar con npm

Usa la misma ruta pública que en Linux y macOS:

~~~powershell
npm install -g trinaxai@latest
trinaxai setup
~~~

El lanzador npm descarga el instalador correspondiente y verifica su checksum
SHA-256. La configuración prepara Python, Ollama, la PWA, los
certificados y los modelos elegidos.

Usa opciones solo cuando las necesites:

~~~powershell
trinaxai setup --no-models
trinaxai setup --no-start
trinaxai setup --profile 16gb
trinaxai setup --install-dir D:\Apps\TrinaxAI
~~~

El lanzador npm es la entrada compatible para usuarios finales. No descargues
ni ejecutes install.ps1 directamente en una instalación normal.

## Primer inicio

Comprueba los servicios:

~~~powershell
trinaxai doctor
trinaxai status
~~~

Abre https://localhost:3334 y confía en el certificado local en el navegador.
Después indexa una carpeta y haz una pregunta:

~~~powershell
trinaxai index "$HOME\Documents"
trinaxai ask "Resume mis archivos indexados" --engine rag
~~~

## Operaciones de servicio en Windows

Usa la CLI desde cualquier ventana de PowerShell:

~~~powershell
trinaxai start
trinaxai stop
trinaxai restart
trinaxai status
~~~

La instalación administrada usa un supervisor local de procesos. Cerrar
PowerShell no detiene los servicios que haya iniciado la configuración.

## Firewall y red local

El acceso local funciona mediante localhost. Para emparejar otro dispositivo,
actualiza la dirección y crea un código de un solo uso:

~~~powershell
trinaxai network refresh
trinaxai pair start
~~~

Permite únicamente las reglas de red local o privada que entiendas. No
reenvíes los puertos 3333, 3334 ni 11434 a Internet.

## Actualizar, respaldar y eliminar

Usa la CLI:

~~~powershell
trinaxai update
trinaxai doctor --strict
trinaxai uninstall
~~~

La desinstalación predeterminada conserva índices y modelos de Ollama. Lee la
[referencia CLI](CLI_REFERENCE.es.md) antes de usar opciones de purge o
remove-data.

## WSL

WSL no es necesario para instalar TrinaxAI en Windows. Si eliges WSL, sigue la
guía de Linux dentro de la distribución y mantén separados sus archivos, red,
certificados y servicios de la instalación de Windows.

## Problemas comunes

| Síntoma | Acción |
| --- | --- |
| Falta npm o node | Instala un Node.js LTS activo y abre un PowerShell nuevo |
| No se reconoce un comando tras npm install | Reinicia PowerShell para aplicar los cambios de PATH |
| El certificado de la PWA es rechazado | Abre la URL de trinaxai network y confía en la CA local |
| Windows Firewall bloquea un dispositivo | Permite solo la regla de red privada que necesitas |
| El servicio está desconectado | Ejecuta trinaxai status y trinaxai doctor --strict |

Para consultar la tabla completa, lee [Solución de problemas](TROUBLESHOOTING.es.md).
