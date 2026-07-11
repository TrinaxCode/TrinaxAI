# Checklist de Publicacion V1 de TrinaxAI

Usa esta lista antes de etiquetar o publicar una version publica de TrinaxAI.

## Chequeos Requeridos

Ejecuta desde la raíz del repositorio:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pip install -e .
python3 scripts/public_readiness.py
python3 -m py_compile rag_api.py index.py config.py trinaxai_cli.py service_manager.py test_system.py scripts/public_readiness.py
ruff check .
pytest -q
bash -n install.sh
bash -n backup.sh
bash -n uninstall.sh
# En Windows/PowerShell, también valida:
# powershell -NoProfile -ExecutionPolicy Bypass -File .\update.ps1 -NonInteractive -NoPull -NoBackup -NoRestart -NoAudit
# powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1 -Yes -KeepServices -KeepAutostart -KeepVenv -KeepFrontend -KeepLogs -KeepEnv -KeepFirewall
cd chat-pwa && npm run build
cd chat-pwa && npm test
cd chat-pwa && npm audit --audit-level=high
```

Para una prueba local de runtime:

```bash
python3 test_system.py --verbose
trinaxai --help
trinaxai doctor
```

## Versionado

Usa etiquetas SemVer:

- `v1.0.0-rc.1` para un candidato de lanzamiento.
- `v1.0.0` para el primer lanzamiento público estable.
- `v1.0.1` para correcciones solo de parches.
- `v1.1.0` para lanzamientos de funcionalidades compatibles hacia atrás.

Etiqueta desde un árbol limpio:

```bash
git tag -a v1.0.0 -m "TrinaxAI v1.0.0"
git push origin v1.0.0
```

## Publicación en GitHub

Crea un GitHub Release desde la etiqueta SemVer con:

- Notas de lanzamiento de `CHANGELOG.md`.
- Comando de instalación para Linux/macOS.
- Comando de instalación PowerShell para Windows.
- Limitaciones conocidas y notas de actualización.
- Enlaces a `SECURITY.md`, `CONTRIBUTING.md` y guías de instalación por plataforma.

Assets sugeridos:

- Archivo fuente generado por GitHub.
- `install.sh`
- `install.ps1`
- Archivo de checksums opcional para los scripts de instalación.

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
- Abrir Configuración > Estadísticas y confirmar que los conteos cambian después de usar la app.
- Ejecutar `trinaxai`, `/help`, `/status`, `/clear`, y `/exit`.
- Ejecutar `trinaxai index .` en un pequeño proyecto de prueba.

## Defaults de Rendimiento

Manten defaults conservadores para equipos locales:

- Perfil 8 GB: modelos 1B/1.5B, embeddings lite, contexto pequeno, un worker de embeddings, LLM `keep_alive=0s`, embeddings `keep_alive=5m`, batch de embeddings 1.
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
