# Política de Seguridad — TrinaxAI

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

TrinaxAI es una aplicación **local** — se ejecuta completamente en tu máquina. La superficie de ataque principal es:

| Componente | Riesgo | Notas |
|------------|--------|-------|
| **RAG API** (`rag_api.py`) | Medio | Puede enlazarse a `0.0.0.0`. Los endpoints administrativos requieren loopback, LAN privada habilitada o token; chat y algunas rutas de lectura/subida siguen accesibles dentro de la frontera de red configurada. |
| **PWA Frontend** (`chat-pwa/`) | Bajo | App React estática. Se recomiendan cabeceras CSP para despliegues en producción. |
| **Scripts de Shell** | Bajo | El uso de `sudo` está documentado. Los scripts deben auditarse antes de usarse en producción. |
| **Ollama** | Medio | Ollama no tiene autenticación integrada. Cuando se expone en la LAN (`OLLAMA_HOST=0.0.0.0`), cualquier persona en tu red puede usar tus modelos. |
| **Subidas** | Medio | La indexación de carpetas está protegida y aislada en `local_sources/collections/`. Adjuntos de chat y extracción temporal no tienen autenticación; aplican límites de tamaño y la API debe permanecer en una red confiable. |

## Fuera del alcance

- Vulnerabilidades en dependencias de terceros (Ollama, LlamaIndex, módulos de Node.js) — repórtalas en sus repositorios correspondientes
- Ataques de ingeniería social contra los usuarios
- Acceso físico a la máquina host
- Denegación de servicio por agotamiento de recursos (inherente a ejecutar LLMs localmente)

## Modelo de amenazas

El modelo de amenazas de TrinaxAI asume:

1. **Máquina local confiable** — el host no está comprometido
2. **LAN confiable (si está habilitada)** — los dispositivos en la misma WiFi son confiables cuando `TRINAXAI_ALLOW_LAN_SYSTEM=1`
3. **Internet no confiable** — TrinaxAI nunca debe exponerse directamente a internet sin una VPN o proxy inverso autenticado

### Vectores de ataque considerados

- **Atacante en LAN** (misma WiFi, sin autenticación): La administración protegida no está disponible por defecto. Si la API es alcanzable, las rutas públicas incluyen salud/recursos, lecturas de colecciones/estado, chat/voz con límite, extracción temporal y subida/descarga de adjuntos. Trata la LAN como confiable o enlaza la API a loopback.
- **Atacante en LAN + mala configuración** (`ALLOW_LAN_SYSTEM=1`, sin token): Control total del sistema (apagado, inicio, indexación, subida de archivos). **Por eso está desactivado por defecto.**
- **Atacante remoto** (internet): Debería ser imposible si los puertos no están reenviados. Usa una VPN para acceso remoto.
- **Tarball malicioso** (`backup.sh restore`): El contenido del tarball se valida antes de la extracción — se rechazan rutas absolutas y entradas `..`.

## Buenas prácticas de seguridad para quien despliega

1. **Mantén desactivado el control de sistema desde LAN** salvo que entiendas el riesgo y estés en una red confiable.
2. **Configura `TRINAXAI_ADMIN_TOKEN`** con un valor fuerte si activas el control de sistema desde LAN.
3. **Restringe Ollama** a `127.0.0.1` si solo necesitas acceso local, o usa un firewall para limitar el acceso al puerto 11434.
4. **Audita el archivo sudoers** (`/etc/sudoers.d/trinaxai`) si usas el setup avanzado de systemd.
5. **Mantén las dependencias actualizadas** — ejecuta `pip-audit` y `npm audit` con regularidad.
6. **Mantén TrinaxAI en localhost o en una LAN privada de confianza** salvo que lo ubiques detrás de una VPN o un proxy inverso con autenticación.

## Seguridad del repositorio

- CI ejecuta `ruff check`, `py_compile`, `npx tsc --noEmit`, `npm audit` y `scripts/public_readiness.py`
- Dependabot monitorea dependencias de Python y npm semanalmente
- No se almacenan secretos, tokens ni credenciales en el repositorio (aplicado por `.gitignore`)

Adiciones recomendadas para repositorios en producción:
- `gitleaks` para detección de secretos
- `semgrep` para SAST
- `CodeQL` para análisis profundo de código
- `trivy` para escaneo de vulnerabilidades

## Agradecimientos

Agradecemos a todos los investigadores de seguridad que divulgan vulnerabilidades de forma responsable. Los colaboradores serán listados aquí (con su permiso).
