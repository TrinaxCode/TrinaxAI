<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · ✍️ Firma de releases
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.0"><img src="https://img.shields.io/badge/version-1.2.0-006bbd" alt="Current candidate: 1.2.0"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="RELEASE_SIGNING.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

El workflow de release publica archivos fuente, instaladores shell y PowerShell
y un wheel de Python. La publicación estable falla cerrada: cada archivo
descargable debe tener una firma separada verificada antes de subirlo.

## Secretos De GitHub Actions

Configura estos secretos del repositorio u organización antes de crear un tag
estable:

| Secreto | Uso |
| --- | --- |
| `RELEASE_SIGNING_KEY_BASE64` | Clave privada GPG de release codificada en Base64 |
| `RELEASE_SIGNING_KEY_PASSPHRASE` | Contraseña de la clave GPG del release |
| `RELEASE_SIGNING_KEY_FINGERPRINT` | Huella completa, sin espacios, de la clave pública de release; el workflow falla si la clave importada no coincide |

El job firma con GPG los archivos fuente, instaladores, wheels y `SHA256SUMS`, y
verifica cada firma antes de publicar. Las imágenes de contenedor usan firma y
verificación Sigstore sin clave.

Si falta o es inválido cualquier secreto requerido, el workflow falla antes de
publicar. Nunca imprimas secretos ni guardes certificados o claves privadas en el
repositorio.

El workflow primero prepara un release en borrador y rechaza archivos remotos
faltantes o obsoletos al comparar el conjunto exacto de archivos y cada firma
separada. Solo después publica y repite las comprobaciones sobre el release
público. Todos los archivos fuente e instaladores están incluidos en
`SHA256SUMS`.

El comprobador de preparación usa deliberadamente comprobaciones sin
dependencias y ancladas a líneas de comandos críticos, en vez de un parser YAML
completo; no sustituye revisar la estructura YAML fuera de esos comandos.

## Estado del ancla de confianza

Este repositorio todavía no contiene una huella ni una clave pública fijada.
`TrinaxAI-release-signing-key.asc` y su correspondiente
`TrinaxAI-release-signing-key.fingerprint` son archivos del mismo release, así
que no prueban su autenticidad de forma independiente. No uses la huella
descargada del mismo release como ancla de confianza. Obtén la huella esperada
por un canal independiente (por ejemplo, una clave previamente confiable o un
anuncio del mantenedor) antes de importar o ejecutar cualquier archivo.

## Verificar una descarga

El workflow de releases exige firmas separadas. Para usuarios finales, la
comprobación de `SHA256SUMS` de las guías de instalación es obligatoria antes de
ejecutar. Esa comprobación protege la integridad, pero no autentica el release.
La verificación GPG separada es un control adicional opcional cuando
la huella de la clave se obtuvo y se confió por un canal independiente. Sin esa
ancla independiente GPG no puede demostrar autenticidad; nunca trates una
clave o huella descargada del mismo release como ancla de confianza.

```bash
version=v1.2.0
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/${version}"
curl -fLO "${base}/TrinaxAI-release-signing-key.asc"
trusted_fingerprint="PEGA_LA_HUELLA_PUBLICADA_POR_OTRO_CANAL"
actual_fingerprint="$(gpg --show-keys --with-colons TrinaxAI-release-signing-key.asc | awk -F: '$1 == "fpr" { print $10; exit }')"
trusted_fingerprint="$(printf '%s' "$trusted_fingerprint" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')"
test "${actual_fingerprint^^}" = "$trusted_fingerprint"
gpg --import TrinaxAI-release-signing-key.asc
curl -fLO "${base}/TrinaxAI-release-signing-key.fingerprint"
curl -fLO "${base}/SHA256SUMS"
curl -fLO "${base}/SHA256SUMS.asc"
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum --check SHA256SUMS
```

Después de descargar el instalador o archivo exacto y su `.asc`, verifica esa
firma separada con la clave importada antes de abrirlo o ejecutarlo:

```bash
asset="TrinaxAI-${version#v}-installer.sh"
curl -fLO "${base}/${asset}" "${base}/${asset}.asc"
gpg --verify "${asset}.asc" "$asset"
```

El actualizador valida los metadatos HTTPS del release y el manifiesto SHA-256,
y exige un SHA-256 proporcionado por el operador para toda URL de archivo
personalizada, incluido `file://`.
No puede establecer autenticidad de firma de extremo a extremo hasta que este
repositorio publique un ancla de confianza fijada.
