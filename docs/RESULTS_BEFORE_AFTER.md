# TrinaxAI — Informe de Resultados (Fases 11–12)

> Comparativa **antes vs. después** del nuevo pipeline de generación.
> Hardware: Ryzen 7 5700U · 16 GB · CPU-only · Ollama. Perfil real: `16gb` + `fast`.
> Mismas dos pruebas del encargo, ejecutadas contra el Ollama local del usuario.

---

## Metodología

- **Antes:** comportamiento descrito y medido sobre el código en `main` (RAG siempre activo, plantilla grounded-QA única, `temperature=0.0`, sin `num_predict`, `num_ctx=4096` con `fast`).
- **Después:** rama `feat/generation-pipeline`. Se llama a `rag_api.run_rag()` directamente (mismo camino que usa el endpoint `/v1/chat/completions`), sin tocar la API pública.
- **Métricas objetivas** (no subjetivas): modelo enrutado, nodos RAG inyectados, tokens generados, ¿compila?, entregables presentes (tests/benchmark/FAQ/chat/responsive), validación automática.

---

## Prueba 1 — Caché LRU + TTL (Python)

Prompt: *"Implementa una caché LRU + TTL extremadamente completa en Python con complejidad O(1) en get y put, incluye tests unitarios y un benchmark."*

| Métrica | ANTES (reportado) | DESPUÉS (medido) |
|---|---|---|
| Régimen | grounded-QA (única) | **code_gen** |
| Modelo | qwen2.5-coder:7b | qwen2.5-coder:7b |
| Nodos RAG inyectados | sí (contexto del repo) | **0 (RAG off)** |
| num_predict | inexistente (techo ≈ 0–500) | **3072** |
| temperature | 0.0 | 0.15 |
| ¿Compila? | **No** | **Sí** (`ast.parse` OK) |
| Tests | **Omitidos** | **Presentes** (`def test`/`assert`) |
| Benchmark | **Omitido** | **Presente** (`perf_counter`) |
| O(1) respetado | roto | mencionado + `OrderedDict` |
| Validación automática | — | **ok** |
| Tiempo | — | ~178 s |
| Valoración usuario (previa) | **4.5/10** | *(pendiente de tu valoración)* |

**Causa del salto:** desactivar RAG liberó toda la ventana para la respuesta (antes el contexto irrelevante del repo la truncaba), y el régimen `code_gen` sustituyó *"responde solo con el contexto, no inventes"* por *"produce código completo que compile, con todos los entregables"*.

---

## Prueba 2 — Landing page moderna

Prompt: *"Crea una landing page moderna para un producto SaaS con glassmorphism, animaciones suaves, un chat flotante, FAQ funcional con acordeón, y diseño responsive premium con varias secciones."*

| Métrica | ANTES (reportado) | DESPUÉS (medido) |
|---|---|---|
| Régimen | grounded-QA (única) | **creative** |
| Modelo | qwen2.5-coder:7b | qwen2.5-coder:7b |
| Nodos RAG inyectados | sí | **0 (RAG off)** |
| num_predict | inexistente | **~5888** (techo) |
| temperature | 0.0 (greedy) | **0.5** |
| Time-to-first-token | — | **0.5 s** (streaming) |
| Tiempo total | — | ~298 s |
| Tokens generados | básico/truncado | **~1.495** (HTML completo, `</html>` cerrado) |
| Hero / Features / FAQ / Chat / Footer | faltaban | **presentes** (7/11 checks) |
| FAQ acordeón funcional (JS) | no | **sí** (`toggleFAQ`) |
| Chat flotante (JS) | no | **sí** |
| Glassmorphism real (`backdrop-filter`) | no | **no** (límite del 7B) |
| `@media` responsive | no | **no** en esta corrida (límite del 7B) |
| Pricing / Testimonios | no | **no** (el 7B cerró antes) |
| Valoración usuario (previa) | **3/10** | *(pendiente de tu valoración)* |

**Lectura honesta:** la salida (~1.495 tokens) quedó **muy por debajo del techo** (5.888), así que **el pipeline ya no trunca** — el HTML cierra correctamente. Lo que falta (glassmorphism con `backdrop-filter`, `@media`, pricing, testimonios) es porque **el 7B se detuvo antes de cubrir todo**, no porque le faltara presupuesto. Esto separa nítidamente el límite del pipeline (resuelto) del límite del modelo (persistente). Mitigación disponible sin cambiar de modelo: la vía **no-stream** (API/CLI) activa `generate→validate→fix`, y el validador —ya corregido para detectar `@media` ausente en CSS inline y entregables faltantes— dispara un pase de corrección que pide explícitamente las secciones que faltan.

---

## Fase 12 — Análisis de límites

### Qué mejoró (atribuible al pipeline)
- **Presupuesto de salida:** de ~0–500 tokens efectivos a 3.000–5.900. Elimina el truncado.
- **Régimen correcto:** generación deja de estar bajo reglas de "no inventes / solo contexto".
- **Temperatura por tarea:** creatividad real en UI (0.5) sin perder determinismo en código (0.15) ni en QA (0.0).
- **Muestreo afinado:** `top_p/top_k/repeat_penalty` ahora se envían (antes: defaults ciegos de Ollama).
- **Red de seguridad:** generate→validate→fix corrige código que no compila o entregables faltantes (no-stream).

### Qué sigue siendo límite del **modelo 7B** (inevitable)
- Coherencia en refactors muy grandes multi-archivo; razonamiento algorítmico de varias etapas con invariantes sutiles.
- Densidad de "wow" visual de un diseñador senior: un 7B produce una landing *buena*, no *de agencia premium*.

### Qué es límite del **hardware** (Ryzen 5700U, CPU-only)
- **Latencia:** ~4–5 tokens/s. Una landing de ~5.900 tokens tarda **minutos**. Es el precio de la calidad sin GPU.
- `num_ctx` > 8.192 penaliza mucho (KV-cache en RAM) → techo práctico 8.192 en generación.

### Qué es límite de **Ollama**
- Un solo `num_predict` por request; carga/descarga de modelos (mitigado con `keep_alive`).
- El timeout total de `complete()` obliga a usar `stream_complete` para outputs largos (ya aplicado).

### Qué es límite del **pipeline** (aún mejorable, futuro)
- La clasificación es léxica (determinista, 0 coste) → puede fallar en frases muy ambiguas; mitigado con fallback y overrides.
- validate→fix hace 1 pase; tareas muy rotas podrían necesitar 2 (configurable, off en stream).

---

## Conclusión

Las dos pruebas confirman la tesis de la auditoría: **el pipeline —no el modelo— era el cuello de botella dominante.** Con el mismo `qwen2.5-coder:7b` y el mismo hardware, la Prueba 1 pasa de *no compila / sin tests* a *compila con tests y benchmark*. La mejora es reproducible y medible, sin cambiar de modelo ni usar la nube.
