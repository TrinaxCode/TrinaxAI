# Hoja de ruta

Esta hoja de ruta mantiene la V1 enfocada en la estabilidad antes de ampliar el alcance. Los plazos son aproximados y están impulsados por la comunidad.

---

## ✅ V1 (Completada — junio de 2026)

- [x] Chat local estable a través de Ollama
- [x] RAG sobre carpetas importadas y proyectos indexados
- [x] Acceso PWA desde escritorio y teléfonos en LAN de confianza
- [x] Memoria local explícita con auto-resumen
- [x] Rutas de instalación multiplataforma para Linux, macOS y Windows
- [x] Verificaciones de lanzamiento público, notas de seguridad, documentación de soporte y flujo de contribución
- [x] Recuperación híbrida con reranker opcional
- [x] Observador de archivos para reindexado automático
- [x] Sincronización de estado entre dispositivos
- [x] Modo de investigación profunda (multi-pasada)

---

## 🔜 Próximo plazo (Q3 2026)

- [ ] **Explorador visual de proyectos** — Vista de árbol de archivos indexados en la PWA
- [ ] **Resumen de conversaciones** — Auto-resumen de chats largos para preservar la ventana de contexto
- [ ] **Eventos de indexación estructurados** — Progreso más detallado desde index.py para una mejor estimación del tiempo restante
- [ ] **Explorador de colecciones/proyectos mejorado** — Inspección y búsqueda visual de fuentes indexadas
- [ ] **Plantillas de prompts** — Guardar y reutilizar prompts de sistema personalizados por colección
- [ ] **Ajuste de límites de tasa en la API** — Límites configurables por usuario

---

## 📅 Mediano plazo (Q4 2026+)

- [ ] **Despliegue con Docker/Compose** — Stack contenerizado reproducible (para usuarios avanzados)
- [ ] **Más perfiles de modelos** — Detección automática para máquinas con GPU potentes (RTX 4090, M2 Ultra)
- [ ] **Sistema de plugins** — Extensiones de herramientas mediante entry points de Python
- [ ] **Cobertura de pruebas E2E** — Pruebas de humo de la PWA (Playwright) y pruebas del instalador
- [ ] **Servidor MCP** — Model Context Protocol para integración con IDEs más allá de Continue.dev
- [ ] **Integración con Obsidian** — Sincronización bidireccional con bóvedas de Obsidian

---

## 🚀 Más adelante

- [ ] **Notificaciones push en móvil** — Sincronización en segundo plano del service worker para tareas de larga duración
- [ ] **Soporte multiusuario** — Colecciones, memoria e historial de chat por usuario
- [ ] **Documentación OpenAPI/Swagger** — Generada automáticamente desde la app FastAPI
- [ ] **Streaming WebSocket** — Chat bidireccional para menor latencia
- [ ] **TUI de línea de comandos** — Interfaz de terminal con widgets enriquecidos (más allá del REPL)
- [ ] **Suite de benchmarks** — Pruebas de regresión de rendimiento para recuperación e indexación

---

## Contribuir

¿Quieres trabajar en algo? Revisa los [issues](https://github.com/TrinaxCode/TrinaxAI/issues) o abre una discusión. Las PRs son bienvenidas — consulta [CONTRIBUTING.md](CONTRIBUTING.md).
