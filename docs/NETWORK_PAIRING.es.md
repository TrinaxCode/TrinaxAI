<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="144" valign="middle"></a> · 🔗 Vinculación de red
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.3.0"><img src="https://img.shields.io/badge/version-1.3.0-006bbd" alt="Stable release: 1.3.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="NETWORK_PAIRING.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

El gateway PWA escucha en loopback por defecto. Ejecuta `trinaxai network refresh`
para habilitar el acceso LAN intencional (`TRINAXAI_PWA_HOST=0.0.0.0`) y reiniciar
el gateway; FastAPI y Ollama permanecen en loopback. Un dispositivo de la misma
Wi-Fi debe confiar en el certificado del anfitrión y usar un código de
vinculación de un solo uso antes de leer datos privados; también puede iniciar
una sesión de dispositivo nuevo limitada a chat/búsqueda web.

## Preparar El Anfitrión

Ejecuta esto desde el directorio instalado de TrinaxAI:

```bash
trinaxai network refresh
trinaxai network
```

El comando muestra la URL actual de la PWA y el certificado público que debe
confiar el teléfono o tablet. Si `mkcert` está instalado, usa la ruta de
`rootCA.pem`. Con el fallback de OpenSSL, usa
`chat-pwa/certs/trinaxai-local.crt`.

Nunca copies ni expongas ninguna de estas claves privadas:

- `rootCA-key.pem` del directorio de la CA de mkcert.
- `chat-pwa/certs/localhost-key.pem`.

Transfiere solo la CA/certificado público a dispositivos que controles,
preferiblemente mediante cable, AirDrop o una transferencia local cifrada. No
lo publiques en Internet ni lo adjuntes a un issue de soporte.

## Confiar En Un Teléfono

Las etiquetas exactas cambian según la versión del sistema. El certificado debe
instalarse como CA/perfil de confianza del usuario, no solo descargarse.

### Android

1. Transfiere el certificado público al teléfono.
2. Abre **Ajustes > Seguridad** (o **Seguridad y privacidad**) y elige **Instalar desde el almacenamiento** o **Instalar un certificado**.
3. Selecciona **Certificado de CA**, elige el archivo transferido y confirma con el bloqueo de pantalla.
4. Abre en Chrome la dirección `https://IP-LAN-DEL-HOST:3334` que muestra el comando.

### iPhone y iPad

1. Transfiere el certificado público como perfil o archivo de certificado.
2. Abre **Ajustes > Perfil descargado** e instálalo, o abre el archivo y sigue el aviso del perfil.
3. Ve a **Ajustes > General > Información > Ajustes de confianza de certificados** y activa la confianza total para la raíz instalada.
4. Abre en Safari la dirección `https://IP-LAN-DEL-HOST:3334` que muestra el comando.

Si el dispositivo sigue mostrando un error de certificado, elimina el perfil
anterior y repite el proceso después de `trinaxai network refresh`. El
certificado incluye la dirección LAN actual; cambiar de Wi-Fi puede requerir
uno nuevo.

## Vincular El Navegador

1. En el anfitrión, abre **Configuración > Avanzado > Dispositivo vinculado**, elige los permisos que tendrá el nuevo dispositivo y pulsa **Generar código de vinculación**.
2. En el teléfono, elige **Ya tengo TrinaxAI en otro dispositivo**.
3. Introduce el código de un solo uso, asigna un nombre y confirma.
4. Revisa, cambia o revoca el dispositivo desde la configuración del anfitrión, o usa `trinaxai pair list`, `trinaxai pair set ID --scopes ...` y `trinaxai pair revoke ID`.

## Permisos Por Dispositivo

Cada dispositivo vinculado tiene su propio conjunto de permisos, que eliges en
el anfitrión al generar el código y puedes editar después (**Permisos** junto al
dispositivo, o `trinaxai pair set`). El anfitrión pide confirmación antes de
conceder cualquier permiso que permita a un dispositivo modificar el equipo.

| Permiso | Permite al dispositivo |
|---|---|
| `chat` | Conversar con los modelos locales. |
| `read_private` | Usar el conocimiento indexado, la memoria, los chats sincronizados y las estadísticas. |
| `web` | Buscar en la web a través del anfitrión. |
| `index` | Indexar y vigilar carpetas, crear/vaciar/borrar colecciones y fuentes. Una carpeta vigilada debe estar dentro de las raíces de indexación configuradas en el anfitrión. |
| `agent` | Usar TrinaxAI Agent dentro de las raíces de trabajo permitidas, nunca en una carpeta que contenga archivos propios de TrinaxAI (instalación, `.env`, storage, credenciales). Cada acción peligrosa sigue requiriendo confirmación desde ese dispositivo. |
| `modify` | Editar la memoria y los ajustes de búsqueda web, y borrar adjuntos. |

Un código nuevo concede por defecto `chat`, `read_private` y `web`. `index`,
`agent` y `modify` están desactivados hasta que los actives para un dispositivo
concreto; un dispositivo vinculado antes de esta función conserva su
comportamiento anterior hasta que se los concedas de forma explícita. Los
cambios se aplican en la siguiente petición del dispositivo.

Apagar y reiniciar, gestionar modelos, borrar datos, abrir archivos del
anfitrión, vincular o revocar otros dispositivos y el modo de autoaprobación
(YOLO) del Agente nunca se pueden conceder. Solo funcionan desde
`https://localhost:3334`, y ni un dispositivo ni un token admin enviado por la
red pueden cambiar los permisos de un dispositivo.

Elegir **Configurar como dispositivo nuevo** crea una cookie revocable con
`chat`/`web`, sin historial sincronizado ni lecturas privadas. Vincúlalo después
desde el host si necesita RAG, memoria o chats sincronizados.

Si no quieres instalar una CA privada en el móvil, usa una VPN confiable o un
proxy inverso con certificado público. No desactives la verificación TLS ni
expongas los puertos `3333` o `11434`.

Para otros fallos de servicios, modelos, indexación o recuperación, continúa con
la [guía de solución de problemas y recuperación](TROUBLESHOOTING.es.md).
