# Hoja de ruta

Esta hoja de ruta mantiene la V1 enfocada en la estabilidad antes de ampliar el alcance. Los plazos son aproximados y están impulsados por la comunidad.

---

## ✅ V1 (Hecho)

- [x] Chat local estable a través de Ollama
- [x] RAG sobre carpetas importadas y proyectos indexados
- [x] Acceso PWA desde escritorio y teléfonos en LAN de confianza
- [x] Memoria local explícita con auto-resumen
- [x] Rutas de instalación multiplataforma (Linux, macOS, Windows)
- [x] Verificaciones de lanzamiento público, notas de seguridad, docs de soporte y flujo de contribución
- [x] Recuperación híbrida con reranker opcional
- [x] Observador de archivos para reindexado automático
- [x] Sincronización de estado entre dispositivos
- [x] Modo de investigación profunda (multi-pasada)
- [x] CLI para desarrolladores (`trinaxai ask`, `trinaxai chat`, `trinaxai index`, `trinaxai doctor`)
- [x] Configuración segura por defecto: control LAN desactivado, token admin auto-generado
- [x] README bilingüe, FAQ, modelo de seguridad y guías de instalación

---

## 🔜 En progreso / Próximo plazo

- [ ] **Capturas de pantalla y GIFs de demostración** — Evidencia visual de la PWA y CLI en acción
- [ ] **Explorador visual de proyectos** — Vista de árbol de archivos indexados en la PWA
- [ ] **Resumen de conversaciones** — Auto-resumen de chats largos para preservar contexto
- [ ] **Eventos de indexación estructurados** — Progreso más detallado para mejor ETA
- [ ] **Plantillas de prompts** — Guardar y reutilizar prompts personalizados por colección
- [ ] **Expansión de CI** — Agregar CodeQL, Gitleaks, Semgrep, Trivy y pytest

---

## 📅 Planeado

- [ ] **Cobertura de pruebas** — pytest para backend, vitest + Testing Library para frontend
- [ ] **Despliegue con Docker/Compose** — Stack contenerizado reproducible (usuarios avanzados)
- [ ] **Más perfiles de modelos** — Detección automática para GPU potentes (RTX 4090, M2 Ultra)
- [ ] **Ajuste de límites de tasa** — Límites configurables por usuario
- [ ] **Servidor MCP** — Model Context Protocol para integración con IDEs más allá de Continue.dev
- [ ] **Integración con Obsidian** — Sincronización bidireccional con bóvedas de Obsidian

---

## 🚀 Ideas futuras

- [ ] **Sistema de plugins** — Extensiones mediante entry points de Python
- [ ] **Notificaciones push en móvil** — Sincronización en segundo plano del service worker
- [ ] **Soporte multiusuario** — Colecciones, memoria e historial por usuario
- [ ] **Documentación OpenAPI/Swagger** — Generada automáticamente desde FastAPI
- [ ] **Streaming WebSocket** — Chat bidireccional para menor latencia
- [ ] **Suite de benchmarks** — Pruebas de regresión de rendimiento para recuperación e indexación

---

## Contribuir

¿Quieres trabajar en algo? Revisa los [issues](https://github.com/TrinaxCode/TrinaxAI/issues) o abre una discusión. PRs bienvenidas — consulta [CONTRIBUTING.md](CONTRIBUTING.md).
