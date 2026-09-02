<h1 align="center">
  <a href="https://www.trinaxai.app/"><img src="../chat-pwa/public/logo.webp" alt="TrinaxAI" width="64" valign="middle"></a>
  <a href="https://www.trinaxai.app/">TrinaxAI</a> · 🛡️ Seguridad
</h1>

<p align="center">
  <a href="https://github.com/TrinaxCode/TrinaxAI"><img src="https://img.shields.io/github/stars/TrinaxCode/TrinaxAI?style=flat&amp;label=%E2%98%85&amp;color=006bbd" alt="GitHub stars"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/releases/tag/v1.2.1"><img src="https://img.shields.io/badge/version-1.2.1-006bbd" alt="Stable release: 1.2.1"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/TrinaxCode/TrinaxAI/ci.yml?branch=main&amp;label=CI" alt="CI status"></a>
  <a href="https://github.com/TrinaxCode/TrinaxAI/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0--or--later-006bbd" alt="License: AGPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-4493F8?style=flat-square" alt="Supported platforms: macOS, Windows, and Linux">
</p>

<p align="center"><sub><a href="SECURITY.md">English</a> · <strong>Español</strong></sub></p>
<p align="center"><sub><a href="https://www.trinaxai.app/">Sitio web</a> · <a href="README.es.md">Documentación</a> · <a href="../README.es.md">Inicio</a> · <a href="CHANGELOG.es.md">Cambios</a></sub></p>

## Versiones con soporte

| Versión  | Con soporte        |
|----------|--------------------|
| Última   | :white_check_mark: |
| < Última | :x:                |

Solo el último commit en `main` recibe parches de seguridad.

## Reportar una vulnerabilidad

**No abras un issue público.** En su lugar, envía un correo a:

> **trinaxcode@gmail.com**

Nuestro objetivo es responder en un plazo de **72 horas** y publicar un parche en un máximo de **7 días** tras la confirmación.

### Qué incluir

- Una descripción clara de la vulnerabilidad
- Pasos para reproducirla (el código de prueba de concepto es de gran ayuda)
- Componentes afectados (RAG API, PWA frontend, scripts de shell, etc.)
- Si crees que es explotable de forma remota o solo localmente
- Cualquier mitigación sugerida

### Proceso

1. Reportas la vulnerabilidad de forma privada por correo.
2. Acusamos recibo en un plazo de 72 horas e iniciamos el triaje.
3. Desarrollamos y probamos un parche.
4. Publicamos un GitHub Security Advisory (GHSA) y un lanzamiento con el parche.
5. Recibes crédito en el advisory (a menos que prefieras el anonimato).

## Alcance

TrinaxAI es **local-first**: la inferencia y los datos persistidos usan por
defecto el host configurado. La instalación/descarga de modelos, investigación
web explícita, assets externos y endpoints remotos configurados usan la red. La
superficie principal es:

| Componente | Riesgo | Notas |
|------------|--------|-------|
| **API RAG** (`app/`) | Medio | El arranque administrado es solo loopback. El gateway firma el peer original con HMAC efímero; se ignoran cabeceras de forwarding ordinarias. Estado privado, fuentes, memoria, adjuntos, agente y administración exigen autorización. |
| **Gateway PWA** (`chat-pwa/vite.config.ts`) | Medio | Frontera HTTPS orientada a LAN. Valida credenciales admin/de dispositivo emparejado, elimina identidad aportada por cliente, firma el peer para FastAPI, aplica cabeceras y publica solo una fachada Ollama con allowlist. |
| **Agente** (`trinaxai_cli/agent/`) | Alto | Las herramientas de archivo resuelven symlinks dentro de raíces registradas. En Linux el shell usa bubblewrap sin red; sin aislamiento compatible falla cerrado. Las acciones peligrosas piden aprobación y autoaprobación HTTP no está disponible remotamente. |
| **CLI** (`trinaxai_cli/`) | Bajo | Herramienta local con TLS verificado; certificados privados requieren `--ca-file` o `TRINAXAI_CA_FILE`. `--yolo` y shell sin sandbox son opt-ins de alto riesgo. |
| **Lifecycle/backups** | Medio | El privilegio usa wrapper exacto, propiedad de root, no scripts editables del repo. El backup usa modos privados, valida rutas/tipos, restaura en staging y revierte fallos. Aun así contiene datos sensibles y debe cifrarse fuera del host. |
| **Ollama** | Alto si se expone | No tiene autenticación. El arranque administrado usa `127.0.0.1`; nunca expongas 11434 ni un proxy genérico. |
| **Subidas/fetch web** | Medio | Imports con raíces gestionadas, rutas saneadas, cuotas y auth. El fetch web es acotado, valida la IP pública al conectar, rechaza redes privadas/link-local y revalida redirects. Mantén límites conservadores para parsers. |

## Fuera del alcance

- Vulnerabilidades en dependencias de terceros (Ollama, LlamaIndex, módulos de Node.js) — repórtalas en sus repositorios correspondientes
- Ataques de ingeniería social contra los usuarios
- Acceso físico a la máquina host
- Denegación de servicio por agotamiento de recursos (inherente a ejecutar LLMs localmente)

## Modelo de amenazas

El modelo de amenazas de TrinaxAI asume:

1. **Máquina local confiable** — el host no está comprometido
2. **LAN no confiable por defecto** — compartir WiFi no demuestra identidad; las solicitudes remotas protegidas requieren token emparejado con scope o credencial administradora
3. **Internet no confiable** — TrinaxAI nunca debe exponerse directamente a internet sin una VPN o proxy inverso autenticado

### Vectores de ataque considerados

- **Atacante en LAN** (misma WiFi, sin credencial): El gateway conserva la IP
  original firmada, por lo que un cliente proxificado no hereda privilegio
  loopback. Estado, adjuntos, fuentes, memoria, índice/sistema y agente devuelven
  `403`. Solo las rutas de salud/recursos declaradas públicas quedan disponibles
  sin credencial.
- **Token de dispositivo robado:** Es una capability bearer limitada a sus
  scopes. Un claim nuevo de la PWA lo conserva únicamente en una cookie
  `HttpOnly; SameSite=Strict` con alcance `/api/rag`; el navegador nunca recibe
  un bearer nuevo en JSON ni lo persiste en almacenamiento web. FastAPI conserva
  solo un hash con clave y el host/admin puede revocarlo. El almacenamiento
  legacy solo se consume durante la migración explícita de
  `/v1/pairing/me` y se limpia tras una respuesta exitosa. Empareja equipos
  controlados y revoca uno perdido con `trinaxai pair revoke`; la CLI sigue usando
  cabecera.
- **Identidad de proxy falsificada:** El gateway quita cabeceras de identidad
  aportadas por cliente. FastAPI solo acepta una firma HMAC fresca y de un uso
  desde loopback o un peer privado de runtime configurado explícitamente;
  pertenecer a la red no basta sin el secreto de `storage/.proxy_secret`.
- **Prompt injection en documentos/web:** El material recuperado se delimita como
  no confiable y no autoriza herramientas. Mantén la aprobación; yolo HTTP está
  apagado y sigue limitado a loopback real si se activa explícitamente.
- **Atacante remoto** (internet): Debería ser imposible si los puertos no están reenviados. Usa una VPN para acceso remoto.
- **Tarball malicioso** (`backup.sh restore`): Solo se aceptan `.env`, `storage/`
  y `local_sources/`; se rechazan rutas absolutas/traversal, enlaces y devices
  antes del reemplazo por staging.

## Buenas prácticas de seguridad para quien despliega

1. **Mantén FastAPI y Ollama en loopback.** Deja `TRINAXAI_UNSAFE_BIND_BACKEND=0` y publica solo el gateway autenticado.
2. **Empareja con mínimo privilegio.** `trinaxai pair start` concede
   `chat,read_private` y solo puede añadir `web`. Revisa `trinaxai pair list` y
   revoca equipos perdidos o en desuso.
3. **Administra solo desde `https://localhost:3334`.** Indexación, Agente,
   modelos, dispositivos, lifecycle y restauración total requieren loopback
   verificado aunque se envíe credencial admin o un scope retirado.
4. **Protege los secretos de credenciales.** No compartas
   `storage/.proxy_secret` ni `storage/.device_secret`; conserva modo `0600`
   también en `storage/device_pairing.json`.
5. **Usa firewall y VPN**; limita la PWA a dispositivos previstos y bloquea acceso directo a 3333/11434.
6. **Mantén dependencias reproducibles/auditadas** — instala `requirements.lock`, ejecuta `pip-audit --require-hashes -r requirements.lock --ignore PYSEC-2026-3740` y `npm audit`. La excepción acotada de NLTK cubre un aviso upstream sobre rutas de modelos sin versión corregida; TrinaxAI no usa esas API de persistencia y CI debe eliminar la excepción cuando NLTK publique una corrección.
7. **Mantén el shell con fallo cerrado.** Instala bubblewrap en Linux y no habilites `TRINAXAI_AGENT_ALLOW_UNSANDBOXED_COMMANDS` en servicios remotos.
8. **Cifra backups** cuando salgan del host; contienen `.env`, chats, adjuntos, fuentes e índices aunque el archivo tenga modo privado.
9. **Audita** con `trinaxai doctor --strict --json` y `python3 scripts/public_readiness.py`.

## Seguridad del repositorio

- CI ejecuta tests/build/typecheck/lint, `pip-audit` sobre lock con hashes,
  Bandit, `npm audit`, gitleaks, CodeQL y readiness; genera SBOM CycloneDX Python
- Dependabot monitorea dependencias de Python y npm semanalmente
- No se almacenan secretos, tokens ni credenciales en el repositorio (aplicado por `.gitignore`)
- Los tags construyen archive determinista, SHA-256 y provenance
  GitHub/Sigstore. La tarea programada solo comprueba disponibilidad; la
  actualización permanece como operación manual revisada.

## Agradecimientos

Agradecemos a todos los investigadores de seguridad que divulgan vulnerabilidades de forma responsable. Los colaboradores serán listados aquí (con su permiso).
