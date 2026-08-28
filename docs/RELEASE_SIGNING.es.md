# Firma De Releases

[English](RELEASE_SIGNING.md)

El workflow de release compila los Gestores de Linux, Windows y macOS en runners
nativos antes de publicar el release. La publicación estable falla cerrada:
cada archivo descargable debe tener una firma separada verificada antes de subirlo.

## Secretos De GitHub Actions

Configura todos estos secretos del repositorio u organización antes de crear un
tag estable:

| Secreto | Uso |
| --- | --- |
| `WINDOWS_SIGNING_CERTIFICATE_BASE64` | Certificado Authenticode `.pfx` codificado en Base64 |
| `WINDOWS_SIGNING_CERTIFICATE_PASSWORD` | Contraseña del certificado de Windows |
| `MACOS_SIGNING_CERTIFICATE_BASE64` | Certificado Apple Developer `.p12` codificado en Base64 |
| `MACOS_SIGNING_CERTIFICATE_PASSWORD` | Contraseña del certificado de Apple |
| `MACOS_SIGNING_IDENTITY` | Identidad exacta de `codesign` |
| `APPLE_ID` | Cuenta Apple Developer para notarización |
| `APPLE_TEAM_ID` | Identificador del equipo Apple Developer |
| `APPLE_APP_PASSWORD` | Contraseña específica para `notarytool` |
| `RELEASE_SIGNING_KEY_BASE64` | Clave privada GPG de release codificada en Base64 |
| `RELEASE_SIGNING_KEY_PASSPHRASE` | Contraseña de la clave GPG del release |
| `RELEASE_SIGNING_KEY_FINGERPRINT` | Huella completa, sin espacios, de la clave pública de release; el workflow falla si la clave importada no coincide |

Windows usa Authenticode SHA-256 con un servicio público de timestamp. macOS usa
runtime endurecido, notariza y estampa el DMG. El job también firma con GPG
los archivos fuente, instaladores, wheels, paquetes y archivos portátiles de los Gestores y `SHA256SUMS`, y
verifica cada firma antes de publicar. Las imágenes de contenedor usan firma y
verificación Sigstore sin clave.

Si falta o es inválido cualquier secreto requerido, el workflow falla antes de
publicar. Nunca imprimas secretos ni guardes certificados o claves privadas en el
repositorio.

Después de publicar, el workflow verifica cada URL esperada y el `.asc` requerido;
todos los paquetes y archivos portátiles de los Gestores están incluidos en `SHA256SUMS`.

## Verificar una descarga

Cada release estable también publica `TrinaxAI-release-signing-key.asc` y
`TrinaxAI-release-signing-key.fingerprint`. Compara esa huella con el valor de
confianza anunciado en el release antes de importar la clave. No ejecutes un
instalador o script de un release que no publique ambos archivos.

```bash
version=v1.2.0
base="https://github.com/TrinaxCode/TrinaxAI/releases/download/${version}"
curl -fLO "${base}/TrinaxAI-release-signing-key.asc"
curl -fLO "${base}/TrinaxAI-release-signing-key.fingerprint"
gpg --show-keys --fingerprint TrinaxAI-release-signing-key.asc
gpg --import TrinaxAI-release-signing-key.asc
curl -fLO "${base}/SHA256SUMS"
curl -fLO "${base}/SHA256SUMS.asc"
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum --check SHA256SUMS
```

Verifica el `.asc` separado del instalador o archivo exacto antes de abrirlo o
ejecutarlo. El workflow publica la clave pública y la huella; los mantenedores
deben publicar la huella confiable por un canal independiente antes de llamar
firmado a un release.
