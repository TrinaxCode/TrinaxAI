# Política de Seguridad — TrinaxAI

## Versiones con soporte

| Versión  | Con soporte        |
|----------|--------------------|
| Última   | :white_check_mark: |
| < Última | :x:                |

Solo el último commit en `main` recibe parches de seguridad.

## Reportar una vulnerabilidad

**No abras un issue público.** En su lugar, envía un correo a:

> **security@trinaxcode.com**

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
| **RAG API** (`rag_api.py`) | Medio | Puede enlazarse a `0.0.0.0` para acceso desde la PWA en LAN. Los endpoints de sistema aceptan localhost por defecto; el control desde LAN requiere `TRINAXAI_ALLOW_LAN_SYSTEM=1` o token de administrador. |
| **PWA Frontend** (`chat-pwa/`) | Bajo | App React estática. Se recomiendan cabeceras CSP para despliegues en producción. |
| **Scripts de Shell** | Bajo | El uso de `sudo` está documentado. Los scripts deben auditarse antes de usarse en producción. |
| **Ollama** | Medio | Ollama no tiene autenticación integrada. Cuando se expone en la LAN (`OLLAMA_HOST=0.0.0.0`), cualquier persona en tu red puede usar tus modelos. |
| **Carga de carpetas** | Bajo | Los archivos subidos se sanean y se aislan en `local_sources/collections/`. |

## Fuera del alcance

- Vulnerabilidades en dependencias de terceros (Ollama, LlamaIndex, módulos de Node.js) — repórtalas en sus repositorios correspondientes
- Ataques de ingeniería social contra los usuarios
- Acceso físico a la máquina host
- Denegación de servicio por agotamiento de recursos (inherente a ejecutar LLMs localmente)

## Buenas prácticas de seguridad para quien despliega

1. **Mantén desactivado el control de sistema desde LAN** salvo que entiendas el riesgo y estés en una red confiable.
2. **Configura `TRINAXAI_ADMIN_TOKEN`** con un valor fuerte si activas el control de sistema desde LAN.
3. **Restringe Ollama** a `127.0.0.1` si solo necesitas acceso local, o usa un firewall para limitar el acceso al puerto 11434.
4. **Audita el archivo sudoers** (`/etc/sudoers.d/trinaxai`) si usas el setup avanzado de systemd.
5. **Mantén las dependencias actualizadas** — ejecuta `pip-audit` y `npm audit` con regularidad.
6. **Mantén TrinaxAI en localhost o en una LAN privada de confianza** salvo que lo ubiques detrás de una VPN o un proxy inverso con autenticación.

## Agradecimientos

Agradecemos a todos los investigadores de seguridad que divulgan vulnerabilidades de forma responsable. Los colaboradores serán listados aquí (con su permiso).
