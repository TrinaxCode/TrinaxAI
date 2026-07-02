# Checklist de Publicacion V1 de TrinaxAI

Usa esta lista antes de etiquetar o publicar una version publica de TrinaxAI.

## Chequeos Requeridos

Ejecuta desde la raiz del repositorio:

```bash
python3 scripts/public_readiness.py
python3 -m py_compile rag_api.py index.py config.py trinaxai_cli.py service_manager.py test_system.py scripts/public_readiness.py
cd chat-pwa && npm run build
```

Para una prueba local de runtime:

```bash
python3 test_system.py --verbose
```

## Alcance de la Version

V1 usa instalacion nativa por defecto. Es intencional: Ollama local, indexacion de archivos del host, HTTPS en LAN y acceso desde telefono funcionan de forma mas predecible nativamente que en Docker para la mayoria de usuarios.

Publica solo codigo fuente, documentacion, scripts y lockfiles. No publiques datos de runtime:

- `.env`
- `.venv/`
- `chat-pwa/node_modules/`
- `chat-pwa/dist/`
- `storage/`
- `local_sources/`
- `logs/`
- `backups/`

## Verificacion Manual

Antes de publicar, verifica estos flujos en una instalacion limpia:

- Instalar en Linux, macOS o Windows usando el instalador documentado.
- Abrir la PWA en `https://localhost:3334`.
- Completar la configuracion inicial una sola vez y confirmar que no reaparece en otro navegador/dispositivo sincronizado.
- Usar chat en ingles y espanol; TrinaxAI debe responder en el idioma del mensaje actual.
- Usar `Apagar IA`; Ollama y RAG deben apagarse y permanecer apagados despues de reiniciar.
- Usar `Encender IA`; Ollama y RAG deben iniciar y permanecer habilitados despues de reiniciar.
- Ejecutar una indexacion y confirmar que las fuentes aparecen en respuestas RAG.
- Abrir Configuracion > Estadisticas y confirmar que los conteos cambian despues de usar la app.

## Defaults de Rendimiento

Manten defaults conservadores para equipos locales:

- Perfil 8 GB: contexto pequeno, un worker de embeddings, LLM `keep_alive=0s`, embeddings `keep_alive=10m`, batch de embeddings 2.
- Perfil 16 GB: contexto balanceado, dos workers de embeddings, LLM `keep_alive=0s`, embeddings `keep_alive=15m`, batch de embeddings 8.
- Perfil max: contexto mas grande, cuatro workers de embeddings, LLM `keep_alive=30m`, embeddings `keep_alive=30m`, batch de embeddings 8.
- Perfil ultra: contexto maximo, seis workers de embeddings, LLM `keep_alive=60m`, embeddings `keep_alive=30m`, batch de embeddings 16.

Variables utiles:

- `TRINAXAI_INDEX_BATCH_SIZE=100` controla el lote de carga de documentos durante la indexacion.
- `TRINAXAI_RATE_LIMIT_PER_MINUTE=30` protege la CPU local de clientes descontrolados.
- `TRINAXAI_EMBED_WORKERS` debe mantenerse bajo en maquinas de 8 GB.
- `TRINAXAI_EMBED_KEEP_ALIVE` debe quedar por encima de `0s` para indexar; `0s` recarga el embedder entre lotes.

## Notas de Seguridad

Las acciones de sistema estan pensadas para localhost o clientes LAN confiables. Si expones TrinaxAI fuera de una LAN privada, configura `TRINAXAI_ADMIN_TOKEN` y prefiere una VPN como Tailscale o WireGuard.

La ruta legacy `setup_trinaxai.sh` puede crear servicios de sistema y reglas sudoers. Para produccion, prefiere la ruta de autoarranque por defecto con `service_manager.py` o mueve los scripts permitidos a ubicaciones propiedad de root.
